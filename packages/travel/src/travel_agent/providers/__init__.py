"""旅行数据源适配器。"""

from .location_resolver import LocationResolutionError, resolve
from .open_meteo import forecast, geocode
from .wikipedia import search, search_locations

__all__ = [
    "LocationResolutionError",
    "forecast",
    "geocode",
    "resolve",
    "search",
    "search_locations",
]
