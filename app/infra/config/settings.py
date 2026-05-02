from pathlib import Path

APP_DIR = Path.home() / ".terminator"
DB_PATH = APP_DIR / "history.db"

# Ensure the app directory exists on first import
APP_DIR.mkdir(exist_ok=True)
