"""
Admin module for Telegram bot.
Provides admin-only commands: broadcast, stats, users, ban, unban, shell, files, logs.
"""

import asyncio
import io
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import aiofiles
import aiosqlite
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import ADMIN_IDS, DATABASE_PATH, LOG_FILE_PATH
from database import DatabaseManager
from utils import is_admin, log_command

logger = logging.getLogger(__name__)

# Conversation states for broadcast
BROADCAST_TEXT, BROADCAST_CONFIRM = range(2)

# Conversation states for shell
SHELL_COMMAND, SHELL_CONFIRM = range(2, 4)


class AdminCommands:
    """Handles all admin-only commands."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.bot_start_time = time.time()

    def get_handlers(self) -> List:
        """Return list of handlers for admin commands."""
        return [
            CommandHandler("broadcast", self.broadcast_start, filters=filters.User(ADMIN_IDS)),
            CommandHandler("stats", self.stats, filters=filters.User(ADMIN_IDS)),
            CommandHandler("users", self.users, filters=filters.User(ADMIN_IDS)),
            CommandHandler("ban", self.ban_user, filters=filters.User(ADMIN_IDS)),
            CommandHandler("unban", self.unban_user, filters=filters.User(ADMIN_IDS)),
            CommandHandler("shell", self.shell_start, filters=filters.User(ADMIN_IDS)),
            CommandHandler("files", self.files, filters=filters.User(ADMIN_IDS)),
            CommandHandler("logs", self.logs, filters=filters.User(ADMIN_IDS)),
            CallbackQueryHandler(self.broadcast_confirm, pattern="^broadcast_confirm$"),
            CallbackQueryHandler(self.broadcast_cancel, pattern="^broadcast_cancel$"),
            CallbackQueryHandler(self.shell_confirm, pattern="^shell_confirm$"),
            CallbackQueryHandler(self.shell_cancel, pattern="^shell_cancel$"),
            MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), self.handle_broadcast_text),
            MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), self.handle_shell_command),
        ]

    async def broadcast_start(self, update: Update, context: CallbackContext) -> int:
        """Start broadcast conversation - ask for message."""
        await update.message.reply_text(
            "📢 *Broadcast Mode*\n\n"
            "Send me the message you want to broadcast to all users.\n"
            "You can use Markdown formatting.\n\n"
            "Type /cancel to abort.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return BROADCAST_TEXT

    async def handle_broadcast_text(self, update: Update, context: CallbackContext) -> int:
        """Handle broadcast text input."""
        if update.message.text == "/cancel":
            await update.message.reply_text("Broadcast cancelled.")
            return ConversationHandler.END

        context.user_data["broadcast_text"] = update.message.text
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="broadcast_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📢 *Preview:*\n\n{update.message.text}\n\n"
            "Do you want to send this broadcast?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )
        return BROADCAST_CONFIRM

    async def broadcast_confirm(self, update: Update, context: CallbackContext) -> int:
        """Confirm and send broadcast."""
        query = update.callback_query
        await query.answer()

        broadcast_text = context.user_data.get("broadcast_text", "")
        if not broadcast_text:
            await query.edit_message_text("No broadcast text found. Please start again.")
            return ConversationHandler.END

        await query.edit_message_text("📤 Sending broadcast...")

        try:
            # Get all active users from database
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute("SELECT user_id FROM users WHERE banned = 0")
                users = await cursor.fetchall()

            sent_count = 0
            failed_count = 0
            total_users = len(users)

            for user_id_tuple in users:
                user_id = user_id_tuple[0]
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=broadcast_text,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    sent_count += 1
                except TelegramError as e:
                    logger.warning(f"Failed to send broadcast to {user_id}: {e}")
                    failed_count += 1
                # Small delay to avoid hitting rate limits
                await asyncio.sleep(0.05)

            await query.edit_message_text(
                f"✅ *Broadcast Complete*\n\n"
                f"Total users: {total_users}\n"
                f"✅ Sent: {sent_count}\n"
                f"❌ Failed: {failed_count}",
                parse_mode=ParseMode.MARKDOWN,
            )

            # Log the broadcast
            await log_command(
                update.effective_user.id,
                "broadcast",
                f"Sent to {sent_count}/{total_users} users",
            )

        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            await query.edit_message_text(f"❌ Broadcast failed: {str(e)}")

        return ConversationHandler.END

    async def broadcast_cancel(self, update: Update, context: CallbackContext) -> int:
        """Cancel broadcast."""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Broadcast cancelled.")
        return ConversationHandler.END

    async def stats(self, update: Update, context: CallbackContext) -> None:
        """Show bot statistics."""
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                # Total users
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                total_users = (await cursor.fetchone())[0]

                # Active users (last 24 hours)
                cutoff = datetime.now() - timedelta(hours=24)
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM users WHERE last_active > ?",
                    (cutoff.isoformat(),),
                )
                active_users = (await cursor.fetchone())[0]

                # Banned users
                cursor = await db.execute("SELECT COUNT(*) FROM users WHERE banned = 1")
                banned_users = (await cursor.fetchone())[0]

                # Total messages
                cursor = await db.execute("SELECT COUNT(*) FROM messages")
                total_messages = (await cursor.fetchone())[0]

                # Messages today
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM messages WHERE timestamp > ?",
                    (today_start.isoformat(),),
                )
                messages_today = (await cursor.fetchone())[0]

            # Bot uptime
            uptime_seconds = int(time.time() - self.bot_start_time)
            uptime_str = str(timedelta(seconds=uptime_seconds))

            stats_text = (
                f"📊 *Bot Statistics*\n\n"
                f"👥 *Users:*\n"
                f"Total: {total_users}\n"
                f"Active (24h): {active_users}\n"
                f"Banned: {banned_users}\n\n"
                f"💬 *Messages:*\n"
                f"Total: {total_messages}\n"
                f"Today: {messages_today}\n\n"
                f"⏱ *Uptime:* {uptime_str}"
            )

            await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

            # Log command
            await log_command(update.effective_user.id, "stats", "Viewed bot statistics")

        except Exception as e:
            logger.error(f"Stats error: {e}")
            await update.message.reply_text(f"❌ Error fetching stats: {str(e)}")

    async def users(self, update: Update, context: CallbackContext) -> None:
        """List all users with details."""
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute(
                    "SELECT user_id, username, first_name, last_name, banned, last_active "
                    "FROM users ORDER BY last_active DESC"
                )
                users = await cursor.fetchall()

            if not users:
                await update.message.reply_text("No users found in database.")
                return

            # Prepare user list (limit to first 50 to avoid message too long)
            user_list = []
            for user in users[:50]:
                user_id, username, first_name, last_name, banned, last_active = user
                status = "🚫 Banned" if banned else "✅ Active"
                name_parts = [p for p in [first_name, last_name] if p]
                name = " ".join(name_parts) if name_parts else "N/A"
                username_str = f"@{username}" if username else "No username"
                last_active_str = last_active[:19] if last_active else "Never"

                user_list.append(
                    f"• ID: `{user_id}`\n"
                    f"  Name: {name}\n"
                    f"  Username: {username_str}\n"
                    f"  Status: {status}\n"
                    f"  Last Active: {last_active_str}\n"
                )

            total_users = len(users)
            text = f"👥 *Users List* ({total_users} total)\n\n" + "\n".join(user_list)

            if len(users) > 50:
                text += f"\n\n*Showing first 50 of {total_users} users*"

            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

            # Log command
            await log_command(update.effective_user.id, "users", f"Listed {total_users} users")

        except Exception as e:
            logger.error(f"Users error: {e}")
            await update.message.reply_text(f"❌ Error fetching users: {str(e)}")

    async def ban_user(self, update: Update, context: CallbackContext) -> None:
        """Ban a user by user ID or username."""
        if not context.args:
            await update.message.reply_text(
                "Usage: /ban <user_id> [reason]\n"
                "Example: /ban 123456789 Spamming"
            )
            return

        target = context.args[0]
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "No reason provided"

        try:
            # Try to parse as user ID
            try:
                user_id = int(target)
            except ValueError:
                # Try to find by username
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    cursor = await db.execute(
                        "SELECT user_id FROM users WHERE username = ?",
                        (target.lstrip("@"),),
                    )
                    result = await cursor.fetchone()
                    if result:
                        user_id = result[0]
                    else:
                        await update.message.reply_text(
                            f"❌ User '{target}' not found in database."
                        )
                        return

            # Check if already banned
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute(
                    "SELECT banned FROM users WHERE user_id = ?", (user_id,)
                )
                result = await cursor.fetchone()

                if result and result[0] == 1:
                    await update.message.reply_text(
                        f"⚠️ User `{user_id}` is already banned.",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return

                # Ban the user
                await db.execute(
                    "UPDATE users SET banned = 1, ban_reason = ?, banned_at = ? WHERE user_id = ?",
                    (reason, datetime.now().isoformat(), user_id),
                )
                await db.commit()

            await update.message.reply_text(
                f"✅ *User Banned*\n\n"
                f"User ID: `{user_id}`\n"
                f"Reason: {reason}",
                parse_mode=ParseMode.MARKDOWN,
            )

            # Log command
            await log_command(
                update.effective_user.id,
                "ban",
                f"Banned user {user_id}: {reason}",
            )

        except Exception as e:
            logger.error(f"Ban error: {e}")
            await update.message.reply_text(f"❌ Error banning user: {str(e)}")

    async def unban_user(self, update: Update, context: CallbackContext) -> None:
        """Unban a user by user ID or username."""
        if not context.args:
            await update.message.reply_text(
                "Usage: /unban <user_id>\n"
                "Example: /unban 123456789"
            )
            return

        target = context.args[0]

        try:
            # Try to parse as user ID
            try:
                user_id = int(target)
            except ValueError:
                # Try to find by username
                async with aiosqlite.connect(DATABASE_PATH) as db:
                    cursor = await db.execute(
                        "SELECT user_id FROM users WHERE username = ?",
                        (target.lstrip("@"),),
                    )
                    result = await cursor.fetchone()
                    if result:
                        user_id = result[0]
                    else:
                        await update.message.reply_text(
                            f"❌ User '{target}' not found in database."
                        )
                        return

            # Check if already unbanned
            async with aiosqlite.connect(DATABASE_PATH) as db:
                cursor = await db.execute(
                    "SELECT banned FROM users WHERE user_id = ?", (user_id,)
                )
                result = await cursor.fetchone()

                if not result:
                    await update.message.reply_text(
                        f"❌ User `{user_id}` not found in database.",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return

                if result[0] == 0:
                    await update.message.reply_text(
                        f"⚠️ User `{user_id}` is not banned.",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return

                # Unban the user
                await db.execute(
                    "UPDATE users SET banned = 0, ban_reason = NULL, banned_at = NULL WHERE user_id = ?",
                    (user_id,),
                )
                await db.commit()

            await update.message.reply_text(
                f"✅ *User Unbanned*\n\n"
                f"User ID: `{user_id}`",
                parse_mode=ParseMode.MARKDOWN,
            )

            # Log command
            await log_command(
                update.effective_user.id,
                "unban",
                f"Unbanned user {user_id}",
            )

        except Exception as e:
            logger.error(f"Unban error: {e}")
            await update.message.reply_text(f"❌ Error unbanning user: {str(e)}")

    async def shell_start(self, update: Update, context: CallbackContext) -> int:
        """Start shell command conversation."""
        await update.message.reply_text(
            "💻 *Shell Command*\n\n"
            "Enter the shell command you want to execute.\n"
            "⚠️ *Warning:* This can be dangerous!\n\n"
            "Type /cancel to abort.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return SHELL_COMMAND

    async def handle_shell_command(self, update: Update, context: CallbackContext) -> int:
        """Handle shell command input."""
        if update.message.text == "/cancel":
            await update.message.reply_text("Shell command cancelled.")
            return ConversationHandler.END

        context.user_data["shell_command"] = update.message.text

        keyboard = [
            [
                InlineKeyboardButton("✅ Execute", callback_data="shell_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="shell_cancel"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"💻 *Command:*\n`{update.message.text}`\n\n"
            "Are you sure you want to execute this command?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
        )
        return SHELL_CONFIRM

    async def shell_confirm(self, update: Update, context: CallbackContext) -> int:
        """Execute shell command."""
        query = update.callback_query
        await query.answer()

        command = context.user_data.get("shell_command", "")
        if not command:
            await query.edit_message_text("No command found. Please start again.")
            return ConversationHandler.END

        await query.edit_message_text("⏳ Executing command...")

        try:
            # Execute command with timeout
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=30
                )
            except asyncio.TimeoutError:
                process.kill()
                await query.edit_message_text(
                    "❌ Command timed out after 30 seconds."
                )
                return ConversationHandler.END