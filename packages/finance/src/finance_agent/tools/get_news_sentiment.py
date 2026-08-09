"""新闻情绪工具：Alpha Vantage NEWS_SENTIMENT（免费 key，限流）。"""

from __future__ import annotations

from loopbase import ToolSpec

from . import _alpha

SPEC = ToolSpec(
    name="get_news_sentiment",
    description="查询指定美股近期新闻与整体情绪（标题、来源、情绪评分与标签）。",
    parameters={
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "美股代码，如：AAPL、TSLA",
            },
        },
        "required": ["ticker"],
    },
)


def impl(ticker: str) -> str:
    """返回 {ticker} 近期新闻数量、平均情绪与主要标题。"""
    data = _alpha.fetch("NEWS_SENTIMENT", tickers=ticker, limit=10)
    feed = data.get("feed") or []
    if not feed:
        raise RuntimeError(_alpha.error_text(data) or f"未找到 {ticker} 的新闻数据")

    scores = [
        float(item["overall_sentiment_score"])
        for item in feed
        if item.get("overall_sentiment_score") is not None
    ]
    average = sum(scores) / len(scores) if scores else None

    lines = [f"{ticker} 近期新闻 {len(feed)} 条（API 共 {data.get('items', '?')} 条）"]
    if average is not None:
        label = "偏正面" if average > 0.1 else ("偏负面" if average < -0.1 else "中性")
        lines.append(f"平均情绪 {average:.2f}（{label}）")
    lines.append("主要标题：")
    for item in feed[:5]:
        score = item.get("overall_sentiment_score")
        sentiment = item.get("overall_sentiment_label")
        lines.append(
            f"- [{sentiment}] {item.get('title')}"
            f"（{item.get('source')}，情绪 {score}）"
        )
    return "\n".join(lines)


def register(registry) -> None:
    """把本工具注册进 registry。"""
    registry.register(
        name=SPEC.name,
        description=SPEC.description,
        parameters=SPEC.parameters,
        impl=impl,
    )
