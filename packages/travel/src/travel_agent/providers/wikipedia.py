"""中文维基百科旅行背景资料搜索；不充当实时票价或开放信息源。"""

from __future__ import annotations

from typing import Any

from .http import fetch_json

API_URL = "https://zh.wikipedia.org/w/api.php"


def search(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    text = query.strip()
    if not text:
        raise ValueError("搜索词不能为空")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 8:
        raise ValueError("limit 必须是 1 到 8 的整数")
    data = fetch_json(
        API_URL,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": text,
            "gsrlimit": limit,
            "prop": "extracts|info",
            "inprop": "url",
            "exintro": 1,
            "explaintext": 1,
            "exsentences": 3,
            "format": "json",
            "formatversion": 2,
        },
    )
    pages = (data.get("query") or {}).get("pages") or []
    pages.sort(key=lambda page: page.get("index", 10_000))
    return [
        {
            "title": page.get("title"),
            "summary": page.get("extract") or "",
            "url": page.get("fullurl")
            or f"https://zh.wikipedia.org/?curid={page.get('pageid')}",
        }
        for page in pages[:limit]
    ]


def search_locations(query: str, *, limit: int = 6) -> list[dict[str, Any]]:
    """Return location candidates, including coordinates when Wikipedia has them."""
    text = query.strip()
    if not text:
        raise ValueError("搜索词不能为空")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 8:
        raise ValueError("limit 必须是 1 到 8 的整数")
    data = fetch_json(
        API_URL,
        params={
            "action": "query",
            "generator": "search",
            "gsrsearch": text,
            "gsrlimit": limit,
            "prop": "coordinates|info",
            "coprimary": "all",
            "inprop": "url",
            "format": "json",
            "formatversion": 2,
        },
    )
    pages = (data.get("query") or {}).get("pages") or []
    pages.sort(key=lambda page: page.get("index", 10_000))
    results: list[dict[str, Any]] = []
    for page in pages[:limit]:
        coordinates = page.get("coordinates") or []
        coordinate = coordinates[0] if coordinates else {}
        results.append(
            {
                "name": page.get("title") or text,
                "latitude": coordinate.get("lat"),
                "longitude": coordinate.get("lon"),
                "url": page.get("fullurl")
                or f"https://zh.wikipedia.org/?curid={page.get('pageid')}",
            }
        )
    return results
