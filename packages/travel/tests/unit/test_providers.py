"""Provider normalization tests."""

from __future__ import annotations

import pytest
from travel_agent.providers import location_resolver, open_meteo, wikipedia


def test_geocode_selects_the_first_match(monkeypatch) -> None:
    monkeypatch.setattr(
        open_meteo,
        "fetch_json",
        lambda url, params: {
            "results": [
                {
                    "name": "北京",
                    "country": "中国",
                    "admin1": "北京市",
                    "latitude": 39.9042,
                    "longitude": 116.4074,
                    "timezone": "Asia/Shanghai",
                }
            ]
        },
    )

    result = open_meteo.geocode("北京")

    assert result["name"] == "北京"
    assert result["latitude"] == 39.9042


def test_wikipedia_search_normalizes_and_orders_pages(monkeypatch) -> None:
    monkeypatch.setattr(
        wikipedia,
        "fetch_json",
        lambda url, params: {
            "query": {
                "pages": [
                    {
                        "pageid": 2,
                        "index": 2,
                        "title": "第二条",
                        "extract": "第二条摘要",
                        "fullurl": "https://example.com/2",
                    },
                    {
                        "pageid": 1,
                        "index": 1,
                        "title": "第一条",
                        "extract": "第一条摘要",
                        "fullurl": "https://example.com/1",
                    },
                ]
            }
        },
    )

    results = wikipedia.search("北京 景点", limit=2)

    assert [item["title"] for item in results] == ["第一条", "第二条"]
    assert results[0]["url"] == "https://example.com/1"


def test_wikipedia_location_search_keeps_candidates_without_coordinates(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        wikipedia,
        "fetch_json",
        lambda url, params: {
            "query": {
                "pages": [
                    {
                        "pageid": 1,
                        "index": 1,
                        "title": "世界之窗 (深圳)",
                        "coordinates": [{"lat": 22.5347, "lon": 113.973}],
                        "fullurl": "https://example.com/window",
                    },
                    {"pageid": 2, "index": 2, "title": "世界之窗"},
                ]
            }
        },
    )

    results = wikipedia.search_locations("深圳世界之窗")

    assert results[0]["latitude"] == 22.5347
    assert results[1]["latitude"] is None


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        ("深圳福田区", "福田区"),
        ("深圳罗湖东门老街", "东门老街"),
        ("深圳世界之窗", "世界之窗 (深圳)"),
    ],
)
def test_location_resolver_fuzzy_matches_landmarks(
    monkeypatch, query, candidate
) -> None:
    monkeypatch.setattr(
        open_meteo,
        "geocode",
        lambda name: (_ for _ in ()).throw(RuntimeError("not found")),
    )
    monkeypatch.setattr(
        wikipedia,
        "search_locations",
        lambda name, limit: [
            {
                "name": candidate,
                "latitude": 22.53,
                "longitude": 114.05,
                "url": "https://example.com/place",
            }
        ],
    )

    result = location_resolver.resolve(query)

    assert result["name"] == candidate
    assert result["source"] == "中文维基百科坐标"
    assert result["match_score"] >= 0.55


def test_location_resolver_matches_station_alias_for_a_landmark(monkeypatch) -> None:
    monkeypatch.setattr(
        open_meteo,
        "geocode",
        lambda name: (_ for _ in ()).throw(RuntimeError("not found")),
    )
    monkeypatch.setattr(
        wikipedia,
        "search_locations",
        lambda name, limit: [
            {
                "name": "老街站 (深圳市)",
                "latitude": 22.5469,
                "longitude": 114.1113,
                "url": "https://example.com/laojie",
            }
        ],
    )

    result = location_resolver.resolve("深圳罗湖东门老街")

    assert result["name"] == "老街站 (深圳市)"
    assert result["match_score"] >= 0.55
