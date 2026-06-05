# src/telegram_bot/bot.py
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.core.config import Config
from src.core.database import ExpenseDB
from src.telegram_bot import handlers

logger = logging.getLogger(__name__)


def create_app() -> Application:
    """Initialize resources, validate configuration, and register command handlers."""
    # Ensure variables are present
    Config.validate()

    # Setup database helper
    db = ExpenseDB(Config.DB_PATH)

    # Initialize application
    app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

    # Store database in bot_data dictionary for dependency injection
    app.bot_data["db"] = db

    # Register Command handlers
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_command))

    # Category Management
    app.add_handler(CommandHandler("categories", handlers.list_categories))
    app.add_handler(CommandHandler("addcategory", handlers.add_category))
    app.add_handler(CommandHandler("delcategory", handlers.del_category))

    # Account Management
    app.add_handler(CommandHandler("accounts", handlers.list_accounts))
    app.add_handler(CommandHandler("addaccount", handlers.add_account))
    app.add_handler(CommandHandler("delaccount", handlers.del_account))
    app.add_handler(CommandHandler("transfer", handlers.transfer_command))

    # Reporting & History
    app.add_handler(CommandHandler("report", handlers.report_command))
    app.add_handler(CommandHandler("history", handlers.history_command))
    app.add_handler(CommandHandler("delete", handlers.delete_command))
    app.add_handler(CommandHandler("undo", handlers.undo_command))
    app.add_handler(CommandHandler("export", handlers.export_command))

    # Fallback to handle unregistered slash commands
    app.add_handler(MessageHandler(filters.COMMAND, handlers.handle_unknown_command))

    # Text message handler (logs transactions)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND, handlers.handle_transaction_message
        )
    )

    logger.info("Bot application factory compiled successfully.")
    return app
