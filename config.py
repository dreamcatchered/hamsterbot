import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DEVELOPER = "@dreamcatch_r"

DATASET_PATH = BASE_DIR / "dataset.json"
DATABASE_DIR = BASE_DIR / "data"

WEB_HOST = "0.0.0.0"
WEB_PORT = 5002
WEB_DOMAIN = "hamster.dreampartners.online"

# Создаем директории
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
