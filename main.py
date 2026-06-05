# main.py
import logging
from src.telegram_bot.bot import create_app

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Boot the bot using the application factory."""
    try:
        app = create_app()
        logger.info("Starting ExpenseGram bot via polling...")
        app.run_polling()
    except Exception as e:
        logger.critical(f"Failed to start the bot: {e}", exc_info=True)


if __name__ == "__main__":
    main()
