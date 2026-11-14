"""Tests of the other names of the municipalities."""

from __future__ import annotations

import pytest

from aiodpc.municipalities import MUNICIPALITY_NAMES, municipality_names, normalize


def test_each_name_belongs_to_one_municipality() -> None:
    """Test that no name is in two groups, which would merge municipalities."""
    names = [normalize(name) for group in MUNICIPALITY_NAMES for name in group]

    assert len(names) == len(set(names))


def test_each_group_has_other_names() -> None:
    """Test that every group gives a municipality at least one other name."""
    assert all(
        len({normalize(name) for name in group}) > 1 for group in MUNICIPALITY_NAMES
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Bozen", {"bolzano", "bozen"}),
        ("Bolzano/Bozen", {"bolzano", "bozen"}),
        (
            " Rasun Anterselva ",
            {"rasun-anterselva", "rasen-antholz", "rasun anterselva"},
        ),
        ("  ROMA ", {"roma"}),
        # "Corvara" is also a municipality of Abruzzo: not another name
        ("Corvara in Badia/Corvara", {"corvara in badia", "corvara"}),
        ("Corvara", {"corvara"}),
        ("Bolzano / ", {"bolzano", "bozen"}),
    ],
)
def test_municipality_names(name: str, expected: set[str]) -> None:
    """Test every name of a municipality, normalized."""
    assert municipality_names(name) == expected
