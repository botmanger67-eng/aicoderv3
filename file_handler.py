"""
File handler module for Telegram bot.
Handles file uploads (images, documents, voice, video) and saves metadata to database.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Union
from pathlib import Path

from telegram import Update, Document, PhotoSize, Voice, Video, Audio, Animation
from telegram.ext import ContextTypes
from telegram.constants import FileSizeLimit

import aiofiles
import aiofiles.os
from PIL import Image

from database import DatabaseManager

# Configure logging
logger = logging.getLogger(__name__)

# Constants
UPLOAD_DIR = Path("uploads")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
ALLOWED_DOCUMENT_TYPES = {".pdf", ".doc", ".docx", ".txt", ".csv", ".xlsx", ".pptx", ".zip", ".rar"}
ALLOWED_VIDEO_TYPES = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
ALLOWED_AUDIO_TYPES = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}

class FileHandler:
    """Handles file uploads and metadata storage."""
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize FileHandler.
        
        Args:
            db_manager: DatabaseManager instance for storing file metadata
        """
        self.db = db_manager
        self._ensure_upload_directory()
    
    def _ensure_upload_directory(self) -> None:
        """Create upload directory if it doesn't exist."""
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f"Upload directory ensured at {UPLOAD_DIR}")
        except Exception as e:
            logger.error(f"Failed to create upload directory: {e}")
            raise
    
    async def _generate_unique_filename(self, original_filename: str) -> str:
        """
        Generate a unique filename to prevent collisions.
        
        Args:
            original_filename: Original filename from Telegram
            
        Returns:
            Unique filename string
        """
        extension = Path(original_filename).suffix if original_filename else ""
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{timestamp}_{unique_id}{extension}"
    
    async def _save_file(self, file_data: bytes, filename: str) -> Optional[Path]:
        """
        Save file data to disk.
        
        Args:
            file_data: Binary file data
            filename: Name to save the file as
            
        Returns:
            Path to saved file or None if failed
        """
        try:
            file_path = UPLOAD_DIR / filename
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)
            logger.info(f"File saved: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to save file {filename}: {e}")
            return None
    
    async def _get_file_metadata(self, file_obj: Union[Document, PhotoSize, Voice, Video, Audio, Animation]) -> Dict[str, Any]:
        """
        Extract metadata from Telegram file object.
        
        Args:
            file_obj: Telegram file object
            
        Returns:
            Dictionary containing file metadata
        """
        metadata = {
            "file_id": file_obj.file_id,
            "file_unique_id": file_obj.file_unique_id,
            "file_size": file_obj.file_size,
            "mime_type": getattr(file_obj, 'mime_type', None),
            "file_name": getattr(file_obj, 'file_name', None),
            "duration": getattr(file_obj, 'duration', None),
            "width": getattr(file_obj, 'width', None),
            "height": getattr(file_obj, 'height', None),
            "thumbnail": getattr(file_obj, 'thumbnail', None),
        }
        
        # Additional metadata for specific file types
        if isinstance(file_obj, PhotoSize):
            metadata["file_type"] = "photo"
        elif isinstance(file_obj, Document):
            metadata["file_type"] = "document"
        elif isinstance(file_obj, Voice):
            metadata["file_type"] = "voice"
        elif isinstance(file_obj, Video):
            metadata["file_type"] = "video"
        elif isinstance(file_obj, Audio):
            metadata["file_type"] = "audio"
        elif isinstance(file_obj, Animation):
            metadata["file_type"] = "animation"
        
        return metadata
    
    async def _validate_file(self, file_obj: Union[Document, PhotoSize, Voice, Video, Audio, Animation]) -> bool:
        """
        Validate file before processing.
        
        Args:
            file_obj: Telegram file object
            
        Returns:
            True if file is valid, False otherwise
        """
        # Check file size
        if file_obj.file_size and file_obj.file_size > MAX_FILE_SIZE:
            logger.warning(f"File too large: {file_obj.file_size} bytes")
            return False
        
        # Check file type if applicable
        if hasattr(file_obj, 'file_name') and file_obj.file_name:
            extension = Path(file_obj.file_name).suffix.lower()
            if isinstance(file_obj, Document):
                if extension not in ALLOWED_DOCUMENT_TYPES:
                    logger.warning(f"Unsupported document type: {extension}")
                    return False
            elif isinstance(file_obj, Video):
                if extension not in ALLOWED_VIDEO_TYPES:
                    logger.warning(f"Unsupported video type: {extension}")
                    return False
            elif isinstance(file_obj, Audio):
                if extension not in ALLOWED_AUDIO_TYPES:
                    logger.warning(f"Unsupported audio type: {extension}")
                    return False
        
        return True
    
    async def _process_image(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Process image file to extract additional metadata.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Dictionary with image metadata or None if failed
        """
        try:
            with Image.open(file_path) as img:
                return {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                    "is_animated": getattr(img, "is_animated", False),
                    "n_frames": getattr(img, "n_frames", 1)
                }
        except Exception as e:
            logger.error(f"Failed to process image {file_path}: {e}")
            return None
    
    async def handle_file_upload(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        file_obj: Union[Document, PhotoSize, Voice, Video, Audio, Animation]
    ) -> Optional[Dict[str, Any]]:
        """
        Handle file upload from Telegram.
        
        Args:
            update: Telegram update object
            context: Telegram context object
            file_obj: Telegram file object to process
            
        Returns:
            Dictionary with file information or None if failed
        """
        user_id = update.effective_user.id if update.effective_user else None
        chat_id = update.effective_chat.id if update.effective_chat else None
        
        try:
            # Validate file
            if not await self._validate_file(file_obj):
                logger.warning(f"File validation failed for user {user_id}")
                return None
            
            # Get file from Telegram
            file = await context.bot.get_file(file_obj.file_id)
            
            # Generate unique filename
            original_filename = getattr(file_obj, 'file_name', f"file_{file_obj.file_id}")
            unique_filename = await self._generate_unique_filename(original_filename)
            
            # Download file
            file_data = await file.download_as_bytearray()
            
            # Save file to disk
            saved_path = await self._save_file(file_data, unique_filename)
            if not saved_path:
                logger.error(f"Failed to save file for user {user_id}")
                return None
            
            # Extract metadata
            metadata = await self._get_file_metadata(file_obj)
            metadata["local_path"] = str(saved_path)
            metadata["original_filename"] = original_filename
            metadata["saved_filename"] = unique_filename
            
            # Process image files for additional metadata
            if isinstance(file_obj, PhotoSize) or (
                isinstance(file_obj, Document) and 
                Path(original_filename).suffix.lower() in ALLOWED_IMAGE_TYPES
            ):
                image_metadata = await self._process_image(saved_path)
                if image_metadata:
                    metadata.update(image_metadata)
            
            # Save metadata to database
            file_id = await self.db.save_file_metadata(
                user_id=user_id,
                chat_id=chat_id,
                file_type=metadata.get("file_type", "unknown"),
                file_id=file_obj.file_id,
                file_unique_id=file_obj.file_unique_id,
                file_name=original_filename,
                file_size=file_obj.file_size,
                mime_type=metadata.get("mime_type"),
                local_path=str(saved_path),
                metadata=metadata
            )
            
            if file_id:
                metadata["database_id"] = file_id
                logger.info(f"File uploaded successfully: {original_filename} (ID: {file_id})")
                return metadata
            else:
                logger.error(f"Failed to save file metadata to database")
                return None
                
        except Exception as e:
            logger.error(f"Error handling file upload: {e}", exc_info=True)
            return None
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict[str, Any]]:
        """
        Handle photo upload.
        
        Args:
            update: Telegram update object
            context: Telegram context object
            
        Returns:
            Dictionary with file information or None if failed
        """
        if not update.message or not update.message.photo:
            logger.warning("No photo in message")
            return None
        
        # Get the largest photo (best quality)
        photo = update.message.photo[-1]
        return await self.handle_file_upload(update, context, photo)
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict[str, Any]]:
        """
        Handle document upload.
        
        Args:
            update: Telegram update object
            context: Telegram context object
            
        Returns:
            Dictionary with file information or None if failed
        """
        if not update.message or not update.message.document:
            logger.warning("No document in message")
            return None
        
        return await self.handle_file_upload(update, context, update.message.document)
    
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict[str, Any]]:
        """
        Handle voice message upload.
        
        Args:
            update: Telegram update object
            context: Telegram context object
            
        Returns:
            Dictionary with file information or None if failed
        """
        if not update.message or not update.message.voice:
            logger.warning("No voice message in message")
            return None
        
        return await self.handle_file_upload(update, context, update.message.voice)
    
    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict[str, Any]]:
        """
        Handle video upload.
        
        Args:
            update: Telegram update object
            context: Telegram context object
            
        Returns:
            Dictionary with file information or None if failed
        """
        if not update.message or not update.message.video:
            logger.warning("No video in message")
            return None
        
        return await self.handle_file_upload(update, context, update.message.video)
    
    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict[str, Any]]:
        """
        Handle audio upload.
        
        Args:
            update: Telegram update object
            context: Telegram context object
            
        Returns:
            Dictionary with file information or None if failed
        """
        if not update.message or not update.message.audio:
            logger.warning("No audio in message")
            return None
        
        return await self.handle_file_upload(update, context, update.message.audio)
    
    async def handle_animation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[Dict[str, Any]]:
        """
        Handle animation (GIF) upload.
        
        Args:
            update: Telegram update object
            context: Telegram context object
            
        Returns:
            Dictionary with file information or None if failed
        """
        if not update.message or not update.message.animation:
            logger.warning("No animation in message")
            return None
        
        return await self.handle_file_upload(update, context, update.message.animation)
    
    async def get_file_info(self, file_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve file information from database.
        
        Args:
            file_id: Database ID of the file
            
        Returns:
            Dictionary with file information or None if not found
        """
        try:
            return await self.db.get_file_metadata(file_id)
        except Exception as e:
            logger.error(f"Failed to get file info for ID {file_id}: {e}")
            return None
    
    async def delete_file(self, file_id: int) -> bool:
        """
        Delete file from disk and database.
        
        Args:
            file_id: Database ID of the file to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Get file metadata
            metadata = await self.db.get_file_metadata(file_id)
            if not metadata:
                logger.warning(f"File with ID {file_id} not found in database")
                return False
            
            # Delete file from disk
            local_path = metadata.get("local_path")
            if local_path and Path(local_path).exists():
                await aiofiles.os.remove(local_path)
                logger.info(f"Deleted file from disk: {local_path}")
            
            # Delete from database
            await self.db.delete_file_metadata(file_id)
            logger.info(f"Deleted file metadata for ID {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False
    
    async def cleanup_old_files(self, days: int = 30) -> int:
        """
        Clean up files older than specified days.
        
        Args:
            days: Number of days to keep files (default: 30)
            
        Returns:
            Number of files cleaned up
        """
        try:
            cutoff_date = datetime.now().timestamp() - (days * 24 * 60 * 60)
            cleaned_count = 0
            
            # Get old files from database
            old_files = await self.db.get_old_files(cutoff_date)
            
            for file_metadata in old_files:
                file_id = file_metadata.get("id")
                local_path = file_metadata.get("local_path")
                
                # Delete file from disk
                if local_path and Path(local_path).exists():
                    await aiofiles.os.remove(local_path)
                
                # Delete from database
                await self.db.delete_file_metadata(file_id)
                cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} old files")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return 0

# Create a singleton instance (to be initialized with db_manager)
file_handler: Optional[FileHandler] = None

def get_file_handler(db_manager: DatabaseManager) -> FileHandler:
    """
    Get or create FileHandler instance.
    
    Args:
        db_manager: DatabaseManager instance
        
    Returns:
        FileHandler instance
    """
    global file_handler
    if file_handler is None:
        file_handler = FileHandler(db_manager)
    return file_handler