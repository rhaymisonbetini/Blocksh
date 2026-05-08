from pathlib import Path

APP_DIR         = Path.home() / ".blocksh"
DB_PATH         = APP_DIR / "history.db"
THEMES_DIR      = APP_DIR / "themes"
THEME_PREF_PATH = APP_DIR / "theme_pref.json"
SETTINGS_PATH   = APP_DIR / "settings.json"

APP_DIR.mkdir(exist_ok=True)
THEMES_DIR.mkdir(exist_ok=True)
