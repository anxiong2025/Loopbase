"""实时股价工具：通过 Alpha Vantage GLOBAL_QUOTE 获取（免费 key，限流）。"""

from __future__ import annotations

from loopbase import ToolSpec

from . import _alpha

SPEC = ToolSpec(
    name="get_stock_price",
    description="查询指定美股的最新价格与当日涨跌（数据源：Alpha Vantage）。",
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
    data = _alpha.fetch("GLOBAL_QUOTE", symbol)
    quote = data.get("Global Quote") or {}
    if not quote:
        raise RuntimeError(_alpha.error_text(data) or f"未找到 {symbol} 的行情数据")

    parts = [f"{symbol} 最新价 {quote.get('05. price')} USD"]
    change = quote.get("09. change")
    percent = quote.get("10. change percent")
    if change and percent:
        parts.append(f"当日 {change}（{percent}）")
    elif change:
        parts.append(f"当日 {change}")
    if quote.get("07. latest trading day"):
        parts.append(f"交易日 {quote.get('07. latest trading day')}")
    return "，".join(parts)


def register(registry) -> None:
    """把本工具注册进 registry。"""
    registry.register(
        name=SPEC.name,
        description=SPEC.description,
        parameters=SPEC.parameters,
        impl=impl,
    )
