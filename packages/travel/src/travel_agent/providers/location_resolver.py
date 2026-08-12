"""Resolve cities, districts, and landmarks into auditable coordinates."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from . import open_meteo, wikipedia


class LocationResolutionError(LookupError):
    """A location could not be resolved with enough confidence."""

    def __init__(self, query: str, candidates: list[dict[str, Any]]) -> None:
        self.query = query
        self.candidates = candidates
        super().__init__(f"没有可靠匹配地点：{query}")


def resolve(name: str) -> dict[str, Any]:
    """Resolve a location, preferring city geocoding then landmark coordinates."""
    query = _clean_query(name)
    try:
        location = open_meteo.geocode(query)
    except RuntimeError:
        pass
    else:
        return {
            **location,
            "source": "Open-Meteo Geocoding",
            "matched_query": query,
            "match_score": 1.0,
        }

    candidates = wikipedia.search_locations(query, limit=6)
    ranked = sorted(
        (
            {**candidate, "match_score": _match_score(query, candidate["name"])}
            for candidate in candidates
        ),
        key=lambda candidate: candidate["match_score"],
        reverse=True,
    )
    matches = [
        candidate
        for candidate in ranked
        if candidate.get("latitude") is not None
        and candidate.get("longitude") is not None
    ]
    if not matches or matches[0]["match_score"] < 0.55:
        raise LocationResolutionError(query, ranked[:5])

    best = matches[0]
    return {
        "name": best["name"],
        "country": best.get("country"),
        "admin1": best.get("admin1"),
        "latitude": best["latitude"],
        "longitude": best["longitude"],
        "timezone": best.get("timezone"),
        "source": "中文维基百科坐标",
        "source_url": best.get("url"),
        "matched_query": query,
        "match_score": round(float(best["match_score"]), 3),
    }


def _clean_query(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("地点名称不能为空")
    return re.sub(r"\s+", " ", value).strip(" ,，。;；")


def _match_score(query: str, candidate: str) -> float:
    left = _match_text(query)
    right = _match_text(candidate)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if right in left or left in right:
        shorter, longer = sorted((len(left), len(right)))
        position_bonus = 0.0
        if right in left and len(left) > len(right):
            position_bonus = 0.05 * left.rfind(right) / (len(left) - len(right))
        type_bonus = 0.0
        for suffix in ("市", "区", "县"):
            if query.rstrip().endswith(suffix) and _without_parenthetical(
                candidate
            ).rstrip().endswith(suffix):
                type_bonus = 0.04
                break
        score = 0.78 + 0.17 * shorter / longer + position_bonus + type_bonus
        return min(1.0, score)
    return SequenceMatcher(None, left, right).ratio()


def _match_text(value: str) -> str:
    text = _without_parenthetical(value).casefold()
    text = re.sub(r"[\s·•,，。\-_]+", "", text)
    return re.sub(r"(?:风景区|旅游区|景区|市|区|县|站)$", "", text)


def _without_parenthetical(value: str) -> str:
    return re.sub(r"[（(][^）)]*[）)]", "", value)
