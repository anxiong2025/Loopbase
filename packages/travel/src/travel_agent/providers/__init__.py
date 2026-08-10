"""旅行数据源适配器。"""

from .open_meteo import forecast, geocode
from .wikipedia import search

__all__ = ["forecast", "geocode", "search"]
