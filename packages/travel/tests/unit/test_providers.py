"""Provider normalization tests."""

from __future__ import annotations

from travel_agent.providers import open_meteo, wikipedia


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
