"""Alpha Vantage 公共辅助（免费 key，限流）。

文档：https://www.alphavantage.co/documentation/
key 通过环境变量 / .env 的 ALPHA_VANTAGE_API_KEY 提供。
"""

from __future__ import annotations

import os
import time
import urllib.parse

from ._http import fetch_json

_BASE_URL = "https://www.alphavantage.co/query"
_MIN_INTERVAL_SECONDS = 1.1  # 免费 key 限 1 请求/秒
_RETRY_SLEEP_SECONDS = 3.0
_last_request_at = 0.0


def api_key() -> str:
    """读取 Alpha Vantage key；未配置时报错（由循环回填给模型）。"""
    key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少 ALPHA_VANTAGE_API_KEY，请在 .env 中配置")
    return key


def fetch(function: str, symbol: str | None = None, **extra: str) -> dict:
    """调用指定 function，返回 JSON。

    symbol 映射为 symbol 参数；其余关键字参数原样拼进 query，
    例如 NEWS_SENTIMENT 用 tickers、limit。
    """
    query = [f"function={function}", f"apikey={api_key()}"]
    if symbol:
        query.append(f"symbol={urllib.parse.quote(symbol)}")
    query.extend(
        f"{key}={urllib.parse.quote(str(value))}" for key, value in extra.items()
    )
    url = _BASE_URL + "?" + "&".join(query)

    data = _request(url)
    if _is_rate_limit(data):
        # 限流：等待后重试一次（免费 key 常见，1 请求/秒）
        time.sleep(_RETRY_SLEEP_SECONDS)
        data = _request(url)
    return data


def _request(url: str) -> dict:
    """带最小间隔节流的请求。"""
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL_SECONDS:
        time.sleep(_MIN_INTERVAL_SECONDS - elapsed)
    _last_request_at = time.monotonic()
    return fetch_json(url)


def _is_rate_limit(data: dict) -> bool:
    """限流响应通常带 Information / Note 字段。"""
    return any(key in data for key in ("Information", "Note"))


def error_text(data: dict) -> str | None:
    """提取 Alpha Vantage 错误响应（Error Message / Information / Note）。"""
    for key in ("Error Message", "Information", "Note"):
        if key in data:
            return f"Alpha Vantage：{data[key]}"
    return None
