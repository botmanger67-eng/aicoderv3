"""
Main entry point for the Telegram bot.
Initializes the bot, registers handlers, and starts polling.
"""

import logging
import os
import sys
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
)

# Import handlers from other modules
from handlers import (
    start_command,
    help_command,
    ai_chat_handler,
    project_generator_handler,
    file_handler,
    admin_handlers,
    error_handler,
)
from config import Config
from database import Database

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def validate_config() -> bool:
    """
    Validate that all required configuration values are present.
    
    Returns:
        bool: True if configuration is valid, False otherwise.
    """
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "OPENAI_API_KEY",
        "GITHUB_TOKEN",
        "ADMIN_USER_IDS",
    ]
    
    missing_vars = []
    for var in required_vars:
        if not getattr(Config, var, None):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(
            "Missing required configuration variables: %s",
            ", ".join(missing_vars),
        )
        return False
    
    return True


async def post_init(application: Application) -> None:
    """
    Post-initialization callback to set up bot commands and database.
    
    Args:
        application: The Application instance.
    """
    try:
        # Initialize database
        db = Database()
        await db.initialize()
        logger.info("Database initialized successfully")
        
        # Set bot commands
        commands = [
            ("start", "Start the bot"),
            ("help", "Get help information"),
            ("chat", "Start AI chat session"),
            ("project", "Generate a new project"),
            ("admin", "Admin panel (admin only)"),
        ]
        
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands set successfully")
        
    except Exception as e:
        logger.error("Failed to initialize bot: %s", str(e))
        raise


def main() -> None:
    """
    Main function to start the bot.
    """
    # Validate configuration
    if not validate_config():
        logger.error("Invalid configuration. Exiting.")
        sys.exit(1)
    
    try:
        # Create the Application
        application = Application.builder() \
            .token(Config.TELEGRAM_BOT_TOKEN) \
            .post_init(post_init) \
            .concurrent_updates(True) \
            .build()
        
        # Register command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        
        # Register conversation handlers
        application.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("chat", ai_chat_handler.start_chat)],
                states={
                    "CHATTING": [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            ai_chat_handler.handle_message,
                        ),
                        CommandHandler("end", ai_chat_handler.end_chat),
                    ],
                },
                fallbacks=[CommandHandler("cancel", ai_chat_handler.cancel_chat)],
            )
        )
        
        application.add_handler(
            ConversationHandler(
                entry_points=[CommandHandler("project", project_generator_handler.start_project)],
                states={
                    "PROJECT_NAME": [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            project_generator_handler.get_project_name,
                        ),
                    ],
                    "PROJECT_TYPE": [
                        CallbackQueryHandler(
                            project_generator_handler.get_project_type,
                            pattern="^(python|javascript|typescript|go|rust)$",
                        ),
                    ],
                    "PROJECT_DESCRIPTION": [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND,
                            project_generator_handler.get_project_description,
                        ),
                    ],
                    "CONFIRMATION": [
                        CallbackQueryHandler(
                            project_generator_handler.confirm_project,
                            pattern="^(confirm|cancel)$",
                        ),
                    ],
                },
                fallbacks=[CommandHandler("cancel", project_generator_handler.cancel_project)],
            )
        )
        
        # Register file handler
        application.add_handler(
            MessageHandler(
                filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
                file_handler.handle_file,
            )
        )
        
        # Register admin handlers
        application.add_handler(
            CommandHandler("admin", admin_handlers.admin_panel)
        )
        application.add_handler(
            CallbackQueryHandler(
                admin_handlers.handle_admin_callback,
                pattern="^admin_",
            )
        )
        
        # Register error handler
        application.add_error_handler(error_handler)
        
        # Start the bot
        logger.info("Starting bot...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        
    except Exception as e:
        logger.error("Failed to start bot: %s", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()