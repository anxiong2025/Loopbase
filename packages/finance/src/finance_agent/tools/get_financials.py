"""财务数据工具：通过 Alpha Vantage OVERVIEW 获取核心估值指标（免费 key，限流）。"""

from __future__ import annotations

from loopbase import ToolSpec

from . import _alpha

SPEC = ToolSpec(
    name="get_financials",
    description="查询指定美股的核心财务与估值指标（市值、市盈率、市净率、股息率、52周区间等，数据源：Alpha Vantage）。",
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


def _format_market_cap(value: float | None) -> str | None:
    if value is None:
        return None
    for unit, divisor in (("万亿", 1e12), ("亿", 1e8), ("万", 1e4)):
        if abs(value) >= divisor:
            return f"{value / divisor:.2f}{unit}美元"
    return str(value)


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_percent(value) -> str | None:
    """OVERVIEW 的 DividendYield 是小数（如 0.0034 = 0.34%）。"""
    try:
        return f"{float(value) * 100:.2f}%" if value is not None else None
    except (TypeError, ValueError):
        return None


def impl(symbol: str) -> str:
    """返回 {symbol} 的核心财务与估值指标。"""
    data = _alpha.fetch("OVERVIEW", symbol)
    if "Symbol" not in data:
        raise RuntimeError(_alpha.error_text(data) or f"未找到 {symbol} 的财务数据")

    low, high = data.get("52WeekLow"), data.get("52WeekHigh")

    items = [
        ("公司", data.get("Name")),
        ("市值", _format_market_cap(_to_float(data.get("MarketCapitalization")))),
        ("市盈率(TTM)", _to_float(data.get("TrailingPE"))),
        ("前瞻市盈率", _to_float(data.get("ForwardPE"))),
        ("市净率", _to_float(data.get("PriceToBookRatio"))),
        ("股息率", _format_percent(data.get("DividendYield"))),
        ("52周区间", f"{low} ~ {high}" if low and high else None),
        ("分析师目标价", data.get("AnalystTargetPrice")),
    ]
    parts = [f"{label}: {value}" for label, value in items if value is not None]
    return "；".join(parts)


def register(registry) -> None:
    """把本工具注册进 registry。"""
    registry.register(
        name=SPEC.name,
        description=SPEC.description,
        parameters=SPEC.parameters,
        impl=impl,
    )
