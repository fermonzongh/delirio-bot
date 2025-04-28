import os
from dotenv import load_dotenv

# Carga las variables desde el archivo .env
load_dotenv()

# Configuración del proveedor de IA
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

# Configuración LLM
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY","")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-7-sonnet-20250219")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "")

# Google Drive
PRODUCT_LIST_FILE_ID = os.getenv("PRODUCT_LIST_FILE_ID")
CATALOG_PDF_FILE_ID = os.getenv("CATALOG_PDF_FILE_ID")
CATALOG_PDF_LINK = f"https://drive.google.com/file/d/{CATALOG_PDF_FILE_ID}/view?usp=sharing"
SERVICE_ACCOUNT_FILE = "service-account-key.json"
PRODUCTS_CACHE_FILE = "data/products_cache.json"

# WhatsApp via Heyoo
HEYOO_TOKEN = os.getenv("HEYOO_TOKEN")
HEYOO_PHONE_ID = os.getenv("HEYOO_PHONE_ID")
OWNER_PHONE_NUMBER = os.getenv("OWNER_PHONE_NUMBER")

# Conversaciones
CONVERSATION_HISTORY_DIR = "data/conversation_histories"
TAKEOVER_FILE = "data/takeover_status.json"

APP_SECRET = os.getenv("APP_SECRET")  # Cambia esto por tu secreto real