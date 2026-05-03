import os

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"

MODEL = os.getenv("GEMMA_WEB_MODEL", "gemma4:26b")
EMBED_MODEL = os.getenv("GEMMA_WEB_EMBED_MODEL", "embeddinggemma")

SEARCH_MAX_RESULTS = 5
READ_TOP_N = 3
MAX_PAGE_CHARS = 4000
FETCH_TIMEOUT_SECONDS = int(os.getenv("GEMMA_WEB_FETCH_TIMEOUT_SECONDS", "15"))
FETCH_MAX_BYTES = int(os.getenv("GEMMA_WEB_FETCH_MAX_BYTES", "1000000"))
RESEARCH_FETCH_TOP = int(os.getenv("GEMMA_WEB_RESEARCH_FETCH_TOP", "3"))
RESEARCH_CACHE_TTL_SECONDS = int(os.getenv("GEMMA_WEB_CACHE_TTL_SECONDS", "3600"))
RESEARCH_CACHE_DIR = os.getenv("GEMMA_WEB_CACHE_DIR", os.path.join("data", "cache"))
USER_AGENT = os.getenv(
    "GEMMA_WEB_USER_AGENT",
    "gemma-web-cli/0.1 local research tool (+https://ollama.com/)"
)

CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
TOP_K_MEMORY = 5

SHOW_DEBUG_STATUS = True
