"""The preview images of the national maps that DPC publishes for each day.

Each day of a bulletin has the preview of its national map (``image_url`` of
:class:`~aiodpc.CriticalityDay` and :class:`~aiodpc.VigilanceDay`), a PNG of
700 x 900 pixels. The DPC pipeline often publishes it blank, a single white
color, and DPC sometimes replaces it later at the same address. Measured on
every preview from 2026-08-02 to 2026-11-16:

- criticality: 88 of 220 published blank; 33 replaced after 7 to 227 minutes
  (median 113), 55 never;
- vigilance: 10 of 214 published blank; 2 replaced after 184 minutes, 8 never.

Every blank preview was a white PNG of 4475 bytes, RGB or RGBA, not
interlaced; the smallest map was 75 KB. :func:`is_blank_preview` tells them
apart without decoding the image: it checks that each compressed row is the
one a single color gives, so it needs no imaging library and stays fast.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterator

PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
"""The first bytes of every PNG file (PNG specification, section 5.2)."""

_CHUNK_HEADER: Final = struct.Struct(">I4s")
"""Length and type of a PNG chunk; its data and a 4-byte CRC follow."""

_CRC_SIZE: Final = 4

_IHDR: Final = struct.Struct(">IIBBBBB")
"""Width, height, bit depth, color type, compression, filter and interlace
methods of a PNG (PNG specification, section 11.2.2)."""

_SAMPLES_PER_PIXEL: Final = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
"""Samples of a pixel by PNG color type: grayscale, RGB, palette index,
grayscale and alpha, RGBA (PNG specification, table 11.1)."""

_BYTE_BITS: Final = 8

_READABLE_BIT_DEPTHS: Final = frozenset({8, 16})
"""Bits per sample whose pixels are whole bytes. Fewer bits pack several
pixels in a byte, and are not read: no DPC preview has them."""

_NOT_INTERLACED: Final = 0


class _Filter(IntEnum):
    """How a row of a PNG is written (PNG specification, section 7.3).

    Each byte is written as its difference from a prediction: the byte of the
    pixel on its left, above it, or both.
    """

    NONE = 0
    SUB = 1
    UP = 2
    AVERAGE = 3
    PAETH = 4


@dataclass(frozen=True, slots=True)
class _Png:
    """The rows of a PNG, still filtered, with what it takes to read them."""

    width: int
    height: int
    pixel_size: int
    """Bytes of a pixel: the unit of the filters."""
    rows: bytes
    """The decompressed image data: each row is its filter type, then its bytes."""


def is_blank_preview(png: bytes) -> bool:
    """Return whether a preview image is blank: a PNG of a single color.

    Only a PNG that can be read in full is blank. One with fewer than 8 bits
    per sample, interlaced, damaged, or that is no PNG at all is not: shown as
    it is, at worst it shows what DPC published.
    """
    image = _read_png(png)
    return image is not None and _has_a_single_color(image)


def _chunks(png: bytes) -> Iterator[tuple[bytes, bytes]]:
    """Yield the type and the data of each chunk of a PNG, up to its end.

    Raises ValueError when a chunk is cut short.
    """
    position = len(PNG_SIGNATURE)
    while position < len(png):
        length, kind = _CHUNK_HEADER.unpack_from(png, position)
        start = position + _CHUNK_HEADER.size
        end = start + length
        if end + _CRC_SIZE > len(png):
            msg = f"PNG chunk {kind!r} is cut short"
            raise ValueError(msg)
        yield kind, png[start:end]
        if kind == b"IEND":
            return
        position = end + _CRC_SIZE


def _read_png(png: bytes) -> _Png | None:
    """Return the rows of a PNG, or None when it cannot be read in full."""
    if not png.startswith(PNG_SIGNATURE):
        return None
    header: bytes | None = None
    data: list[bytes] = []
    try:
        for kind, chunk in _chunks(png):
            if kind == b"IHDR":
                header = chunk
            elif kind == b"IDAT":
                data.append(chunk)
        if header is None:
            return None
        width, height, bit_depth, color_type, _, _, interlace = _IHDR.unpack(header)
        rows = zlib.decompress(b"".join(data))
    except (ValueError, struct.error, zlib.error):
        return None
    samples = _SAMPLES_PER_PIXEL.get(color_type)
    if (
        samples is None
        or bit_depth not in _READABLE_BIT_DEPTHS
        or interlace != _NOT_INTERLACED
        or width == 0
        or height == 0
    ):
        return None
    image = _Png(width, height, samples * bit_depth // _BYTE_BITS, rows)
    return image if len(rows) == height * (1 + width * image.pixel_size) else None


def _single_color_rows(
    pixel: bytes, width: int
) -> tuple[dict[int, bytes], dict[int, bytes]]:
    """Return the rows each filter writes for an image of a single color.

    The first, with nothing above it; then the others, with the same pixel
    above. The filters subtract from each byte its prediction, modulo 256: the
    byte on its left (Sub), above it (Up), their mean (Average) or the
    nearest of the left, above and upper left (Paeth); outside the image, 0.
    """
    rest = width - 1
    zeros = bytes(len(pixel) * rest)
    # A byte less half of itself, rounded down: Average, against one neighbor
    half = bytes(sample - (sample >> 1) for sample in pixel)
    first: dict[int, bytes] = {
        _Filter.NONE: pixel * width,
        _Filter.SUB: pixel + zeros,
        _Filter.UP: pixel * width,
        _Filter.AVERAGE: pixel + half * rest,
        _Filter.PAETH: pixel + zeros,
    }
    others: dict[int, bytes] = {
        _Filter.NONE: pixel * width,
        _Filter.SUB: pixel + zeros,
        _Filter.UP: bytes(len(pixel) * width),
        _Filter.AVERAGE: half + zeros,
        _Filter.PAETH: bytes(len(pixel) * width),
    }
    return first, others


def _has_a_single_color(image: _Png) -> bool:
    """Return whether every pixel of a PNG is its first pixel.

    Any filter writes the first pixel as it is, with nothing on its left nor
    above it. A single color gives each row a single possible content for its
    filter: comparing the rows to it reads the image without decoding it.
    """
    row_size = 1 + image.width * image.pixel_size
    pixel = image.rows[1 : 1 + image.pixel_size]
    first, others = _single_color_rows(pixel, image.width)
    for row in range(image.height):
        start = row * row_size
        expected = (first if row == 0 else others).get(image.rows[start])
        if expected is None or image.rows[start + 1 : start + row_size] != expected:
            return False
    return True
