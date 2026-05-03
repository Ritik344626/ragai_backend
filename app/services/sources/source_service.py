from app.core.config import settings
from app.schemas.source import SourceInfo, SourceItem
from app.services.sources.google_trends import fetch_google_trends_items
from app.services.sources.hackernews import fetch_hackernews_items
from app.services.sources.rss import build_google_news_rss_url, fetch_rss_items

AVAILABLE_SOURCES: list[SourceInfo] = [
    SourceInfo(
        id="google_news_ai",
        name="Google News (AI query)",
        category="news",
        description="Google News RSS for AI related headlines.",
    ),
    SourceInfo(
        id="google_news_global",
        name="Google News (Global query)",
        category="news",
        description="Google News RSS for global trend headlines.",
    ),
    SourceInfo(
        id="hackernews_topstories",
        name="Hacker News Top Stories",
        category="trend",
        description="Top stories from Hacker News official API.",
    ),
    SourceInfo(
        id="google_trends_daily",
        name="Google Trends Daily",
        category="trend",
        description="Daily trending searches from Google Trends.",
    ),
]


def list_sources() -> list[SourceInfo]:
    return AVAILABLE_SOURCES


def fetch_source_preview(source_id: str, limit: int) -> list[SourceItem]:
    normalized_limit = max(1, min(limit, settings.source_preview_max_items))

    if source_id == "google_news_ai":
        return fetch_rss_items(
            feed_url=build_google_news_rss_url("artificial intelligence"),
            source_id=source_id,
            limit=normalized_limit,
        )

    if source_id == "google_news_global":
        return fetch_rss_items(
            feed_url=build_google_news_rss_url("global trends"),
            source_id=source_id,
            limit=normalized_limit,
        )

    if source_id == "hackernews_topstories":
        return fetch_hackernews_items(
            limit=normalized_limit,
            timeout_seconds=settings.external_request_timeout_seconds,
        )

    if source_id == "google_trends_daily":
        return fetch_google_trends_items(
            limit=normalized_limit,
            pn=settings.google_trends_pn,
        )

    raise ValueError(f"Unsupported source_id: {source_id}")
