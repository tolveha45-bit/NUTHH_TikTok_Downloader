import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

admin_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = set()

if admin_raw:
    for x in admin_raw.split(","):
        clean_id = x.strip()
        if clean_id.isdigit():
            ADMIN_IDS.add(int(clean_id))

print(f"DEBUG: Loaded ADMIN_IDS = {ADMIN_IDS}")

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
