from datetime import datetime, timezone

import httpx

from app.schemas.source import SourceItem

HACKERNEWS_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HACKERNEWS_ITEM_URL_TEMPLATE = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"


def _to_datetime(utc_seconds: int | None) -> datetime | None:
    if utc_seconds is None:
        return None
    return datetime.fromtimestamp(utc_seconds, tz=timezone.utc)


def fetch_hackernews_items(limit: int, timeout_seconds: float) -> list[SourceItem]:
    with httpx.Client(timeout=timeout_seconds) as client:
        story_ids_response = client.get(HACKERNEWS_TOP_STORIES_URL)
        story_ids_response.raise_for_status()
        story_ids: list[int] = story_ids_response.json()

        items: list[SourceItem] = []
        for item_id in story_ids[:limit]:
            item_response = client.get(HACKERNEWS_ITEM_URL_TEMPLATE.format(item_id=item_id))
            item_response.raise_for_status()
            payload = item_response.json()

            url = payload.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
            items.append(
                SourceItem(
                    source_id="hackernews_topstories",
                    title=payload.get("title", "Untitled"),
                    url=url,
                    published_at=_to_datetime(payload.get("time")),
                    summary=None,
                )
            )

    return items
