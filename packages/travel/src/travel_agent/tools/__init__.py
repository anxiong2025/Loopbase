"""旅行攻略工具集：每个工具独立定义 Schema、实现和注册函数。"""

from . import calculate_distance, calculate_trip_budget, get_weather, search_places

__all__ = ["register_all"]


def register_all(registry) -> None:
    get_weather.register(registry)
    search_places.register(registry)
    calculate_distance.register(registry)
    calculate_trip_budget.register(registry)
