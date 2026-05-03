from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from .config import FETCH_MAX_BYTES, FETCH_TIMEOUT_SECONDS, MAX_PAGE_CHARS, USER_AGENT

try:
    import trafilatura
except ImportError:  # pragma: no cover - exercised in minimal test envs
    trafilatura = None

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.2",
}


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def extract_text_with_trafilatura(html: str, url: str = "") -> str:
    if trafilatura is None:
        return ""
    text = trafilatura.extract(
        html,
        url=url,
        favor_precision=True,
        include_comments=False,
        include_tables=True
    )
    return text.strip() if text else ""


def extract_text_with_bs4(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def fetch(url: str, timeout: int = FETCH_TIMEOUT_SECONDS, max_bytes: int = FETCH_MAX_BYTES) -> dict:
    fetched_at = datetime.now().isoformat(timespec="seconds")
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, stream=True, allow_redirects=True)
        content_type = response.headers.get("content-type", "")
        if content_type and not any(kind in content_type.lower() for kind in ("text/", "html", "xml", "json")):
            return {
                "success": False,
                "url": url,
                "final_url": response.url,
                "status_code": response.status_code,
                "content_type": content_type,
                "html": "",
                "text": "",
                "error_message": "binary or unsupported content type skipped",
                "fetched_at": fetched_at,
            }
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536, decode_unicode=False):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                chunks.append(chunk[: max(0, len(chunk) - (total - max_bytes))])
                break
            chunks.append(chunk)
        body = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        if response.status_code >= 400:
            return {
                "success": False,
                "url": url,
                "final_url": response.url,
                "status_code": response.status_code,
                "content_type": content_type,
                "html": body[:MAX_PAGE_CHARS],
                "text": "",
                "error_message": f"HTTP {response.status_code}",
                "fetched_at": fetched_at,
            }
        return {
            "success": True,
            "url": url,
            "final_url": response.url,
            "status_code": response.status_code,
            "content_type": content_type,
            "html": body,
            "text": body,
            "error_message": "",
            "fetched_at": fetched_at,
            "truncated": total > max_bytes,
        }
    except requests.exceptions.Timeout:
        return {"success": False, "url": url, "final_url": url, "status_code": 0, "content_type": "", "html": "", "text": "", "error_message": "request timed out", "fetched_at": fetched_at}
    except Exception as exc:
        return {"success": False, "url": url, "final_url": url, "status_code": 0, "content_type": "", "html": "", "text": "", "error_message": str(exc), "fetched_at": fetched_at}


def extract(url: str = "", html: str = "") -> dict:
    try:
        soup = BeautifulSoup(html or "", "lxml")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        headings = [tag.get_text(" ", strip=True) for tag in soup.find_all(["h1", "h2", "h3"]) if tag.get_text(" ", strip=True)][:20]
        links = []
        for tag in soup.find_all("a", href=True):
            href = urljoin(url, tag["href"])
            text = tag.get_text(" ", strip=True)
            links.append({"text": text[:120], "url": href})
            if len(links) >= 50:
                break
        code_blocks = [tag.get_text("\n", strip=True)[:1000] for tag in soup.find_all(["pre", "code"]) if tag.get_text(strip=True)][:10]
        main_text = extract_text_with_trafilatura(html, url=url) if html else ""
        if not main_text:
            main_text = extract_text_with_bs4(html)
        if len(main_text) > MAX_PAGE_CHARS:
            main_text = main_text[:MAX_PAGE_CHARS] + "\n...[truncated]"
        return {
            "url": url,
            "title": title,
            "main_text": main_text,
            "text": main_text,
            "headings": headings,
            "links": links,
            "code_blocks": code_blocks,
            "text_char_count": len(main_text),
            "extraction_success": bool(main_text.strip()),
            "error_message": "" if main_text.strip() else "no readable text extracted",
        }
    except Exception as exc:
        return {"url": url, "title": "", "main_text": "", "text": "", "headings": [], "links": [], "code_blocks": [], "text_char_count": 0, "extraction_success": False, "error_message": str(exc)}


def read_url(url: str) -> dict:
    try:
        fetched = fetch(url)
        if not fetched.get("success"):
            return {
                "url": url,
                "success": False,
                "text": "",
                "error": fetched.get("error_message", "fetch failed"),
                "status_code": fetched.get("status_code", 0),
            }
        extracted = extract(fetched.get("final_url") or url, fetched.get("html", ""))

        return {
            "url": url,
            "final_url": fetched.get("final_url", url),
            "success": extracted.get("extraction_success", False),
            "title": extracted.get("title", ""),
            "text": extracted.get("main_text", ""),
            "headings": extracted.get("headings", []),
            "links": extracted.get("links", []),
            "code_blocks": extracted.get("code_blocks", []),
            "error": extracted.get("error_message", ""),
            "fetched_at": fetched.get("fetched_at", ""),
        }
    except Exception as e:
        return {
            "url": url,
            "success": False,
            "text": "",
            "error": str(e)
        }
