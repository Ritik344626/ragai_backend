from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser

from app.schemas.source import SourceItem


def _parse_published(entry: dict) -> datetime | None:
    raw_value = entry.get("published") or entry.get("updated")
    if not raw_value:
        return None

    try:
        return parsedate_to_datetime(raw_value)
    except (TypeError, ValueError):
        return None


def fetch_rss_items(feed_url: str, source_id: str, limit: int) -> list[SourceItem]:
    parsed_feed = feedparser.parse(feed_url)
    items: list[SourceItem] = []

    for entry in parsed_feed.entries[:limit]:
        items.append(
            SourceItem(
                source_id=source_id,
                title=entry.get("title", "Untitled"),
                url=entry.get("link", ""),
                published_at=_parse_published(entry),
                summary=entry.get("summary"),
            )
        )

    return items


def build_google_news_rss_url(query: str) -> str:
    encoded_query = quote_plus(query)
    return (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    )
