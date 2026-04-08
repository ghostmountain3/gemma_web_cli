import requests
import trafilatura
from bs4 import BeautifulSoup
from .config import MAX_PAGE_CHARS

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return response.text


def extract_text_with_trafilatura(html: str, url: str = "") -> str:
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


def read_url(url: str) -> dict:
    try:
        html = fetch_html(url)

        text = extract_text_with_trafilatura(html, url=url)
        if not text:
            text = extract_text_with_bs4(html)

        if len(text) > MAX_PAGE_CHARS:
            text = text[:MAX_PAGE_CHARS] + "\n...[truncated]"

        return {
            "url": url,
            "success": True,
            "text": text,
            "error": ""
        }
    except Exception as e:
        return {
            "url": url,
            "success": False,
            "text": "",
            "error": str(e)
        }