import aiosqlite
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Async SQLite database manager for the Telegram bot.
    Manages tables for users, projects, files, conversations, and analytics.
    """
    
    def __init__(self, db_path: str = "bot_database.db"):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Initialize the database connection and create tables if they don't exist."""
        try:
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA journal_mode=WAL")
            await self._connection.execute("PRAGMA foreign_keys=ON")
            await self._create_tables()
            logger.info(f"Database initialized successfully at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
            
    async def _create_tables(self) -> None:
        """Create all required database tables."""
        async with self._lock:
            try:
                # Users table
                await self._connection.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        language_code TEXT DEFAULT 'en',
                        is_admin INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL,
                        last_active_at TEXT NOT NULL,
                        total_conversations INTEGER DEFAULT 0,
                        total_projects INTEGER DEFAULT 0,
                        preferences TEXT DEFAULT '{}'
                    )
                """)
                
                # Projects table
                await self._connection.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        project_name TEXT NOT NULL,
                        description TEXT,
                        github_url TEXT,
                        github_repo_name TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_commit_at TEXT,
                        total_files INTEGER DEFAULT 0,
                        total_commits INTEGER DEFAULT 0,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    )
                """)
                
                # Files table
                await self._connection.execute("""
                    CREATE TABLE IF NOT EXISTS files (
                        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        file_name TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_size INTEGER DEFAULT 0,
                        mime_type TEXT,
                        file_type TEXT,
                        content_hash TEXT,
                        uploaded_at TEXT NOT NULL,
                        last_modified_at TEXT NOT NULL,
                        is_deleted INTEGER DEFAULT 0,
                        metadata TEXT DEFAULT '{}',
                        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    )
                """)
                
                # Conversations table
                await self._connection.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        conversation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                        content TEXT NOT NULL,
                        tokens_used INTEGER DEFAULT 0,
                        model_used TEXT,
                        created_at TEXT NOT NULL,
                        metadata TEXT DEFAULT '{}',
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    )
                """)
                
                # Analytics table
                await self._connection.execute("""
                    CREATE TABLE IF NOT EXISTS analytics (
                        analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        event_type TEXT NOT NULL,
                        event_data TEXT DEFAULT '{}',
                        ip_address TEXT,
                        user_agent TEXT,
                        created_at TEXT NOT NULL,
                        session_id TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
                    )
                """)
                
                # Indexes for better performance
                await self._connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_projects_user_id 
                    ON projects(user_id)
                """)
                await self._connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_files_project_id 
                    ON files(project_id)
                """)
                await self._connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_files_user_id 
                    ON files(user_id)
                """)
                await self._connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conversations_user_id 
                    ON conversations(user_id)
                """)
                await self._connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conversations_session_id 
                    ON conversations(session_id)
                """)
                await self._connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_analytics_user_id 
                    ON analytics(user_id)
                """)
                await self._connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_analytics_event_type 
                    ON analytics(event_type)
                """)
                await self._connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_analytics_created_at 
                    ON analytics(created_at)
                """)
                
                await self._connection.commit()
                logger.info("All database tables created successfully")
            except Exception as e:
                logger.error(f"Failed to create tables: {e}")
                raise
                
    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
            
    # ==================== User Operations ====================
    
    async def add_user(self, user_id: int, username: Optional[str] = None,
                      first_name: Optional[str] = None, last_name: Optional[str] = None,
                      language_code: str = 'en') -> bool:
        """
        Add a new user to the database.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            last_name: User's last name
            language_code: User's language code
            
        Returns:
            True if successful, False otherwise
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            async with self._lock:
                await self._connection.execute("""
                    INSERT OR IGNORE INTO users 
                    (user_id, username, first_name, last_name, language_code, 
                     created_at, last_active_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, language_code, now, now))
                await self._connection.commit()
                logger.info(f"User {user_id} added successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to add user {user_id}: {e}")
            return False
            
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by ID.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            User data as dict or None if not found
        """
        try:
            async with self._lock:
                cursor = await self._connection.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user_id,)
                )
                row = await cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
            
    async def update_user_activity(self, user_id: int) -> bool:
        """
        Update user's last active timestamp.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if successful, False otherwise
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            async with self._lock:
                await self._connection.execute(
                    "UPDATE users SET last_active_at = ? WHERE user_id = ?",
                    (now, user_id)
                )
                await self._connection.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update user activity for {user_id}: {e}")
            return False
            
    async def get_all_users(self) -> List[Dict[str, Any]]:
        """
        Get all users from the database.
        
        Returns:
            List of user dictionaries
        """
        try:
            async with self._lock:
                cursor = await self._connection.execute("SELECT * FROM users")
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get all users: {e}")
            return []
            
    async def get_active_users_count(self) -> int:
        """
        Get count of active users.
        
        Returns:
            Number of active users
        """
        try:
            async with self._lock:
                cursor = await self._connection.execute(
                    "SELECT COUNT(*) FROM users WHERE is_active = 1"
                )
                row = await cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Failed to get active users count: {e}")
            return 0
            
    # ==================== Project Operations ====================
    
    async def create_project(self, user_id: int, project_name: str,
                            description: Optional[str] = None) -> Optional[int]:
        """
        Create a new project for a user.
        
        Args:
            user_id: Telegram user ID
            project_name: Name of the project
            description: Project description
            
        Returns:
            Project ID if successful, None otherwise
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            async with self._lock:
                cursor = await self._connection.execute("""
                    INSERT INTO projects 
                    (user_id, project_name, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, project_name, description, now, now))
                await self._connection.commit()
                
                # Update user's project count
                await self._connection.execute("""
                    UPDATE users SET total_projects = total_projects + 1 
                    WHERE user_id = ?
                """, (user_id,))
                await self._connection.commit()
                
                project_id = cursor.lastrowid
                logger.info(f"Project '{project_name}' created for user {user_id}")
                return project_id
        except Exception as e:
            logger.error(f"Failed to create project for user {user_id}: {e}")
            return None
            
    async def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """
        Get project by ID.
        
        Args:
            project_id: Project ID
            
        Returns:
            Project data as dict or None if not found
        """
        try:
            async with self._lock:
                cursor = await self._connection.execute(
                    "SELECT * FROM projects WHERE project_id = ?", (project_id,)
                )
                row = await cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            return None
            
    async def get_user_projects(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all projects for a specific user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of project dictionaries
        """
        try:
            async with self._lock:
                cursor = await self._connection.execute(
                    "SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC",
                    (user_id,)
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get projects for user {user_id}: {e}")
            return []
            
    async def update_project(self, project_id: int, **kwargs) -> bool:
        """
        Update project fields.
        
        Args:
            project_id: Project ID
            **kwargs: Fields to update (project_name, description, status, etc.)
            
        Returns:
            True if successful, False otherwise
        """
        if not kwargs:
            return False
            
        now = datetime.now(timezone.utc).isoformat()
        kwargs['updated_at'] = now
        
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [project_id]
        
        try:
            async with self._lock:
                await self._connection.execute(
                    f"UPDATE projects SET {set_clause} WHERE project_id = ?",
                    values
                )
                await self._connection.commit()
                logger.info(f"Project {project_id} updated successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to update project {project_id}: {e}")
            return False
            
    async def delete_project(self, project_id: int) -> bool:
        """
        Delete a project and its associated files.
        
        Args:
            project_id: Project ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with self._lock:
                # Get user_id before deletion for count update
                cursor = await self._connection.execute(
                    "SELECT user_id FROM projects WHERE project_id = ?", (project_id,)
                )
                row = await cursor.fetchone()
                if not row:
                    return False
                    
                user_id = row[0]
                
                # Delete project (cascade will delete files)
                await self._connection.execute(
                    "DELETE FROM projects WHERE project_id = ?", (project_id,)
                )
                
                # Update user's project count
                await self._connection.execute("""
                    UPDATE users SET total_projects = MAX(0, total_projects - 1) 
                    WHERE user_id = ?
                """, (user_id,))
                
                await self._connection.commit()
                logger.info(f"Project {project_id} deleted successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            return False
            
    # ==================== File Operations ====================
    
    async def add_file(self, project_id: int, user_id: int, file_name: str,
                      file_path: str, file_size: int = 0, mime_type: Optional[str] = None,
                      file_type: Optional[str] = None, content_hash: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """
        Add a file to a project.
        
        Args:
            project_id: Project ID
            user_id: Telegram user ID
            file_name: Name of the file
            file_path: Path to the file
            file_size: Size of the file in bytes
            mime_type: MIME type of the file
            file_type: Type of file (e.g., 'image', 'document', 'code')
            content_hash: Hash of file content
            metadata: Additional metadata as dict
            
        Returns:
            File ID if successful, None otherwise
        """
        now = datetime.now(timezone.utc).isoformat()
        metadata_str = str(metadata) if metadata else '{}'
        
        try:
            async with self._lock:
                cursor = await self._connection.execute("""
                    INSERT INTO files 
                    (project_id, user_id, file_name, file_path, file_size, 
                     mime_type, file_type, content_hash, uploaded_at, last_modified_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (project_id, user_id, file_name, file_path, file_size,
                      mime_type, file_type, content_hash, now, now, metadata_str))
                
                # Update project file count
                await self._connection.execute("""
                    UPDATE projects SET total_files = total_files + 1 
                    WHERE project_id = ?
                """, (project_id,))
                
                await self._connection.commit()
                file_id = cursor.lastrowid
                logger.info(f"File '{file_name}' added to project {project_id}")
                return file_id
        except Exception as e:
            logger.error(f"Failed to add file to project {project_id}: {e}")
            return None
            
    async def get_project_files(self, project_id: int) -> List[Dict[str, Any]]:
        """
        Get all files for a specific project.
        
        Args:
            project_id: Project ID
            
        Returns:
            List of file dictionaries
        """
        try:
            async with self._lock:
                cursor = await self._connection.execute(
                    "SELECT * FROM files WHERE project_id = ? AND is_deleted = 0",
                    (project_id,)
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get files for project {project_id}: {e}")
            return []
            
    async def get_user_files(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all files for a specific user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of file dictionaries
        """
        try:
            async with self._lock:
                cursor = await self._connection.execute(
                    "SELECT * FROM files WHERE user_id = ? AND is_deleted = 0",
                    (user_id,)
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get files for user {user_id}: {e}")
            return []
            
    async def soft_delete_file(self, file_id: int) -> bool:
        """
        Soft delete a file by marking it as deleted.
        
        Args:
            file_id: File ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with self._lock:
                await self._connection.execute(
                    "UPDATE files SET