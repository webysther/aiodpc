"""Tests of the blank preview images of the national maps."""

from __future__ import annotations

import struct
import zlib
from typing import TYPE_CHECKING

import pytest

from aiodpc.previews import PNG_SIGNATURE, is_blank_preview

from . import FIXTURES

if TYPE_CHECKING:
    from collections.abc import Sequence

WHITE: bytes = b"\xff\xff\xff\xff"
GRAY: bytes = b"\x80\x7f\x01\xfe"
"""An RGBA color whose samples differ, odd and even, to exercise each filter."""

FILTERS: Sequence[int] = range(5)
"""None, Sub, Up, Average and Paeth (PNG specification, section 7.3)."""


def _paeth(left: int, above: int, upper_left: int) -> int:
    """Return the Paeth predictor: the nearest of the three to their estimate."""
    estimate = left + above - upper_left
    distances = (
        abs(estimate - left),
        abs(estimate - above),
        abs(estimate - upper_left),
    )
    return (left, above, upper_left)[distances.index(min(distances))]


def _filtered(kind: int, row: bytes, above: bytes, pixel_size: int) -> bytes:
    """Return a row of an image written with a filter, as a PNG encoder does."""
    written = bytearray()
    for index, sample in enumerate(row):
        left = row[index - pixel_size] if index >= pixel_size else 0
        upper_left = above[index - pixel_size] if index >= pixel_size else 0
        prediction = (
            0,
            left,
            above[index],
            (left + above[index]) >> 1,
            _paeth(left, above[index], upper_left),
        )[kind]
        written.append((sample - prediction) & 0xFF)
    return bytes(written)


def _chunk(kind: bytes, data: bytes) -> bytes:
    """Return a PNG chunk: length, type, data and CRC."""
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data))
    )


def _png_of(
    image_data: bytes,
    *,
    width: int,
    height: int,
    color_type: int = 6,
    bit_depth: int = 8,
    interlace: int = 0,
) -> bytes:
    """Return a PNG of its header and its compressed image data."""
    header = struct.pack(
        ">IIBBBBB", width, height, bit_depth, color_type, 0, 0, interlace
    )
    return (
        PNG_SIGNATURE
        + _chunk(b"IHDR", header)
        + _chunk(b"tEXt", b"Software\x00aiodpc tests")
        + _chunk(b"IDAT", image_data)
        + _chunk(b"IEND", b"")
    )


def _png(
    rows: Sequence[bytes],
    *,
    filters: Sequence[int],
    pixel_size: int = 4,
    color_type: int = 6,
    bit_depth: int = 8,
    interlace: int = 0,
) -> bytes:
    """Return a PNG of rows of pixels, each row written with its filter."""
    above = bytes(len(rows[0]))
    data = bytearray()
    for row, kind in zip(rows, filters, strict=True):
        data += bytes([kind]) + _filtered(kind, row, above, pixel_size)
        above = row
    return _png_of(
        zlib.compress(bytes(data)),
        width=len(rows[0]) // pixel_size,
        height=len(rows),
        color_type=color_type,
        bit_depth=bit_depth,
        interlace=interlace,
    )


def _single_color(pixel: bytes, filters: Sequence[int], width: int = 3) -> bytes:
    """Return a PNG of a single color, a row per filter."""
    return _png([pixel * width] * len(filters), filters=filters, pixel_size=len(pixel))


@pytest.mark.parametrize("pixel", [WHITE, GRAY, b"\x00\x00\x00\x00"])
@pytest.mark.parametrize("kind", FILTERS)
def test_a_single_color_is_blank_whatever_the_filter(pixel: bytes, kind: int) -> None:
    """Test that every filter writes a single color as blank, first row or not."""
    assert is_blank_preview(_single_color(pixel, [kind, kind, kind]))


def test_a_single_color_is_blank_whatever_filters_its_rows_mix() -> None:
    """Test a blank image whose rows each have another filter, as encoders choose."""
    assert is_blank_preview(_single_color(GRAY, [4, 0, 3, 1, 2, 4, 3]))


@pytest.mark.parametrize("kind", FILTERS)
def test_another_color_is_not_blank_whatever_the_filter(kind: int) -> None:
    """Test that a pixel of another color, in any row, is found."""
    for row in range(3):
        rows = [GRAY * 3] * 3
        rows[row] = GRAY * 2 + WHITE
        assert not is_blank_preview(_png(rows, filters=[kind] * 3))


@pytest.mark.parametrize(
    ("color_type", "bit_depth", "pixel"),
    [
        (0, 8, b"\xff"),  # grayscale
        (0, 16, b"\xff\x7f"),  # grayscale, 16 bits per sample
        (2, 8, b"\xff\xff\xff"),  # RGB
        (3, 8, b"\x02"),  # palette index
        (4, 8, b"\x80\xff"),  # grayscale and alpha
        (6, 16, b"\x80\x7f" * 4),  # RGBA, 16 bits per sample
    ],
)
def test_a_single_color_is_blank_in_any_color_type(
    color_type: int, bit_depth: int, pixel: bytes
) -> None:
    """Test the color types and bit depths whose pixels are whole bytes."""
    rows = [pixel * 4] * 3
    assert is_blank_preview(
        _png(
            rows,
            filters=[1, 3, 4],
            pixel_size=len(pixel),
            color_type=color_type,
            bit_depth=bit_depth,
        )
    )


def test_a_single_pixel_is_blank() -> None:
    """Test an image of one pixel, with nothing beside nor above it."""
    assert is_blank_preview(_single_color(GRAY, [3], width=1))


@pytest.mark.parametrize(
    "header",
    [
        {"bit_depth": 4, "color_type": 3, "pixel_size": 1},  # packed pixels
        {"interlace": 1},
        {"color_type": 5},  # no such color type
    ],
)
def test_what_cannot_be_read_is_not_blank(header: dict[str, int]) -> None:
    """Test that a PNG read only in part is shown as it is."""
    assert not is_blank_preview(_png([WHITE * 2] * 2, filters=[0, 0], **header))


def test_a_damaged_png_is_not_blank() -> None:
    """Test damaged images, and what is no PNG at all."""
    blank = _single_color(WHITE, [0, 0])
    ihdr_size = 4 + 4 + 13 + 4  # length, type, header, CRC
    two_rows = b"\x00" + WHITE * 3 + b"\x00" + WHITE * 3
    for data in (
        b"<html>Not found</html>",
        blank[:40],  # cut in the header of a chunk
        blank[:60],  # cut in the data of a chunk
        PNG_SIGNATURE + blank[len(PNG_SIGNATURE) + ihdr_size :],  # no header
        _png_of(b"not zlib", width=3, height=2),
        _png_of(
            zlib.compress(b"\x05" + WHITE * 3), width=3, height=1
        ),  # no such filter
        _png_of(zlib.compress(two_rows[:-1]), width=3, height=2),  # rows too short
        _png([b""], filters=[0]),  # no pixel
    ):
        assert not is_blank_preview(data)


def test_a_png_without_its_end_is_read() -> None:
    """Test that the image data is enough, even without the end chunk."""
    end_chunk_size = 4 + 4 + 4
    assert is_blank_preview(_single_color(WHITE, [0, 0])[:-end_chunk_size])


def test_the_real_previews() -> None:
    """Test a preview DPC published blank, and the map that replaced it."""
    real = FIXTURES / "real"
    assert is_blank_preview(
        (real / "preview_20261115_1421_oggi_blank.png").read_bytes()
    )
    assert not is_blank_preview((real / "preview_20261115_1421_oggi.png").read_bytes())
