import math
import requests
from .config import OLLAMA_EMBED_URL, EMBED_MODEL


def embed_texts(texts):
    if isinstance(texts, str):
        texts = [texts]

    payload = {
        "model": EMBED_MODEL,
        "input": texts
    }

    response = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=300)
    response.raise_for_status()
    data = response.json()
    return data["embeddings"]


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)