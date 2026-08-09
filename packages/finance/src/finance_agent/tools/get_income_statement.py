"""利润表工具：Alpha Vantage INCOME_STATEMENT（免费 key，限流）。"""

from __future__ import annotations

from loopbase import ToolSpec

from . import _alpha

SPEC = ToolSpec(
    name="get_income_statement",
    description="查询指定美股最近一年的利润表关键项（营收、毛利、营业利润、净利润、EBITDA、利润率）。",
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


def _fmt(value) -> str | None:
    """金额字符串 → 亿/万亿美元。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    for unit, divisor in (("万亿美元", 1e12), ("亿美元", 1e8), ("万美元", 1e4)):
        if abs(number) >= divisor:
            return f"{number / divisor:.2f}{unit}"
    return str(number)


def _margin(report: dict, numerator: str, denominator: str) -> str | None:
    try:
        return f"{float(report[numerator]) / float(report[denominator]) * 100:.1f}%"
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def impl(symbol: str) -> str:
    """返回 {symbol} 最近一个财年的利润表摘要。"""
    data = _alpha.fetch("INCOME_STATEMENT", symbol)
    annual = data.get("annualReports") or []
    if not annual:
        raise RuntimeError(_alpha.error_text(data) or f"未找到 {symbol} 的利润表数据")
    report = annual[0]

    items = [
        ("财年结束", report.get("fiscalDateEnding")),
        ("总营收", _fmt(report.get("totalRevenue"))),
        ("毛利润", _fmt(report.get("grossProfit"))),
        ("营业利润", _fmt(report.get("operatingIncome"))),
        ("净利润", _fmt(report.get("netIncome"))),
        ("EBITDA", _fmt(report.get("ebitda"))),
        ("毛利率", _margin(report, "grossProfit", "totalRevenue")),
        ("净利率", _margin(report, "netIncome", "totalRevenue")),
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
