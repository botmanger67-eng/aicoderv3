"""
bot_handlers.py - Handler registration and dispatch module.

This module registers all command and message handlers for the Telegram bot
and dispatches incoming updates to the appropriate feature modules.
"""

import logging
from typing import Callable, Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# Import feature modules
from features import (
    ai_chat,
    project_generator,
    file_handler,
    admin_controls,
    utils,
)

# Configure logging
logger = logging.getLogger(__name__)


class BotHandlers:
    """
    Manages registration and dispatching of all bot handlers.
    """

    def __init__(self, application: Application):
        """
        Initialize the handler manager.

        Args:
            application: The Telegram bot application instance.
        """
        self.application = application
        self._registered_handlers: Dict[str, Any] = {}
        self._feature_modules = {
            "ai_chat": ai_chat,
            "project_generator": project_generator,
            "file_handler": file_handler,
            "admin_controls": admin_controls,
            "utils": utils,
        }

    def register_all_handlers(self) -> None:
        """
        Register all command and message handlers with the application.
        """
        logger.info("Registering all bot handlers...")

        # Register command handlers
        self._register_command_handlers()

        # Register message handlers
        self._register_message_handlers()

        # Register callback query handlers
        self._register_callback_query_handlers()

        # Register error handler
        self._register_error_handler()

        logger.info("All handlers registered successfully.")

    def _register_command_handlers(self) -> None:
        """
        Register all command handlers from feature modules.
        """
        # Basic commands
        self._register_command("start", self._handle_start)
        self._register_command("help", self._handle_help)

        # AI Chat commands
        self._register_command("chat", ai_chat.handle_chat_command)
        self._register_command("clear", ai_chat.handle_clear_command)

        # Project generator commands
        self._register_command("generate", project_generator.handle_generate_command)
        self._register_command("push", project_generator.handle_push_command)

        # File handler commands
        self._register_command("files", file_handler.handle_files_command)
        self._register_command("upload", file_handler.handle_upload_command)

        # Admin commands
        self._register_command("admin", admin_controls.handle_admin_command)
        self._register_command("stats", admin_controls.handle_stats_command)
        self._register_command("broadcast", admin_controls.handle_broadcast_command)

        # Utility commands
        self._register_command("ping", utils.handle_ping_command)
        self._register_command("info", utils.handle_info_command)

    def _register_message_handlers(self) -> None:
        """
        Register all message handlers based on content type.
        """
        # Text messages (AI chat)
        self._register_message_handler(
            ai_chat.handle_text_message,
            filters.TEXT & ~filters.COMMAND,
            "text_handler",
        )

        # Document/File uploads
        self._register_message_handler(
            file_handler.handle_document_upload,
            filters.Document.ALL,
            "document_handler",
        )

        # Photo uploads
        self._register_message_handler(
            file_handler.handle_photo_upload,
            filters.PHOTO,
            "photo_handler",
        )

        # Voice messages
        self._register_message_handler(
            ai_chat.handle_voice_message,
            filters.VOICE,
            "voice_handler",
        )

        # Sticker messages
        self._register_message_handler(
            utils.handle_sticker_message,
            filters.Sticker.ALL,
            "sticker_handler",
        )

    def _register_callback_query_handlers(self) -> None:
        """
        Register all callback query handlers for inline keyboards.
        """
        # AI Chat callbacks
        self._register_callback_query_handler(
            ai_chat.handle_chat_callback,
            pattern="^chat_",
        )

        # Project generator callbacks
        self._register_callback_query_handler(
            project_generator.handle_project_callback,
            pattern="^project_",
        )

        # File handler callbacks
        self._register_callback_query_handler(
            file_handler.handle_file_callback,
            pattern="^file_",
        )

        # Admin callbacks
        self._register_callback_query_handler(
            admin_controls.handle_admin_callback,
            pattern="^admin_",
        )

        # Generic callback handler for unhandled patterns
        self._register_callback_query_handler(
            self._handle_unknown_callback,
            pattern=None,
        )

    def _register_error_handler(self) -> None:
        """
        Register the global error handler.
        """
        self.application.add_error_handler(self._handle_error)

    def _register_command(
        self,
        command: str,
        handler: Callable,
        filters: Optional[Any] = None,
    ) -> None:
        """
        Register a single command handler.

        Args:
            command: The command name (without '/').
            handler: The async handler function.
            filters: Optional filters for the command.
        """
        try:
            handler_obj = CommandHandler(command, handler, filters=filters)
            self.application.add_handler(handler_obj)
            self._registered_handlers[f"command_{command}"] = handler_obj
            logger.debug(f"Registered command handler: /{command}")
        except Exception as e:
            logger.error(f"Failed to register command /{command}: {e}")

    def _register_message_handler(
        self,
        handler: Callable,
        message_filter: Any,
        name: str,
    ) -> None:
        """
        Register a single message handler.

        Args:
            handler: The async handler function.
            message_filter: The message filter to apply.
            name: A descriptive name for the handler.
        """
        try:
            handler_obj = MessageHandler(message_filter, handler)
            self.application.add_handler(handler_obj)
            self._registered_handlers[f"message_{name}"] = handler_obj
            logger.debug(f"Registered message handler: {name}")
        except Exception as e:
            logger.error(f"Failed to register message handler {name}: {e}")

    def _register_callback_query_handler(
        self,
        handler: Callable,
        pattern: Optional[str] = None,
    ) -> None:
        """
        Register a single callback query handler.

        Args:
            handler: The async handler function.
            pattern: Optional regex pattern to match callback data.
        """
        try:
            handler_obj = CallbackQueryHandler(handler, pattern=pattern)
            self.application.add_handler(handler_obj)
            pattern_name = pattern if pattern else "default"
            self._registered_handlers[f"callback_{pattern_name}"] = handler_obj
            logger.debug(f"Registered callback handler: {pattern_name}")
        except Exception as e:
            logger.error(f"Failed to register callback handler: {e}")

    async def _handle_start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Handle the /start command.

        Args:
            update: The update object.
            context: The context object.
        """
        user = update.effective_user
        welcome_message = (
            f"👋 Hello {user.first_name}!\n\n"
            "I'm your personal all-in-one assistant bot. Here's what I can do:\n\n"
            "🤖 **AI Chat** - Chat with DeepSeek AI\n"
            "📁 **File Management** - Upload and manage files\n"
            "🚀 **Project Generator** - Generate and push projects to GitHub\n"
            "⚙️ **Admin Controls** - Manage bot settings\n\n"
            "Use /help to see all available commands."
        )

        # Create inline keyboard with quick actions
        keyboard = [
            [
                InlineKeyboardButton("🤖 Start Chat", callback_data="chat_start"),
                InlineKeyboardButton("📁 My Files", callback_data="file_list"),
            ],
            [
                InlineKeyboardButton("🚀 Generate Project", callback_data="project_new"),
                InlineKeyboardButton("❓ Help", callback_data="help_main"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    async def _handle_help(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Handle the /help command.

        Args:
            update: The update object.
            context: The context object.
        """
        help_text = (
            "📚 **Available Commands**\n\n"
            "**AI Chat**\n"
            "/chat <message> - Chat with AI\n"
            "/clear - Clear chat history\n\n"
            "**Project Generator**\n"
            "/generate - Create a new project\n"
            "/push - Push project to GitHub\n\n"
            "**File Management**\n"
            "/files - List your files\n"
            "/upload - Upload a file\n\n"
            "**Admin**\n"
            "/admin - Admin panel\n"
            "/stats - Bot statistics\n"
            "/broadcast - Send broadcast message\n\n"
            "**Utilities**\n"
            "/ping - Check bot status\n"
            "/info - Get user info\n\n"
            "Just send me a message to start chatting!"
        )

        await update.message.reply_text(
            help_text,
            parse_mode="Markdown",
        )

    async def _handle_unknown_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Handle unknown callback queries.

        Args:
            update: The update object.
            context: The context object.
        """
        query = update.callback_query
        await query.answer("Unknown action. Please try again.")
        logger.warning(f"Unknown callback data: {query.data}")

    async def _handle_error(
        self,
        update: Optional[Update],
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """
        Handle errors that occur during update processing.

        Args:
            update: The update object (may be None).
            context: The context object containing error information.
        """
        error = context.error
        logger.error(f"Update {update} caused error {error}", exc_info=error)

        # Notify user if possible
        if update and update.effective_chat:
            try:
                await update.effective_chat.send_message(
                    "❌ An error occurred while processing your request. "
                    "Please try again later."
                )
            except Exception as e:
                logger.error(f"Failed to send error message: {e}")

    def get_registered_handlers(self) -> Dict[str, Any]:
        """
        Get all registered handlers.

        Returns:
            Dictionary of registered handlers.
        """
        return self._registered_handlers.copy()

    def unregister_handler(self, handler_name: str) -> bool:
        """
        Unregister a specific handler by name.

        Args:
            handler_name: The name of the handler to unregister.

        Returns:
            True if handler was unregistered, False otherwise.
        """
        if handler_name in self._registered_handlers:
            handler = self._registered_handlers.pop(handler_name)
            self.application.remove_handler(handler)
            logger.info(f"Unregistered handler: {handler_name}")
            return True
        logger.warning(f"Handler not found: {handler_name}")
        return False


def setup_handlers(application: Application) -> BotHandlers:
    """
    Setup and register all handlers for the bot application.

    Args:
        application: The Telegram bot application instance.

    Returns:
        The BotHandlers instance managing all handlers.
    """
    handler_manager = BotHandlers(application)
    handler_manager.register_all_handlers()
    return handler_manager