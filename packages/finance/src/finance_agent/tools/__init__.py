"""金融领域工具集：每个工具一个模块（SPEC + impl + register）。"""

from . import get_financials, get_income_statement, get_news_sentiment, get_stock_price

__all__ = ["register_all"]


def register_all(registry) -> None:
    """把金融领域全部工具注册进 registry。"""
    get_stock_price.register(registry)
    get_financials.register(registry)
    get_income_statement.register(registry)
    get_news_sentiment.register(registry)
