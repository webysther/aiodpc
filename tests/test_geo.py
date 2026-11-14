"""Tests of the geometry helpers."""

from __future__ import annotations

import pytest

from aiodpc.geo import calculate_initial_compass_bearing, distance_km, point_in_area

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
