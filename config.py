"""
Configuration module for the Telegram bot.
Loads environment variables and provides configuration constants.
"""

import os
import sys
from typing import Optional
from dotenv import load_dotenv


# Load environment variables from .env file if it exists
load_dotenv()


def _get_env_var(name: str, required: bool = True, default: Optional[str] = None) -> str:
    """
    Get an environment variable with proper error handling.
    
    Args:
        name: The name of the environment variable
        required: Whether the variable is required (default: True)
        default: Default value if the variable is not found and not required
        
    Returns:
        The value of the environment variable
        
    Raises:
        SystemExit: If a required variable is missing
    """
    value = os.getenv(name)
    
    if value is None:
        if required:
            print(f"ERROR: Required environment variable '{name}' is not set.", file=sys.stderr)
            print("Please set it in your .env file or environment.", file=sys.stderr)
            sys.exit(1)
        return default
    
    return value


# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN: str = _get_env_var("TELEGRAM_BOT_TOKEN")
"""Telegram Bot API token obtained from @BotFather"""

# AI Configuration
DEEPSEEK_API_KEY: str = _get_env_var("DEEPSEEK_API_KEY")
"""API key for DeepSeek AI service"""

DEEPSEEK_MODEL: str = _get_env_var("DEEPSEEK_MODEL", default="deepseek-chat")
"""Model name for DeepSeek API (default: deepseek-chat)"""

DEEPSEEK_BASE_URL: str = _get_env_var("DEEPSEEK_BASE_URL", default="https://api.deepseek.com/v1")
"""Base URL for DeepSeek API (default: https://api.deepseek.com/v1)"""

# GitHub Configuration
GITHUB_TOKEN: str = _get_env_var("GITHUB_TOKEN")
"""GitHub personal access token for repository operations"""

GITHUB_USERNAME: str = _get_env_var("GITHUB_USERNAME")
"""GitHub username for repository creation"""

# Database Configuration
DATABASE_PATH: str = _get_env_var("DATABASE_PATH", default="bot_database.db")
"""Path to the SQLite database file (default: bot_database.db)"""

# Admin Configuration
ADMIN_USER_IDS: list[int] = []
"""List of Telegram user IDs with admin privileges"""

_admin_ids_str: str = _get_env_var("ADMIN_USER_IDS", default="")
if _admin_ids_str:
    try:
        ADMIN_USER_IDS = [int(id_.strip()) for id_ in _admin_ids_str.split(",") if id_.strip()]
    except ValueError:
        print("WARNING: Invalid ADMIN_USER_IDS format. Expected comma-separated integers.", file=sys.stderr)
        ADMIN_USER_IDS = []

# File Handling Configuration
MAX_FILE_SIZE_MB: int = int(_get_env_var("MAX_FILE_SIZE_MB", default="50"))
"""Maximum file size in MB that the bot can handle (default: 50 MB)"""

ALLOWED_FILE_EXTENSIONS: list[str] = []
"""List of allowed file extensions for upload"""

_allowed_extensions_str: str = _get_env_var("ALLOWED_FILE_EXTENSIONS", default=".txt,.pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.zip,.py,.js,.html,.css,.json,.xml,.csv")
if _allowed_extensions_str:
    ALLOWED_FILE_EXTENSIONS = [ext.strip().lower() for ext in _allowed_extensions_str.split(",") if ext.strip()]

# Bot Behavior Configuration
MAX_MESSAGE_LENGTH: int = int(_get_env_var("MAX_MESSAGE_LENGTH", default="4096"))
"""Maximum message length for Telegram messages (default: 4096)"""

AI_RESPONSE_TIMEOUT: int = int(_get_env_var("AI_RESPONSE_TIMEOUT", default="30"))
"""Timeout in seconds for AI API calls (default: 30 seconds)"""

MAX_HISTORY_LENGTH: int = int(_get_env_var("MAX_HISTORY_LENGTH", default="50"))
"""Maximum number of messages to keep in conversation history (default: 50)"""

# Logging Configuration
LOG_LEVEL: str = _get_env_var("LOG_LEVEL", default="INFO")
"""Logging level (default: INFO)"""

LOG_FILE: Optional[str] = _get_env_var("LOG_FILE", required=False, default=None)
"""Path to log file (optional, defaults to console logging)"""

# Application Configuration
BOT_NAME: str = _get_env_var("BOT_NAME", default="All-in-One Bot")
"""Display name for the bot (default: All-in-One Bot)"""

BOT_VERSION: str = _get_env_var("BOT_VERSION", default="1.0.0")
"""Version of the bot application (default: 1.0.0)"""

# Webhook Configuration (optional)
WEBHOOK_URL: Optional[str] = _get_env_var("WEBHOOK_URL", required=False, default=None)
"""Webhook URL for production deployment (optional)"""

WEBHOOK_PORT: int = int(_get_env_var("WEBHOOK_PORT", default="8443"))
"""Port for webhook server (default: 8443)"""

# Rate Limiting
RATE_LIMIT_MESSAGES: int = int(_get_env_var("RATE_LIMIT_MESSAGES", default="20"))
"""Maximum messages per minute per user (default: 20)"""

RATE_LIMIT_WINDOW: int = int(_get_env_var("RATE_LIMIT_WINDOW", default="60"))
"""Rate limit window in seconds (default: 60 seconds)"""


def validate_config() -> bool:
    """
    Validate that all required configuration values are properly set.
    
    Returns:
        True if configuration is valid, False otherwise
    """
    errors: list[str] = []
    
    # Check required tokens
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is missing or empty")
    
    if not DEEPSEEK_API_KEY:
        errors.append("DEEPSEEK_API_KEY is missing or empty")
    
    if not GITHUB_TOKEN:
        errors.append("GITHUB_TOKEN is missing or empty")
    
    if not GITHUB_USERNAME:
        errors.append("GITHUB_USERNAME is missing or empty")
    
    # Validate numeric values
    if MAX_FILE_SIZE_MB <= 0:
        errors.append("MAX_FILE_SIZE_MB must be a positive integer")
    
    if MAX_MESSAGE_LENGTH <= 0:
        errors.append("MAX_MESSAGE_LENGTH must be a positive integer")
    
    if AI_RESPONSE_TIMEOUT <= 0:
        errors.append("AI_RESPONSE_TIMEOUT must be a positive integer")
    
    if MAX_HISTORY_LENGTH <= 0:
        errors.append("MAX_HISTORY_LENGTH must be a positive integer")
    
    if RATE_LIMIT_MESSAGES <= 0:
        errors.append("RATE_LIMIT_MESSAGES must be a positive integer")
    
    if RATE_LIMIT_WINDOW <= 0:
        errors.append("RATE_LIMIT_WINDOW must be a positive integer")
    
    # Validate log level
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if LOG_LEVEL.upper() not in valid_log_levels:
        errors.append(f"LOG_LEVEL must be one of {valid_log_levels}")
    
    if errors:
        print("Configuration validation errors:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return False
    
    return True


# Validate configuration on import
if not validate_config():
    print("WARNING: Configuration validation failed. The bot may not function correctly.", file=sys.stderr)