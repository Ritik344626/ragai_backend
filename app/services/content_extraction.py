from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings

_WHITESPACE_RE = re.compile(r"\s+")
_MIN_CONTENT_LEN = 200
_MAX_CONTENT_LEN = 12000


def _normalize_text(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _best_text_block(soup: BeautifulSoup) -> str:
    # Prefer semantic content containers when available.
    preferred_blocks = soup.select("article, main, [role='main']")
    for block in preferred_blocks:
        text = _normalize_text(block.get_text(" ", strip=True))
        if len(text) >= _MIN_CONTENT_LEN:
            return text[:_MAX_CONTENT_LEN]

    # Fallback: choose the largest paragraph-like block.
    candidates = []
    for block in soup.select("p, li, h1, h2, h3"):
        text = _normalize_text(block.get_text(" ", strip=True))
        if len(text) >= 40:
            candidates.append(text)
    joined = _normalize_text(" ".join(candidates))
    if joined:
        return joined[:_MAX_CONTENT_LEN]

    body_text = _normalize_text(soup.get_text(" ", strip=True))
    return body_text[:_MAX_CONTENT_LEN]


def extract_full_content(url: str, timeout_seconds: float | None = None) -> str | None:
    timeout = timeout_seconds or settings.external_request_timeout_seconds
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }

    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()

        content_type = (response.headers.get("content-type") or "").lower()
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            text_payload = _normalize_text(response.text)
            return text_payload[:_MAX_CONTENT_LEN] if text_payload else None

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup.select("script, style, noscript, nav, footer, header, form, aside"):
            tag.decompose()

        extracted = _best_text_block(soup)
        if len(extracted) < 80:
            return None
        return extracted

