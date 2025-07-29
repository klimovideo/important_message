import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# GigaChat API Credentials
CLIENT_ID = os.getenv("CLIENT_ID")
SECRET = os.getenv("SECRET")

# Userbot credentials (for fake account monitoring)
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")

# Logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Default importance threshold
DEFAULT_IMPORTANCE_THRESHOLD = 0.7

# Userbot enabled flag
USERBOT_ENABLED = os.getenv("USERBOT_ENABLED", "true").lower() == "true"

# Validation
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

if not CLIENT_ID or not SECRET:
    raise ValueError("CLIENT_ID and SECRET environment variables must be set")

# Userbot validation (optional)
if USERBOT_ENABLED and not all([TELEGRAM_API_ID, TELEGRAM_API_HASH]):
    print("⚠️  WARNING: TELEGRAM_API_ID and TELEGRAM_API_HASH are not set. Userbot functionality will be disabled.")
    print("   To enable userbot (fake account monitoring), set these variables in your .env file.") 