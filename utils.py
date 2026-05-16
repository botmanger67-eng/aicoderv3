import logging
import time
import asyncio
from typing import Dict, Tuple, Optional, Callable, Any
from functools import wraps
from datetime import datetime, timedelta
import os

# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 30  # max requests per window

# Admin user IDs (should be loaded from environment or config)
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else set()

# In-memory rate limit store: user_id -> list of timestamps
_rate_limit_store: Dict[int, list] = {}

# Logger instance
logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, logs to console only.
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Create formatter
    formatter = logging.Formatter(log_format, date_format)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            logger.error(f"Failed to set up file logging: {e}")
    
    logger.info(f"Logging configured with level: {log_level}")


def is_admin(user_id: int) -> bool:
    """
    Check if a user is an admin.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        True if user is an admin, False otherwise
    """
    return user_id in ADMIN_IDS


def require_admin(func: Callable) -> Callable:
    """
    Decorator to restrict command access to admin users only.
    
    Args:
        func: The async function to wrap
        
    Returns:
        Wrapped function that checks admin status
    """
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id if update.effective_user else None
        if user_id is None:
            await update.message.reply_text("❌ Could not identify user.")
            return
        
        if not is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            logger.warning(f"Unauthorized admin command attempt by user {user_id}")
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper


def rate_limit(max_requests: int = RATE_LIMIT_MAX_REQUESTS, 
               window: int = RATE_LIMIT_WINDOW) -> Callable:
    """
    Decorator to apply rate limiting to a function.
    
    Args:
        max_requests: Maximum number of requests allowed in the time window
        window: Time window in seconds
        
    Returns:
        Decorated function with rate limiting
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id if update.effective_user else None
            if user_id is None:
                await update.message.reply_text("❌ Could not identify user.")
                return
            
            # Clean old entries
            now = time.time()
            if user_id in _rate_limit_store:
                _rate_limit_store[user_id] = [
                    t for t in _rate_limit_store[user_id] 
                    if now - t < window
                ]
            else:
                _rate_limit_store[user_id] = []
            
            # Check rate limit
            if len(_rate_limit_store[user_id]) >= max_requests:
                retry_after = int(window - (now - _rate_limit_store[user_id][0]))
                await update.message.reply_text(
                    f"⏳ Rate limit exceeded. Please try again in {retry_after} seconds."
                )
                logger.warning(f"Rate limit hit for user {user_id}")
                return
            
            # Add current request timestamp
            _rate_limit_store[user_id].append(now)
            
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator


def format_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"


def format_duration(seconds: int) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2h 30m 15s")
    """
    if seconds < 0:
        return "0s"
    
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")
    
    return " ".join(parts)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing or replacing unsafe characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Replace unsafe characters
    unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    
    # Ensure filename is not empty
    if not filename:
        filename = "unnamed_file"
    
    return filename


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with optional suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length of the result
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def parse_command_args(text: str) -> Tuple[str, str]:
    """
    Parse command arguments from text.
    
    Args:
        text: Full command text (e.g., "/command arg1 arg2")
        
    Returns:
        Tuple of (command, args_string)
    """
    if not text:
        return ("", "")
    
    parts = text.split(maxsplit=1)
    command = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""
    
    return (command, args)


def escape_markdown(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for MarkdownV2
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def create_error_message(error: Exception, context: str = "") -> str:
    """
    Create a user-friendly error message from an exception.
    
    Args:
        error: The exception that occurred
        context: Optional context about where the error occurred
        
    Returns:
        Formatted error message
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    message_parts = ["❌ An error occurred"]
    if context:
        message_parts.append(f" while {context}")
    message_parts.append(":")
    message_parts.append(f"\n\n`{error_type}: {error_msg}`")
    
    return "".join(message_parts)


def get_timestamp() -> str:
    """
    Get current timestamp in ISO format.
    
    Returns:
        Current timestamp string
    """
    return datetime.now().isoformat()


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """
    Check if a file has an allowed extension.
    
    Args:
        filename: Name of the file to check
        allowed_extensions: Set of allowed extensions (e.g., {'.txt', '.pdf'})
        
    Returns:
        True if extension is allowed, False otherwise
    """
    _, ext = os.path.splitext(filename.lower())
    return ext in allowed_extensions


def chunk_list(lst: list, chunk_size: int) -> list:
    """
    Split a list into chunks of specified size.
    
    Args:
        lst: List to split
        chunk_size: Maximum size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


async def retry_async(func: Callable, max_retries: int = 3, 
                      delay: float = 1.0, backoff: float = 2.0,
                      exceptions: tuple = (Exception,)) -> Any:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
        
    Returns:
        Result of the function
        
    Raises:
        The last exception if all retries fail
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(f"Retry {attempt + 1}/{max_retries} failed: {e}")
                await asyncio.sleep(current_delay)
                current_delay *= backoff
    
    raise last_exception


def clean_old_rate_limit_entries() -> None:
    """
    Clean expired entries from the rate limit store.
    Should be called periodically.
    """
    now = time.time()
    expired_users = []
    
    for user_id, timestamps in _rate_limit_store.items():
        valid_timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
        if valid_timestamps:
            _rate_limit_store[user_id] = valid_timestamps
        else:
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del _rate_limit_store[user_id]