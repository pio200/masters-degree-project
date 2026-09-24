import os
from pathlib import Path
from dotenv import load_dotenv

# Załaduj zmienne z .env
load_dotenv()

# ============ ŚCIEŻKI ============
BASE_DIR = Path(__file__).parent
PDF_DIR = BASE_DIR / "pdfs"
LOGS_DIR = BASE_DIR / "logs"

# Utwórz katalogi jeśli nie istnieją
PDF_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# ============ OPENAI ============
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY nie ustawiony w zmiennych środowiskowych!")

OPENAI_MODEL = "gpt-4o"
OPENAI_MAX_TOKENS = 4096 #16000

# ============ OPENSEARCH ============
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "127.0.0.1:5601")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "pio200")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "")
OPENSEARCH_INDEX = "pdf_chunks"
OPENSEARCH_USE_SSL = os.getenv("OPENSEARCH_USE_SSL", "True").lower() == "true"
OPENSEARCH_VERIFY_CERTS = os.getenv("OPENSEARCH_VERIFY_CERTS", "False").lower() == "true"

# ============ LOGGING ============
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ============ PROCESSING ============
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))  # Liczba stron przetwarzanych jednocześnie
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "120"))  # Timeout dla GPT-4o
