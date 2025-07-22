import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# GigaChat API Credentials
CLIENT_ID = os.getenv("CLIENT_ID")
SECRET = os.getenv("SECRET")

# Logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Default importance threshold
DEFAULT_IMPORTANCE_THRESHOLD = 0.7

# Validation
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set")

if not CLIENT_ID or not SECRET:
    raise ValueError("CLIENT_ID and SECRET environment variables must be set") 