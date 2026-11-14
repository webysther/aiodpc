"""Async client for the Italian Civil Protection Department (DPC) bulletins.

It reads the national "Bollettino di criticità idrogeologica e idraulica"
(alert levels per risk) and "Bollettino di vigilanza meteorologica" (weather
vigilance and phenomena) published by DPC as open data.
"""

from .client import DpcClient
from .const import (
    ATTRIBUTION,
    CRITICALITY_PAGE_URL,
    DEFAULT_PHENOMENA_RADIUS_KM,
    DEFAULT_REQUEST_TIMEOUT,
    ROME_TZ,
    VIGILANCE_PAGE_URL,
)
from .discovery import BulletinIdSource, MapPageIdSource, TextFetcher
from .exceptions import DpcConnectionError, DpcError, DpcLocationError, DpcParseError
from .models import (
    AlertLevel,
    Assessment,
    BulletinKind,
    CriticalityBulletin,
    CriticalityDay,
    Phenomenon,
    PhenomenonCategory,
    Risk,
    VigilanceBulletin,
    VigilanceDay,
    rome_date,
)

__version__ = "0.1.0"

__all__ = [
    "ATTRIBUTION",
    "CRITICALITY_PAGE_URL",
    "DEFAULT_PHENOMENA_RADIUS_KM",
    "DEFAULT_REQUEST_TIMEOUT",
    "ROME_TZ",
    "VIGILANCE_PAGE_URL",
    "AlertLevel",
    "Assessment",
    "BulletinIdSource",
    "BulletinKind",
    "CriticalityBulletin",
    "CriticalityDay",
    "DpcClient",
    "DpcConnectionError",
    "DpcError",
    "DpcLocationError",
    "DpcParseError",
    "MapPageIdSource",
    "Phenomenon",
    "PhenomenonCategory",
    "Risk",
    "TextFetcher",
    "VigilanceBulletin",
    "VigilanceDay",
    "__version__",
    "rome_date",
]
