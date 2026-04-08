import json
import os
import uuid

from .config import CHUNK_SIZE, CHUNK_OVERLAP
from .embeddings import embed_texts, cosine_similarity

PAGES_PATH = os.path.join("data", "pages.json")
VECTORS_PATH = os.path.join("data", "vectors.json")


def ensure_data_files():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(PAGES_PATH):
        with open(PAGES_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

    if not os.path.exists(VECTORS_PATH):
        with open(VECTORS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)


def load_json(path):
    ensure_data_files()
    try:  
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            return []
        
        return json.loads(content)
    
    except (json.JSONDecodeError, OSError):
        return []


def save_json(path, data):
    ensure_data_files()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_len:
            break
        start = end - overlap

    return chunks

def page_exists(url):
    pages = load_json(PAGES_PATH)
    return any(page.get("url") == url for page in pages)


def save_page(url, title, full_text):
    ensure_data_files()

    if page_exists(url):
        return False

    pages = load_json(PAGES_PATH)
    vectors = load_json(VECTORS_PATH)

    page_id = str(uuid.uuid4())
    page_record = {
        "page_id": page_id,
        "url": url,
        "title": title,
        "text": full_text
    }
    pages.append(page_record)

    chunks = chunk_text(full_text)
    if not chunks:
        save_json(PAGES_PATH, pages)
        save_json(VECTORS_PATH, vectors)
        return True

    embeddings = embed_texts(chunks)

    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        vectors.append({
            "chunk_id": str(uuid.uuid4()),
            "page_id": page_id,
            "url": url,
            "title": title,
            "chunk_index": i,
            "text": chunk,
            "embedding": emb
        })

    save_json(PAGES_PATH, pages)
    save_json(VECTORS_PATH, vectors)
    return True


def search_memory(query, top_k=5):
    ensure_data_files()
    vectors = load_json(VECTORS_PATH)

    if not vectors:
        return []

    query_embedding = embed_texts(query)[0]

    scored = []
    for item in vectors:
        score = cosine_similarity(query_embedding, item["embedding"])
        scored.append({
            "score": score,
            "url": item["url"],
            "title": item["title"],
            "text": item["text"],
            "chunk_index": item["chunk_index"]
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]

def rank_chunks_for_query(query, text, top_k=3):
    chunks = chunk_text(text)
    if not chunks:
        return []

    query_embedding = embed_texts(query)[0]
    chunk_embeddings = embed_texts(chunks)

    scored = []
    for i, (chunk, emb) in enumerate(zip(chunks, chunk_embeddings)):
        score = cosine_similarity(query_embedding, emb)
        scored.append({
            "chunk_index": i,
            "text": chunk,
            "score": score
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]