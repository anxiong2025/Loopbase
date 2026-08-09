"""结构化行情/基本面数据：给仪表盘用的原始数值，不做成给模型看的字符串。

区别于 tools/ 目录下的工具（返回字符串，供 ReAct 循环回填给模型），
这里的函数返回结构化 dict，供 HTTP API 直接序列化成 JSON 给前端。

行情走 Yahoo Finance（免费、无 key、无每日硬限额）；基本面
（市值/市盈率/利润率等）Yahoo 的公开接口拿不到，仍走 Alpha Vantage
OVERVIEW（免费 key，限流）。两次调用相互独立，任一失败不影响另一半。
"""

from __future__ import annotations

from typing import Any

from .tools import _alpha, _yahoo


def _to_float(value: Any) -> float | None:
    if value in (None, "", "None", "-"):
        return None
    try:
        return float(str(value).rstrip("%"))
    except (TypeError, ValueError):
        return None


def fetch_overview(symbol: str) -> dict[str, Any]:
    """返回 {symbol} 的实时行情 + 核心基本面指标（结构化）。

    行情（Yahoo）和基本面（Alpha Vantage OVERVIEW）是两次独立调用，
    任一失败都不让另一半数据陪葬——部分数据也比整体报错更有用，
    失败原因记录在 warnings 里，由前端决定怎么提示。
    """
    symbol = symbol.upper().strip()
    result: dict[str, Any] = {"symbol": symbol, "warnings": []}

    try:
        quote = _yahoo.fetch_quote(symbol)
        result["price"] = quote.get("price")
        result["change"] = quote.get("change")
        result["changePercent"] = quote.get("changePercent")
        result["name"] = quote.get("name")
        result["week52Low"] = quote.get("week52Low")
        result["week52High"] = quote.get("week52High")
        result["latestTradingDay"] = quote.get("latestTradingDay")
    except RuntimeError as exc:
        result["warnings"].append(str(exc))

    try:
        overview_data = _alpha.fetch("OVERVIEW", symbol)
        if "Symbol" in overview_data:
            result.update(
                {
                    "name": overview_data.get("Name"),
                    "sector": overview_data.get("Sector"),
                    "industry": overview_data.get("Industry"),
                    "marketCap": _to_float(overview_data.get("MarketCapitalization")),
                    "peTTM": _to_float(overview_data.get("TrailingPE")),
                    "peForward": _to_float(overview_data.get("ForwardPE")),
                    "psTTM": _to_float(overview_data.get("PriceToSalesRatioTTM")),
                    "pbRatio": _to_float(overview_data.get("PriceToBookRatio")),
                    "evToEbitda": _to_float(overview_data.get("EVToEBITDA")),
                    "profitMargin": _to_float(overview_data.get("ProfitMargin")),
                    "operatingMargin": _to_float(overview_data.get("OperatingMarginTTM")),
                    "revenueGrowthYoY": _to_float(overview_data.get("QuarterlyRevenueGrowthYOY")),
                    "earningsGrowthYoY": _to_float(
                        overview_data.get("QuarterlyEarningsGrowthYOY")
                    ),
                    "dividendYield": _to_float(overview_data.get("DividendYield")),
                    "analystTargetPrice": _to_float(overview_data.get("AnalystTargetPrice")),
                    "week52Low": _to_float(overview_data.get("52WeekLow")),
                    "week52High": _to_float(overview_data.get("52WeekHigh")),
                    "beta": _to_float(overview_data.get("Beta")),
                    "cik": overview_data.get("CIK"),
                }
            )
        else:
            result["warnings"].append(_alpha.error_text(overview_data) or "基本面数据暂不可用")
    except RuntimeError as exc:
        result["warnings"].append(str(exc))

    if "price" not in result and "marketCap" not in result:
        raise RuntimeError("；".join(result["warnings"]) or f"未找到 {symbol} 的数据")

    return result
