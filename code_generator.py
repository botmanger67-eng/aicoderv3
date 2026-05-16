"""
Code Generator Module for Telegram Bot
Generates project code from user description using DeepSeek, creates files, and pushes to GitHub.
"""

import os
import json
import tempfile
import shutil
from typing import Optional, Dict, List, Any
from pathlib import Path

import aiofiles
import aiofiles.os
from openai import AsyncOpenAI
from github import Github, GithubException
from github.Repository import Repository
from telegram import Update, Document
from telegram.ext import ContextTypes

from config import Config
from logger import get_logger
from database import Database

logger = get_logger(__name__)


class CodeGenerator:
    """Handles project code generation, file creation, and GitHub push operations."""

    def __init__(self, config: Config, db: Database):
        """
        Initialize CodeGenerator with configuration and database.

        Args:
            config: Application configuration
            db: Database instance for storing project metadata
        """
        self.config = config
        self.db = db
        self.openai_client = AsyncOpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)
        self.github_client = Github(config.GITHUB_TOKEN)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="codegen_"))

    async def generate_project(self, description: str, user_id: int) -> Dict[str, Any]:
        """
        Generate project code from user description using DeepSeek.

        Args:
            description: User's project description
            user_id: Telegram user ID

        Returns:
            Dictionary containing project structure and generated files

        Raises:
            ValueError: If description is empty or invalid
            RuntimeError: If API call fails
        """
        if not description or not description.strip():
            raise ValueError("Project description cannot be empty")

        logger.info(f"Generating project for user {user_id}: {description[:50]}...")

        try:
            # Prepare the prompt for DeepSeek
            system_prompt = """You are an expert software developer. Generate a complete project structure based on the user's description.
            Return ONLY valid JSON with the following structure:
            {
                "project_name": "string",
                "description": "string",
                "files": [
                    {
                        "path": "relative/file/path",
                        "content": "file content as string",
                        "language": "programming language"
                    }
                ],
                "dependencies": ["list of dependencies"],
                "readme": "README content"
            }
            Ensure all code is production-ready, well-documented, and follows best practices."""

            user_prompt = f"Generate a complete project for: {description}"

            # Call DeepSeek API
            response = await self.openai_client.chat.completions.create(
                model=self.config.DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=8000,
                response_format={"type": "json_object"}
            )

            # Parse the response
            project_data = json.loads(response.choices[0].message.content)

            # Validate project data
            if not project_data.get("files"):
                raise ValueError("No files generated in the project")

            logger.info(f"Generated project '{project_data.get('project_name', 'unnamed')}' with {len(project_data['files'])} files")

            return project_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse DeepSeek response: {e}")
            raise RuntimeError("Failed to parse generated project structure")
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            raise RuntimeError(f"Failed to generate project: {str(e)}")

    async def create_project_files(self, project_data: Dict[str, Any], project_dir: Optional[Path] = None) -> Path:
        """
        Create project files on disk from generated project data.

        Args:
            project_data: Dictionary containing project structure
            project_dir: Optional custom directory path

        Returns:
            Path to the created project directory

        Raises:
            OSError: If file creation fails
        """
        if project_dir is None:
            project_dir = self.temp_dir / project_data.get("project_name", "generated_project")

        project_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Creating project files in {project_dir}")

        # Create README
        readme_content = project_data.get("readme", f"# {project_data.get('project_name', 'Generated Project')}\n\n{project_data.get('description', '')}")
        readme_path = project_dir / "README.md"
        async with aiofiles.open(readme_path, "w", encoding="utf-8") as f:
            await f.write(readme_content)

        # Create all project files
        for file_info in project_data["files"]:
            file_path = project_dir / file_info["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(file_info["content"])

            logger.debug(f"Created file: {file_path}")

        # Create requirements.txt if dependencies exist
        dependencies = project_data.get("dependencies", [])
        if dependencies:
            req_path = project_dir / "requirements.txt"
            async with aiofiles.open(req_path, "w", encoding="utf-8") as f:
                await f.write("\n".join(dependencies))

        logger.info(f"Successfully created {len(project_data['files'])} files in {project_dir}")
        return project_dir

    async def push_to_github(self, project_dir: Path, repo_name: str, description: str = "") -> str:
        """
        Push project files to a new GitHub repository.

        Args:
            project_dir: Path to the project directory
            repo_name: Name for the GitHub repository
            description: Repository description

        Returns:
            URL of the created repository

        Raises:
            GithubException: If GitHub API operations fail
            ValueError: If repository name is invalid
        """
        if not repo_name or not repo_name.strip():
            raise ValueError("Repository name cannot be empty")

        logger.info(f"Pushing project to GitHub as '{repo_name}'")

        try:
            # Get authenticated user
            user = self.github_client.get_user()

            # Create repository
            repo: Repository = user.create_repo(
                name=repo_name,
                description=description or f"Generated project: {repo_name}",
                private=False,
                auto_init=False
            )

            logger.info(f"Created repository: {repo.html_url}")

            # Initialize git repository
            import git
            repo_dir = git.Repo.init(project_dir)

            # Configure git user
            repo_dir.config_writer().set_value("user", "name", self.config.GIT_USER_NAME).release()
            repo_dir.config_writer().set_value("user", "email", self.config.GIT_USER_EMAIL).release()

            # Add all files
            repo_dir.index.add("*")

            # Create initial commit
            repo_dir.index.commit("Initial commit: Generated project")

            # Add remote and push
            remote = repo_dir.create_remote("origin", repo.clone_url)
            remote.push(refspec="master:master")

            logger.info(f"Successfully pushed to {repo.html_url}")
            return repo.html_url

        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            if e.status == 422:
                raise ValueError(f"Repository '{repo_name}' already exists or name is invalid")
            raise RuntimeError(f"Failed to push to GitHub: {str(e)}")
        except Exception as e:
            logger.error(f"Git push error: {e}")
            raise RuntimeError(f"Failed to push to GitHub: {str(e)}")

    async def handle_generation_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle user request for project generation.

        Args:
            update: Telegram update object
            context: Callback context
        """
        user_id = update.effective_user.id
        message = update.message

        try:
            # Get project description from message
            if message.document:
                # Handle file upload with description
                description = message.caption or "Generate a project from this file"
                file_content = await self._download_file(message.document)
                description = f"{description}\n\nAdditional context from file:\n{file_content[:1000]}"
            else:
                description = message.text

            # Send processing message
            processing_msg = await message.reply_text("🔄 Generating your project... This may take a moment.")

            # Generate project
            project_data = await self.generate_project(description, user_id)

            # Create project files
            project_dir = await self.create_project_files(project_data)

            # Push to GitHub
            repo_name = project_data.get("project_name", f"project_{user_id}_{message.message_id}").replace(" ", "_").lower()
            repo_url = await self.push_to_github(project_dir, repo_name, project_data.get("description", ""))

            # Store project metadata in database
            await self.db.add_project(
                user_id=user_id,
                project_name=repo_name,
                repo_url=repo_url,
                description=project_data.get("description", ""),
                file_count=len(project_data["files"])
            )

            # Send success message
            await processing_msg.edit_text(
                f"✅ Project generated successfully!\n\n"
                f"📁 **{repo_name}**\n"
                f"📄 {len(project_data['files'])} files created\n"
                f"🔗 [View on GitHub]({repo_url})\n\n"
                f"Use /download to get the project files."
            )

            # Clean up temporary files
            await self._cleanup_temp(project_dir)

        except ValueError as e:
            await message.reply_text(f"❌ Invalid request: {str(e)}")
        except RuntimeError as e:
            logger.error(f"Generation failed for user {user_id}: {e}")
            await message.reply_text(f"❌ Generation failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in generation: {e}", exc_info=True)
            await message.reply_text("❌ An unexpected error occurred. Please try again later.")

    async def _download_file(self, document: Document) -> str:
        """
        Download a file from Telegram and read its content.

        Args:
            document: Telegram document object

        Returns:
            File content as string
        """
        file = await document.get_file()
        file_path = self.temp_dir / document.file_name

        await file.download_to_drive(file_path)
        async with aiofiles.open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = await f.read()

        # Clean up downloaded file
        await aiofiles.os.remove(file_path)
        return content

    async def _cleanup_temp(self, project_dir: Optional[Path] = None) -> None:
        """
        Clean up temporary files and directories.

        Args:
            project_dir: Optional specific directory to clean
        """
        try:
            if project_dir and project_dir.exists():
                shutil.rmtree(project_dir, ignore_errors=True)
                logger.debug(f"Cleaned up project directory: {project_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary files: {e}")

    async def cleanup(self) -> None:
        """Clean up all temporary resources."""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.info("Cleaned up all temporary files")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory: {e}")

    async def get_project_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Get project generation statistics for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Dictionary with user's project statistics
        """
        projects = await self.db.get_user_projects(user_id)
        return {
            "total_projects": len(projects),
            "projects": projects
        }

    async def validate_project_data(self, project_data: Dict[str, Any]) -> bool:
        """
        Validate generated project data structure.

        Args:
            project_data: Project data to validate

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["project_name", "files"]
        for field in required_fields:
            if field not in project_data:
                logger.error(f"Missing required field: {field}")
                return False

        if not isinstance(project_data["files"], list) or len(project_data["files"]) == 0:
            logger.error("Files must be a non-empty list")
            return False

        for file_info in project_data["files"]:
            if "path" not in file_info or "content" not in file_info:
                logger.error(f"File info missing required fields: {file_info}")
                return False

        return True


# Module-level function for easy integration
async def generate_and_push(description: str, user_id: int, config: Config, db: Database) -> str:
    """
    Convenience function to generate project and push to GitHub.

    Args:
        description: Project description
        user_id: Telegram user ID
        config: Application configuration
        db: Database instance

    Returns:
        GitHub repository URL
    """
    generator = CodeGenerator(config, db)
    try:
        project_data = await generator.generate_project(description, user_id)
        project_dir = await generator.create_project_files(project_data)
        repo_name = project_data.get("project_name", f"project_{user_id}").replace(" ", "_").lower()
        repo_url = await generator.push_to_github(project_dir, repo_name, project_data.get("description", ""))
        return repo_url
    finally:
        await generator.cleanup()