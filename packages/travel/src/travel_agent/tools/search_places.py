"""旅行地点与景点背景搜索工具。"""

from __future__ import annotations

import json

from loopbase import ToolSpec

from ..providers import wikipedia

SPEC = ToolSpec(
    name="search_travel_places",
    description=(
        "搜索目的地的景点、街区、博物馆等背景资料并返回来源链接。"
        "资料来自中文维基百科，不代表实时开放时间、预约规则或票价。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "目的地城市"},
            "query": {
                "type": "string",
                "description": "偏好或地点关键词，如历史景点、亲子博物馆",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 8,
                "description": "最多返回多少条，默认5条",
            },
        },
        "required": ["city", "query"],
    },
)


def impl(city: str, query: str, limit: int = 5) -> str:
    results = wikipedia.search(f"{city} {query}", limit=limit)
    return json.dumps(
        {
            "source": "中文维基百科",
            "notice": "仅作背景资料；开放时间、预约和票价需出发前复核官方来源。",
            "results": results,
        },
        ensure_ascii=False,
    )


def register(registry) -> None:
    registry.register(
        name=SPEC.name,
        description=SPEC.description,
        parameters=SPEC.parameters,
        impl=impl,
    )
