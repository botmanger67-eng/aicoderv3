"""
GitHub Manager Module

This module handles GitHub repository creation and file operations using PyGithub.
It provides functionality to create repositories, push files, and manage GitHub
interactions for the Telegram bot.
"""

import os
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from pathlib import Path

from github import Github, GithubException
from github.Repository import Repository
from github.ContentFile import ContentFile

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class GitHubConfig:
    """Configuration for GitHub connection."""
    token: str
    username: Optional[str] = None
    default_branch: str = "main"


class GitHubManager:
    """
    Manages GitHub repository operations including creation and file pushes.
    
    This class provides methods to interact with GitHub repositories using
    PyGithub library. It handles authentication, repository management,
    and file operations with proper error handling.
    """
    
    def __init__(self, config: GitHubConfig):
        """
        Initialize the GitHub manager with configuration.
        
        Args:
            config: GitHubConfig object containing authentication and settings
            
        Raises:
            ValueError: If token is empty or invalid
        """
        if not config.token:
            raise ValueError("GitHub token is required")
        
        self.config = config
        self._github: Optional[Github] = None
        self._user = None
        
        # Initialize GitHub connection
        self._initialize_connection()
    
    def _initialize_connection(self) -> None:
        """
        Initialize the GitHub API connection.
        
        Raises:
            GithubException: If authentication fails
        """
        try:
            self._github = Github(self.config.token)
            self._user = self._github.get_user()
            logger.info(f"Successfully authenticated as {self._user.login}")
        except GithubException as e:
            logger.error(f"Failed to authenticate with GitHub: {e}")
            raise
    
    @property
    def github(self) -> Github:
        """Get the GitHub API instance."""
        if self._github is None:
            self._initialize_connection()
        return self._github
    
    @property
    def user(self):
        """Get the authenticated user."""
        if self._user is None:
            self._initialize_connection()
        return self._user
    
    def create_repository(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True,
        gitignore_template: Optional[str] = None,
        license_template: Optional[str] = None
    ) -> Repository:
        """
        Create a new GitHub repository.
        
        Args:
            name: Repository name
            description: Repository description
            private: Whether the repository should be private
            auto_init: Whether to initialize with a README
            gitignore_template: Gitignore template to use
            license_template: License template to use
            
        Returns:
            Repository object for the created repository
            
        Raises:
            GithubException: If repository creation fails
            ValueError: If repository name is invalid
        """
        if not name or not name.strip():
            raise ValueError("Repository name cannot be empty")
        
        try:
            logger.info(f"Creating repository: {name}")
            
            repo = self.user.create_repo(
                name=name.strip(),
                description=description,
                private=private,
                auto_init=auto_init,
                gitignore_template=gitignore_template,
                license_template=license_template
            )
            
            logger.info(f"Successfully created repository: {repo.full_name}")
            return repo
            
        except GithubException as e:
            logger.error(f"Failed to create repository {name}: {e}")
            raise
    
    def get_repository(self, repo_name: str) -> Repository:
        """
        Get an existing repository by name.
        
        Args:
            repo_name: Full repository name (e.g., 'username/repo') or just name
            
        Returns:
            Repository object
            
        Raises:
            GithubException: If repository not found or access denied
        """
        try:
            # If it's just a name, prepend the username
            if '/' not in repo_name:
                repo_name = f"{self.user.login}/{repo_name}"
            
            return self.user.get_repo(repo_name)
            
        except GithubException as e:
            logger.error(f"Failed to get repository {repo_name}: {e}")
            raise
    
    def push_file(
        self,
        repo: Repository,
        file_path: str,
        content: str,
        commit_message: str,
        branch: Optional[str] = None
    ) -> ContentFile:
        """
        Push a file to a repository.
        
        Args:
            repo: Repository object
            file_path: Path where the file will be created/updated
            content: File content as string
            commit_message: Commit message
            branch: Branch name (defaults to repository default branch)
            
        Returns:
            ContentFile object for the pushed file
            
        Raises:
            GithubException: If file push fails
            ValueError: If parameters are invalid
        """
        if not file_path:
            raise ValueError("File path cannot be empty")
        
        if not content:
            raise ValueError("File content cannot be empty")
        
        if not commit_message:
            raise ValueError("Commit message cannot be empty")
        
        branch = branch or self.config.default_branch
        
        try:
            logger.info(f"Pushing file {file_path} to {repo.full_name}/{branch}")
            
            # Check if file already exists
            try:
                existing_file = repo.get_contents(file_path, ref=branch)
                # Update existing file
                result = repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    sha=existing_file.sha,
                    branch=branch
                )
                logger.info(f"Updated existing file: {file_path}")
                return result['content']
                
            except GithubException as e:
                if e.status == 404:
                    # File doesn't exist, create new one
                    result = repo.create_file(
                        path=file_path,
                        message=commit_message,
                        content=content,
                        branch=branch
                    )
                    logger.info(f"Created new file: {file_path}")
                    return result['content']
                else:
                    raise
                    
        except GithubException as e:
            logger.error(f"Failed to push file {file_path}: {e}")
            raise
    
    def push_files(
        self,
        repo: Repository,
        files: Dict[str, str],
        commit_message: str,
        branch: Optional[str] = None
    ) -> List[ContentFile]:
        """
        Push multiple files to a repository.
        
        Args:
            repo: Repository object
            files: Dictionary mapping file paths to their content
            commit_message: Commit message for all files
            branch: Branch name (defaults to repository default branch)
            
        Returns:
            List of ContentFile objects for pushed files
            
        Raises:
            GithubException: If file push fails
        """
        results = []
        
        for file_path, content in files.items():
            try:
                result = self.push_file(
                    repo=repo,
                    file_path=file_path,
                    content=content,
                    commit_message=commit_message,
                    branch=branch
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to push {file_path}: {e}")
                raise
        
        return results
    
    def delete_file(
        self,
        repo: Repository,
        file_path: str,
        commit_message: str,
        branch: Optional[str] = None
    ) -> bool:
        """
        Delete a file from a repository.
        
        Args:
            repo: Repository object
            file_path: Path to the file to delete
            commit_message: Commit message
            branch: Branch name (defaults to repository default branch)
            
        Returns:
            True if deletion was successful
            
        Raises:
            GithubException: If file deletion fails
        """
        branch = branch or self.config.default_branch
        
        try:
            logger.info(f"Deleting file {file_path} from {repo.full_name}/{branch}")
            
            existing_file = repo.get_contents(file_path, ref=branch)
            repo.delete_file(
                path=file_path,
                message=commit_message,
                sha=existing_file.sha,
                branch=branch
            )
            
            logger.info(f"Successfully deleted file: {file_path}")
            return True
            
        except GithubException as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            raise
    
    def get_file_content(
        self,
        repo: Repository,
        file_path: str,
        branch: Optional[str] = None
    ) -> str:
        """
        Get the content of a file from a repository.
        
        Args:
            repo: Repository object
            file_path: Path to the file
            branch: Branch name (defaults to repository default branch)
            
        Returns:
            File content as string
            
        Raises:
            GithubException: If file retrieval fails
        """
        branch = branch or self.config.default_branch
        
        try:
            content_file = repo.get_contents(file_path, ref=branch)
            return content_file.decoded_content.decode('utf-8')
            
        except GithubException as e:
            logger.error(f"Failed to get file content {file_path}: {e}")
            raise
    
    def list_files(
        self,
        repo: Repository,
        path: str = "",
        branch: Optional[str] = None
    ) -> List[ContentFile]:
        """
        List files in a repository directory.
        
        Args:
            repo: Repository object
            path: Directory path (empty for root)
            branch: Branch name (defaults to repository default branch)
            
        Returns:
            List of ContentFile objects
            
        Raises:
            GithubException: If listing fails
        """
        branch = branch or self.config.default_branch
        
        try:
            contents = repo.get_contents(path, ref=branch)
            return contents if isinstance(contents, list) else [contents]
            
        except GithubException as e:
            logger.error(f"Failed to list files in {path}: {e}")
            raise
    
    def create_or_update_branch(
        self,
        repo: Repository,
        branch_name: str,
        source_branch: Optional[str] = None
    ) -> bool:
        """
        Create a new branch or ensure it exists.
        
        Args:
            repo: Repository object
            branch_name: Name of the branch to create
            source_branch: Source branch to create from (defaults to default branch)
            
        Returns:
            True if branch was created or already exists
            
        Raises:
            GithubException: If branch creation fails
        """
        source_branch = source_branch or self.config.default_branch
        
        try:
            # Check if branch already exists
            try:
                repo.get_branch(branch_name)
                logger.info(f"Branch {branch_name} already exists")
                return True
            except GithubException as e:
                if e.status != 404:
                    raise
            
            # Create new branch
            source = repo.get_branch(source_branch)
            repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=source.commit.sha
            )
            
            logger.info(f"Created branch {branch_name} from {source_branch}")
            return True
            
        except GithubException as e:
            logger.error(f"Failed to create branch {branch_name}: {e}")
            raise
    
    def delete_repository(self, repo_name: str) -> bool:
        """
        Delete a repository.
        
        Args:
            repo_name: Name of the repository to delete
            
        Returns:
            True if deletion was successful
            
        Raises:
            GithubException: If deletion fails
        """
        try:
            repo = self.get_repository(repo_name)
            repo.delete()
            logger.info(f"Successfully deleted repository: {repo_name}")
            return True
            
        except GithubException as e:
            logger.error(f"Failed to delete repository {repo_name}: {e}")
            raise
    
    def close(self) -> None:
        """Close the GitHub connection and clean up resources."""
        if self._github:
            self._github.close()
            self._github = None
            self._user = None
            logger.info("GitHub connection closed")


# Convenience function to create a GitHub manager from environment variables
def create_github_manager_from_env() -> GitHubManager:
    """
    Create a GitHubManager instance using environment variables.
    
    Required environment variables:
        GITHUB_TOKEN: GitHub personal access token
    
    Optional environment variables:
        GITHUB_USERNAME: GitHub username
        GITHUB_DEFAULT_BRANCH: Default branch name (default: main)
    
    Returns:
        Configured GitHubManager instance
        
    Raises:
        ValueError: If GITHUB_TOKEN is not set
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    
    config = GitHubConfig(
        token=token,
        username=os.getenv("GITHUB_USERNAME"),
        default_branch=os.getenv("GITHUB_DEFAULT_BRANCH", "main")
    )
    
    return GitHubManager(config)


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create manager from environment variables
        manager = create_github_manager_from_env()
        
        # Example: Create a repository
        repo = manager.create_repository(
            name="test-repo",
            description="A test repository created by GitHubManager",
            private=False
        )
        
        # Example: Push a file
        content = "# Test Repository\n\nThis is a test file."
        manager.push_file(
            repo=repo,
            file_path="README.md",
            content=content,
            commit_message="Initial commit with README"
        )
        
        # Example: Push multiple files
        files = {
            "src/main.py": "print('Hello, World!')",
            "src/utils.py": "def helper():\n    pass",
            "requirements.txt": "requests==2.28.0\n"
        }
        manager.push_files(
            repo=repo,
            files=files,
            commit_message="Add project files"
        )
        
        # Clean up
        manager.close()
        
    except Exception as e:
        logger.error(f"Error in example usage: {e}")
        raise