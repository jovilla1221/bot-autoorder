import os
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "@reveuseress")
SAYABAYAR_API_KEY = os.getenv("SAYABAYAR_API_KEY", "")
SAYABAYAR_API_BASE = os.getenv("SAYABAYAR_API_BASE", "https://api.sayabayar.com/v1")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
