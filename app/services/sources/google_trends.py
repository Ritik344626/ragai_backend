import time
from urllib.parse import quote_plus

from pytrends.request import TrendReq

from app.schemas.source import SourceItem

# Fallback mock trending keywords if live fetch fails
FALLBACK_TRENDING_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "python programming",
    "web development",
    "cloud computing",
    "cybersecurity",
    "data science",
    "blockchain",
    "quantum computing",
    "open source",
]


def _build_google_search_url(keyword: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(keyword)}"


def fetch_google_trends_items(limit: int, pn: str, retries: int = 3) -> list[SourceItem]:
    """
    Fetch trending keywords from Google Trends with retry logic.
    Falls back to mock data if live fetch fails.
    """
    items: list[SourceItem] = []

    # Try to fetch live trends with retries
    for attempt in range(retries):
        try:
            pytrends = TrendReq(hl="en-US", tz=330)
            trends_df = pytrends.trending_searches(pn=pn)

            for keyword in trends_df[0].tolist()[:limit]:
                items.append(
                    SourceItem(
                        source_id="google_trends_daily",
                        title=str(keyword),
                        url=_build_google_search_url(str(keyword)),
                        published_at=None,
                        summary="Trending keyword from Google Trends daily feed.",
                    )
                )
            return items
        except Exception as exc:
            if attempt < retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                time.sleep(wait_time)
            else:
                # Last attempt failed, use fallback
                print(f"Warning: Google Trends fetch failed after {retries} attempts: {exc}")
                break

    # Fallback: use mock trending keywords
    for keyword in FALLBACK_TRENDING_KEYWORDS[:limit]:
        items.append(
            SourceItem(
                source_id="google_trends_daily",
                title=keyword,
                url=_build_google_search_url(keyword),
                published_at=None,
                summary="Trending keyword (fallback mock data - live fetch unavailable).",
            )
        )

    return items

