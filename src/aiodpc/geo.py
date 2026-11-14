"""Geometry helpers on (latitude, longitude) points and GeoJSON geometries."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Final

from geojson_utils import point_distance, point_in_polygon

if TYPE_CHECKING:
    from collections.abc import Mapping

COMPASS_POINTS: Final = (
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
)

_AREA_TYPES: Final = frozenset({"Polygon", "MultiPolygon"})


def geojson_point(latitude: float, longitude: float) -> dict[str, Any]:
    """Return a GeoJSON Point (GeoJSON orders coordinates as longitude, latitude)."""
    return {"type": "Point", "coordinates": [longitude, latitude]}


def point_in_area(
    latitude: float, longitude: float, geometry: Mapping[str, Any]
) -> bool:
    """Return whether a point is inside a Polygon or MultiPolygon geometry.

    Points on the boundary count as inside; other geometry types never
    contain a point.
    """
    if geometry.get("type") not in _AREA_TYPES:
        return False
    return bool(point_in_polygon(geojson_point(latitude, longitude), dict(geometry)))


def distance_km(point_a: tuple[float, float], point_b: tuple[float, float]) -> float:
    """Return the great-circle distance in km between two (lat, lon) points."""
    meters = point_distance(geojson_point(*point_a), geojson_point(*point_b))
    return float(meters) / 1000


def calculate_initial_compass_bearing(
    point_a: tuple[float, float], point_b: tuple[float, float]
) -> tuple[str, int]:
    """Return the compass point and degrees from point_a to point_b (lat, lon).

    Credits: https://gist.github.com/jeromer/2005586
    and https://gist.github.com/RobertSudwarts/acf8df23a16afdb5837f
    """
    lat1 = math.radians(point_a[0])
    lat2 = math.radians(point_b[0])
    diff_long = math.radians(point_b[1] - point_a[1])
    x = math.sin(diff_long) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (
        math.sin(lat1) * math.cos(lat2) * math.cos(diff_long)
    )
    compass_bearing = (math.degrees(math.atan2(x, y)) + 360) % 360
    index = round(compass_bearing / (360.0 / len(COMPASS_POINTS)))
    return COMPASS_POINTS[index % len(COMPASS_POINTS)], math.floor(compass_bearing)
