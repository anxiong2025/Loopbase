"""仅标准库的 JSON HTTP 客户端。"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "LoopbaseTravel/0.1"


def fetch_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}{'&' if '?' in url else '?'}{query}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"旅行数据接口请求失败：{exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("旅行数据接口返回了无效 JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("旅行数据接口返回值不是 JSON 对象")
    return data
