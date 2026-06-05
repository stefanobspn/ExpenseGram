# src/telegram_bot/middleware.py
import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from src.core.config import Config

logger = logging.getLogger(__name__)

def owner_required(func):
    """Decorator to restrict handler execution to the authorized bot owner only."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return
            
        owner_id_str = Config.TELEGRAM_OWNER_ID
        user_id = update.effective_user.id
        
        # If owner ID is not set, allow only '/start' so they can see their ID
        if not owner_id_str:
            if update.message and update.message.text and update.message.text.startswith("/start"):
                return await func(update, context)
            else:
                if update.message:
                    await update.message.reply_text(
                        "🔒 Bot access is locked. Please set `TELEGRAM_OWNER_ID` in your `.env` file to authorize yourself.",
                        parse_mode="Markdown"
                    )
                return
                
        # Access control check
        if str(user_id) != owner_id_str.strip():
            logger.warning(f"Unauthorized access attempt by Telegram User ID: {user_id}")
            return
            
        return await func(update, context)
    return wrapper
