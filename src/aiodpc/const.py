"""Constants of the DPC open data."""

from __future__ import annotations

from typing import Final
from zoneinfo import ZoneInfo

ROME_TZ: Final = ZoneInfo("Europe/Rome")
"""Time zone of the bulletins: their days are Italian calendar days."""

ATTRIBUTION: Final = (
    "Dipartimento della Protezione Civile – Presidenza del Consiglio dei Ministri"  # noqa: RUF001
)
"""Attribution required by the CC BY 4.0 license of the DPC data."""

CRITICALITY_PAGE_URL: Final = (
    "https://mappe.protezionecivile.gov.it/it/mappe-rischi/bollettino-di-criticita/"
)
"""Map page of the criticality bulletin ("Bollettino di criticità")."""

VIGILANCE_PAGE_URL: Final = (
    "https://mappe.protezionecivile.gov.it/it/mappe-rischi/bollettino-di-vigilanza/"
)
"""Map page of the weather vigilance bulletin ("Bollettino di vigilanza")."""

CRITICALITY_FILES_URL: Final = (
    "https://raw.githubusercontent.com/pcm-dpc/"
    "DPC-Bollettini-Criticita-Idrogeologica-Idraulica/master/files"
)
"""Base URL of the criticality bulletin files published by DPC on GitHub."""

VIGILANCE_FILES_URL: Final = (
    "https://raw.githubusercontent.com/pcm-dpc/"
    "DPC-Bollettini-Vigilanza-Meteorologica/master/files"
)
"""Base URL of the vigilance bulletin files published by DPC on GitHub."""

DEFAULT_REQUEST_TIMEOUT: Final = 30.0
"""Default timeout of each HTTP request, in seconds."""

DEFAULT_PHENOMENA_RADIUS_KM: Final = 50.0
"""Default radius around the location to report weather phenomena, in km."""
