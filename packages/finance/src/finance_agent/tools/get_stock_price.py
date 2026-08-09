"""实时股价工具：通过 Yahoo Finance 公开行情接口获取（免费，无 key，无每日限额）。"""

from __future__ import annotations

from loopbase import ToolSpec

from . import _yahoo

SPEC = ToolSpec(
    name="get_stock_price",
    description="查询指定美股的最新价格与当日涨跌（数据源：Yahoo Finance）。",
    parameters={
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "美股代码，如：AAPL、TSLA、IBM",
            },
        },
        "required": ["symbol"],
    },
)


def impl(symbol: str) -> str:
    """返回 {symbol} 的最新价与当日涨跌。"""
    quote = _yahoo.fetch_quote(symbol)

    parts = [f"{symbol} 最新价 {quote['price']} {quote.get('currency') or 'USD'}"]
    if quote.get("change") is not None and quote.get("changePercent") is not None:
        parts.append(f"当日 {quote['change']:+.2f}（{quote['changePercent']:+.2f}%）")
    if quote.get("week52Low") and quote.get("week52High"):
        parts.append(f"52周区间 {quote['week52Low']} ~ {quote['week52High']}")
    return "，".join(parts)


def register(registry) -> None:
    """把本工具注册进 registry。"""
    registry.register(
        name=SPEC.name,
        description=SPEC.description,
        parameters=SPEC.parameters,
        impl=impl,
    )
