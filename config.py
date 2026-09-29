import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "data/nuthh.db"
)

DOWNLOAD_DIR = os.getenv(
    "DOWNLOAD_DIR",
    "downloads"
)

MAX_FILE_SIZE_MB = int(
    os.getenv("MAX_FILE_SIZE_MB", "49")
)

KEY_LENGTH = int(
    os.getenv("KEY_LENGTH", "16")
)
