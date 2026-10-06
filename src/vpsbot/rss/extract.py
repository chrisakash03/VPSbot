from __future__ import annotations

import logging
from urllib.parse import urlparse

from vpsbot.rss.feed import clip_plain_text

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 1_000_000
EXCERPT_MAX_CHARS = 4000
_MIN_EXTRACT_CHARS = 80


def fetchable_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    path = parsed.path.lower()
    return not path.endswith(".pdf")


async def fetch_article_excerpt(url: str) -> str | None:
    """Download one page and return clipped article text. Imports stay local."""
    if not fetchable_url(url):
        return None

    import httpx

    body = bytearray()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=FETCH_TIMEOUT_SECONDS,
            headers={"User-Agent": "VPSbot/1.0 (daily digest excerpt)"},
        ) as client:
            async with client.stream("GET", url) as response:
                if response.status_code >= 400:
                    return None
                content_type = response.headers.get("content-type", "").lower()
                if "pdf" in content_type:
                    return None
                async for chunk in response.aiter_bytes():
                    remaining = MAX_RESPONSE_BYTES - len(body)
                    if remaining <= 0:
                        break
                    body.extend(chunk[:remaining])
    except httpx.HTTPError as exc:
        logger.info("Excerpt fetch failed %s: %s", url, exc)
        return None

    html = bytes(body).decode("utf-8", errors="replace")
    del body
    text = _extract_text(html)
    del html
    if text is None:
        return None
    clipped = clip_plain_text(text, EXCERPT_MAX_CHARS)
    if len(clipped) < _MIN_EXTRACT_CHARS:
        return None
    return clipped


def _extract_text(html: str) -> str | None:
    import trafilatura

    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
    )
    if not extracted:
        return None
    return extracted.strip()
