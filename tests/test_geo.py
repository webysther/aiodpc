"""Tests of the geometry helpers."""

from __future__ import annotations

import math

import pytest

from aiodpc.geo import (
    calculate_initial_compass_bearing,
    distance_km,
    distance_to_area_km,
    point_in_area,
)

SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [[12.0, 41.5], [13.0, 41.5], [13.0, 42.3], [12.0, 42.3], [12.0, 41.5]]
    ],
}


@pytest.mark.parametrize(
    ("point_b", "expected"),
    [
        ((1.0, 0.0), ("N", 0)),
        ((1.0, 1.0), ("NE", 44)),
        ((0.0, 1.0), ("E", 90)),
        ((-1.0, 0.0), ("S", 180)),
        ((0.0, -1.0), ("W", 270)),
        ((1.0, -0.01), ("N", 359)),
        ((1.0, -0.5), ("NNW", 333)),
        ((0.0, 0.0), ("N", 0)),
    ],
)
def test_compass_bearing(
    point_b: tuple[float, float], expected: tuple[str, int]
) -> None:
    """Test the compass point and degrees from the origin to a point."""
    assert calculate_initial_compass_bearing((0.0, 0.0), point_b) == expected


def test_distance() -> None:
    """Test the great-circle distance between Rome and Milan."""
    assert distance_km((41.9028, 12.4964), (45.4642, 9.19)) == pytest.approx(
        477.0, abs=1.0
    )


@pytest.mark.parametrize(
    ("latitude", "longitude", "expected"),
    [(41.9, 12.5, True), (42.3, 12.5, True), (45.0, 9.0, False)],
)
def test_point_in_polygon(latitude: float, longitude: float, expected: bool) -> None:  # noqa: FBT001
    """Test points inside, on the boundary and outside a polygon."""
    assert point_in_area(latitude, longitude, SQUARE) is expected


def test_point_in_multipolygon() -> None:
    """Test a point inside the second polygon of a MultiPolygon."""
    far = [[[8.5, 45.2], [9.6, 45.2], [9.6, 46.0], [8.5, 46.0], [8.5, 45.2]]]
    geometry = {"type": "MultiPolygon", "coordinates": [far, SQUARE["coordinates"]]}

    assert point_in_area(41.9, 12.5, geometry)


def test_point_never_in_other_geometries() -> None:
    """Test that a Point geometry never contains a location."""
    assert not point_in_area(41.9, 12.5, {"type": "Point", "coordinates": [12.5, 41.9]})


@pytest.mark.parametrize(("latitude", "longitude"), [(41.9, 12.5), (42.3, 12.5)])
def test_distance_inside_area(latitude: float, longitude: float) -> None:
    """Test that a point inside an area or on its boundary is at 0 km."""
    assert distance_to_area_km(latitude, longitude, SQUARE) == 0


@pytest.mark.parametrize(
    ("point", "nearest"),
    [
        # North of an edge, 40 km from its nearest vertex
        ((42.4, 12.5), (42.3, 12.5)),
        ((41.9, 13.1), (41.9, 13.0)),
        ((42.4, 13.1), (42.3, 13.0)),
        ((44.0, 12.5), (42.3, 12.5)),
    ],
)
def test_distance_to_area(
    point: tuple[float, float], nearest: tuple[float, float]
) -> None:
    """Test the distance from outside to the nearest point of the boundary."""
    assert distance_to_area_km(*point, SQUARE) == pytest.approx(
        distance_km(point, nearest), rel=0.01
    )


def test_distance_to_multipolygon() -> None:
    """Test the distance to the nearest polygon of a MultiPolygon."""
    far = [[[8.5, 45.2], [9.6, 45.2], [9.6, 46.0], [8.5, 46.0], [8.5, 45.2]]]
    geometry = {"type": "MultiPolygon", "coordinates": [far, SQUARE["coordinates"]]}

    assert distance_to_area_km(42.4, 12.5, geometry) == distance_to_area_km(
        42.4, 12.5, SQUARE
    )


def test_distance_with_a_repeated_vertex() -> None:
    """Test a boundary that repeats a vertex: a segment without length."""
    (ring,) = SQUARE["coordinates"]
    geometry = {"type": "Polygon", "coordinates": [[ring[0], *ring]]}

    assert distance_to_area_km(42.4, 12.5, geometry) == distance_to_area_km(
        42.4, 12.5, SQUARE
    )


def test_distance_to_other_geometries() -> None:
    """Test that a Point geometry is never near."""
    point = {"type": "Point", "coordinates": [12.5, 41.9]}

    assert distance_to_area_km(41.9, 12.5, point) == math.inf
