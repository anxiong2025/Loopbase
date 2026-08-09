"""Yahoo Finance 公开行情接口（免费，无需 key，没有 Alpha Vantage 那种每日硬限额）。

只用 /v8/finance/chart —— 这个端点公开可访问，不需要 crumb 鉴权。
quoteSummary（市值/市盈率等基本面）需要 crumb，而 Yahoo 最近收紧了拿 crumb
的流程（fc.yahoo.com 已经 404，正常访问 finance.yahoo.com 也拿不到会话
cookie 了），实测走不通，所以这里不碰，基本面依然走 Alpha Vantage。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


def fetch_quote(symbol: str) -> dict:
    """返回 {symbol} 的实时价格、涨跌、52 周区间（结构化数值）。"""
    url = _CHART_URL.format(symbol=symbol.upper()) + "?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"Yahoo Finance 请求失败：{exc}") from exc

    chart = data.get("chart") or {}
    result = chart.get("result") or []
    if not result:
        error = chart.get("error") or {}
        raise RuntimeError(error.get("description") or f"未找到 {symbol} 的行情数据")

    meta = result[0].get("meta") or {}
    price = meta.get("regularMarketPrice")
    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = price - prev_close if price is not None and prev_close is not None else None
    change_percent = change / prev_close * 100 if change is not None and prev_close else None

    trading_time = meta.get("regularMarketTime")
    latest_trading_day = (
        datetime.fromtimestamp(trading_time, tz=UTC).strftime("%Y-%m-%d")
        if trading_time
        else None
    )

    return {
        "symbol": meta.get("symbol", symbol).upper(),
        "name": meta.get("longName") or meta.get("shortName"),
        "price": price,
        "change": change,
        "changePercent": change_percent,
        "previousClose": prev_close,
        "week52Low": meta.get("fiftyTwoWeekLow"),
        "week52High": meta.get("fiftyTwoWeekHigh"),
        "currency": meta.get("currency"),
        "exchangeName": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "latestTradingDay": latest_trading_day,
    }
