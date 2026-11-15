"""Geometry helpers on (latitude, longitude) points and GeoJSON geometries."""

from __future__ import annotations

import math
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Final

from geojson_utils import point_distance, point_in_polygon

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

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

EARTH_RADIUS_KM: Final = 6371.0088
"""Mean radius of the Earth."""

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


def distance_to_area_km(
    latitude: float, longitude: float, geometry: Mapping[str, Any]
) -> float:
    """Return the distance in km from a point to a Polygon or MultiPolygon.

    It is 0 inside the area or on its boundary, and infinite for other geometry
    types. Outside, it is the distance to the nearest edge on a plane tangent at
    the point, within about 1% up to a few hundred km.
    """
    if geometry.get("type") not in _AREA_TYPES:
        return math.inf
    if point_in_area(latitude, longitude, geometry):
        return 0.0
    km_per_radian_of_longitude = EARTH_RADIUS_KM * math.cos(math.radians(latitude))

    def plane(position: Sequence[float]) -> tuple[float, float]:
        """Return a GeoJSON position on the plane, in km from the point."""
        return (
            math.radians(position[0] - longitude) * km_per_radian_of_longitude,
            math.radians(position[1] - latitude) * EARTH_RADIUS_KM,
        )

    return min(
        (
            _distance_from_origin(start, end)
            for ring in _rings(geometry)
            for start, end in pairwise(map(plane, ring))
        ),
        default=math.inf,
    )


def _rings(geometry: Mapping[str, Any]) -> Iterator[Sequence[Sequence[float]]]:
    """Yield the rings of a Polygon or MultiPolygon: its outlines and holes."""
    polygons = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        polygons = [polygons]
    for polygon in polygons:
        yield from polygon


def _distance_from_origin(
    start: tuple[float, float], end: tuple[float, float]
) -> float:
    """Return the distance from the origin to a segment of the plane."""
    (x, y), (dx, dy) = start, (end[0] - start[0], end[1] - start[1])
    length_squared = dx * dx + dy * dy
    # Fraction of the segment where it is nearest to the origin
    t = 0.0 if length_squared == 0 else -(x * dx + y * dy) / length_squared
    t = min(1.0, max(0.0, t))
    return math.hypot(x + t * dx, y + t * dy)


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
