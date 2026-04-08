import os

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"

MODEL = os.getenv("GEMMA_WEB_MODEL", "gemma4:26b")
EMBED_MODEL = os.getenv("GEMMA_WEB_EMBED_MODEL", "embeddinggemma")

SEARCH_MAX_RESULTS = 5
READ_TOP_N = 3
MAX_PAGE_CHARS = 4000

CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
TOP_K_MEMORY = 5

SHOW_DEBUG_STATUS = True