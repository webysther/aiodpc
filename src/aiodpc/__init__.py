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
from .exceptions import (
    DpcConnectionError,
    DpcError,
    DpcLocationError,
    DpcNoDataError,
    DpcParseError,
)
from .maps import CriticalityMap, VigilanceMap
from .models import (
    AlertLevel,
    AlertZone,
    BulletinKind,
    CriticalityBulletin,
    CriticalityDay,
    Day,
    Location,
    Phenomenon,
    PhenomenonCategory,
    PhenomenonType,
    Precipitation,
    Risk,
    RiskAssessment,
    RiskType,
    VigilanceBulletin,
    VigilanceDay,
    rome_date,
)
from .monitor import MonitoredLocation

__version__ = "0.6.0"

__all__ = [
    "ATTRIBUTION",
    "CRITICALITY_PAGE_URL",
    "DEFAULT_PHENOMENA_RADIUS_KM",
    "DEFAULT_REQUEST_TIMEOUT",
    "ROME_TZ",
    "VIGILANCE_PAGE_URL",
    "AlertLevel",
    "AlertZone",
    "BulletinIdSource",
    "BulletinKind",
    "CriticalityBulletin",
    "CriticalityDay",
    "CriticalityMap",
    "Day",
    "DpcClient",
    "DpcConnectionError",
    "DpcError",
    "DpcLocationError",
    "DpcNoDataError",
    "DpcParseError",
    "Location",
    "MapPageIdSource",
    "MonitoredLocation",
    "Phenomenon",
    "PhenomenonCategory",
    "PhenomenonType",
    "Precipitation",
    "Risk",
    "RiskAssessment",
    "RiskType",
    "TextFetcher",
    "VigilanceBulletin",
    "VigilanceDay",
    "VigilanceMap",
    "__version__",
    "rome_date",
]
