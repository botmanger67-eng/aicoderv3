"""
AI Chat module for Telegram bot.
Handles /chat command and AI conversation with DeepSeek via OpenAI-compatible API.
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

from telegram import Update, Message
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from config import Config
from database import Database
from utils import is_admin, rate_limit, log_command

logger = logging.getLogger(__name__)

# Initialize OpenAI client for DeepSeek
client = AsyncOpenAI(
    api_key=Config.DEEPSEEK_API_KEY,
    base_url=Config.DEEPSEEK_BASE_URL
)

# Conversation history storage (in-memory cache with database fallback)
conversation_cache: Dict[int, List[Dict[str, Any]]] = {}

# System prompt for AI assistant
SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are a helpful AI assistant integrated into a Telegram bot. "
        "You can help with various tasks including coding, writing, analysis, "
        "and general conversation. Be concise, accurate, and friendly. "
        "When providing code, use proper formatting. "
        "Current date: " + datetime.now().strftime("%Y-%m-%d")
    )
}

# Maximum conversation history length
MAX_HISTORY_LENGTH = 50

# Maximum message length for Telegram
MAX_TELEGRAM_MESSAGE_LENGTH = 4096


async def get_conversation_history(user_id: int, db: Database) -> List[Dict[str, Any]]:
    """
    Retrieve conversation history for a user.
    First checks in-memory cache, then falls back to database.
    
    Args:
        user_id: Telegram user ID
        db: Database instance
        
    Returns:
        List of conversation messages
    """
    if user_id in conversation_cache:
        return conversation_cache[user_id]
    
    # Try to load from database
    try:
        history = await db.get_conversation_history(user_id)
        if history:
            conversation_cache[user_id] = history
            return history
    except Exception as e:
        logger.error(f"Error loading conversation history for user {user_id}: {e}")
    
    # Initialize new conversation
    conversation_cache[user_id] = [SYSTEM_PROMPT.copy()]
    return conversation_cache[user_id]


async def save_conversation_history(user_id: int, history: List[Dict[str, Any]], db: Database) -> None:
    """
    Save conversation history to database.
    
    Args:
        user_id: Telegram user ID
        history: List of conversation messages
        db: Database instance
    """
    try:
        await db.save_conversation_history(user_id, history)
    except Exception as e:
        logger.error(f"Error saving conversation history for user {user_id}: {e}")


async def trim_conversation_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Trim conversation history to maximum length while preserving system prompt.
    
    Args:
        history: Full conversation history
        
    Returns:
        Trimmed conversation history
    """
    if len(history) <= MAX_HISTORY_LENGTH:
        return history
    
    # Keep system prompt and last N messages
    system_prompt = history[0] if history and history[0]["role"] == "system" else SYSTEM_PROMPT.copy()
    recent_messages = history[-(MAX_HISTORY_LENGTH - 1):]
    
    return [system_prompt] + recent_messages


async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /chat command - start or continue AI conversation.
    
    Args:
        update: Telegram update object
        context: Callback context
    """
    user_id = update.effective_user.id
    message = update.message
    db: Database = context.bot_data.get("db")
    
    if not db:
        await message.reply_text("❌ Database not available. Please try again later.")
        return
    
    # Check if user is admin (optional restriction)
    if Config.RESTRICT_CHAT_TO_ADMINS and not await is_admin(user_id, db):
        await message.reply_text("❌ This command is restricted to administrators.")
        return
    
    # Get the user's message
    user_text = message.text.replace("/chat", "", 1).strip()
    
    if not user_text:
        await message.reply_text(
            "💬 *AI Chat*\n\n"
            "Send me a message and I'll respond using DeepSeek AI.\n\n"
            "Commands:\n"
            "/chat <message> - Start or continue conversation\n"
            "/reset - Clear conversation history\n"
            "/history - View conversation history\n\n"
            "Example: `/chat What is Python?`",
            parse_mode="Markdown"
        )
        return
    
    # Send typing indicator
    await message.chat.send_action(action="typing")
    
    try:
        # Get conversation history
        history = await get_conversation_history(user_id, db)
        
        # Add user message to history
        user_message = {"role": "user", "content": user_text}
        history.append(user_message)
        
        # Trim history if needed
        history = await trim_conversation_history(history)
        
        # Call DeepSeek API
        response = await client.chat.completions.create(
            model=Config.DEEPSEEK_MODEL,
            messages=history,
            temperature=Config.AI_TEMPERATURE,
            max_tokens=Config.AI_MAX_TOKENS,
            top_p=Config.AI_TOP_P,
            frequency_penalty=Config.AI_FREQUENCY_PENALTY,
            presence_penalty=Config.AI_PRESENCE_PENALTY
        )
        
        # Extract assistant response
        assistant_message = response.choices[0].message
        
        # Add assistant response to history
        history.append({
            "role": "assistant",
            "content": assistant_message.content
        })
        
        # Save updated history
        conversation_cache[user_id] = history
        await save_conversation_history(user_id, history, db)
        
        # Send response (split if too long)
        response_text = assistant_message.content
        if len(response_text) > MAX_TELEGRAM_MESSAGE_LENGTH:
            # Split into multiple messages
            parts = []
            current_part = ""
            
            for line in response_text.split("\n"):
                if len(current_part) + len(line) + 1 > MAX_TELEGRAM_MESSAGE_LENGTH:
                    parts.append(current_part)
                    current_part = line
                else:
                    current_part += "\n" + line if current_part else line
            
            if current_part:
                parts.append(current_part)
            
            for i, part in enumerate(parts):
                if i == 0:
                    await message.reply_text(part)
                else:
                    await message.reply_text(f"*Continued...*\n\n{part}", parse_mode="Markdown")
        else:
            await message.reply_text(response_text)
        
        # Log command usage
        await log_command(update, "chat", db)
        
    except Exception as e:
        logger.error(f"Error in chat command for user {user_id}: {e}")
        error_message = str(e)
        
        if "rate_limit" in error_message.lower():
            await message.reply_text("⏳ Too many requests. Please wait a moment and try again.")
        elif "authentication" in error_message.lower():
            await message.reply_text("❌ API authentication error. Please contact the administrator.")
        elif "timeout" in error_message.lower():
            await message.reply_text("⏰ Request timed out. Please try again.")
        else:
            await message.reply_text(f"❌ An error occurred: {error_message[:200]}")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /reset command - clear conversation history.
    
    Args:
        update: Telegram update object
        context: Callback context
    """
    user_id = update.effective_user.id
    message = update.message
    db: Database = context.bot_data.get("db")
    
    if not db:
        await message.reply_text("❌ Database not available. Please try again later.")
        return
    
    try:
        # Clear in-memory cache
        if user_id in conversation_cache:
            del conversation_cache[user_id]
        
        # Clear database history
        await db.clear_conversation_history(user_id)
        
        await message.reply_text("✅ Conversation history has been cleared. Starting fresh!")
        await log_command(update, "reset", db)
        
    except Exception as e:
        logger.error(f"Error resetting conversation for user {user_id}: {e}")
        await message.reply_text("❌ Failed to reset conversation history.")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /history command - view conversation history.
    
    Args:
        update: Telegram update object
        context: Callback context
    """
    user_id = update.effective_user.id
    message = update.message
    db: Database = context.bot_data.get("db")
    
    if not db:
        await message.reply_text("❌ Database not available. Please try again later.")
        return
    
    try:
        history = await get_conversation_history(user_id, db)
        
        if len(history) <= 1:  # Only system prompt
            await message.reply_text("📝 No conversation history yet. Start chatting with /chat!")
            return
        
        # Format history for display
        history_text = "📝 *Conversation History*\n\n"
        message_count = 0
        
        for msg in history:
            if msg["role"] == "system":
                continue
            
            role_emoji = "👤" if msg["role"] == "user" else "🤖"
            content = msg["content"][:200]  # Truncate long messages
            
            if len(msg["content"]) > 200:
                content += "..."
            
            history_text += f"{role_emoji} *{msg['role'].title()}*: {content}\n\n"
            message_count += 1
            
            # Split if too long
            if len(history_text) > MAX_TELEGRAM_MESSAGE_LENGTH - 500:
                history_text += f"... and {len(history) - message_count - 1} more messages"
                break
        
        history_text += f"\n*Total messages:* {message_count}"
        
        await message.reply_text(history_text, parse_mode="Markdown")
        await log_command(update, "history", db)
        
    except Exception as e:
        logger.error(f"Error getting history for user {user_id}: {e}")
        await message.reply_text("❌ Failed to retrieve conversation history.")


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle regular text messages in chat mode.
    Only responds if user has an active conversation.
    
    Args:
        update: Telegram update object
        context: Callback context
    """
    user_id = update.effective_user.id
    message = update.message
    
    # Check if user has an active conversation
    if user_id not in conversation_cache:
        return
    
    # Check if message is a command (should be handled elsewhere)
    if message.text and message.text.startswith("/"):
        return
    
    # Process as chat message
    await chat_command(update, context)


def get_handlers() -> List[Any]:
    """
    Get all handlers for this module.
    
    Returns:
        List of handler objects
    """
    return [
        CommandHandler("chat", chat_command),
        CommandHandler("reset", reset_command),
        CommandHandler("history", history_command),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message)
    ]


async def cleanup_inactive_conversations() -> None:
    """
    Clean up inactive conversations from cache.
    Should be called periodically.
    """
    # This is a placeholder for future implementation
    # Could remove conversations older than X hours
    pass