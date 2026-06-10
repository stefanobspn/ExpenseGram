# src/core/config.py
import os
import tomllib
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


def _get_version() -> str:
    try:
        pyproject_path = (
            Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
        )
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
                return data.get("project", {}).get("version", "0.1.0")
    except Exception:
        pass
    return "0.1.0"


class Config:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_OWNER_ID: str = os.getenv("TELEGRAM_OWNER_ID", "")
    DB_PATH: str = os.getenv("DB_PATH", "expenses.db")
    VERSION: str = _get_version()

    @classmethod
    def validate(cls) -> None:
        """Validate critical configuration parameters."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is missing! Please configure it in your environment or .env file."
            )

        # Ensure the directory for DB_PATH exists
        db_dir = Path(cls.DB_PATH).parent
        if db_dir != Path(".") and not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
