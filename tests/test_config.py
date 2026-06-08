# tests/test_config.py
from src.core.config import Config


def test_config_version():
    # Verify VERSION is loaded correctly as a string and has content
    assert isinstance(Config.VERSION, str)
    assert len(Config.VERSION) > 0
    # Also verify it conforms to semver (e.g. "0.1.0")
    parts = Config.VERSION.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
