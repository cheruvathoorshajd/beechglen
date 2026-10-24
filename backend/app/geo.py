"""Geospatial helpers.

Thin wrapper over h3 v4 so the rest of the codebase never touches the h3 API
directly, and exact distance is always haversine rather than an H3 ring
approximation.
"""

from __future__ import annotations

import math

import h3

#: H3 resolution 9 averages roughly 174 m edge length, a good fit for the
#: 400-2000 m search radii Nexus911 uses.
H3_RESOLUTION = 9

#: Approximate metres covered by one H3 resolution-9 ring step.
_RING_METRES = 300.0

EARTH_RADIUS_M = 6_371_000.0


def cell_for(lat: float, lng: float, resolution: int = H3_RESOLUTION) -> str:
    """H3 cell containing ``(lat, lng)``."""
    return h3.latlng_to_cell(lat, lng, resolution)


def cell_center(cell: str) -> tuple[float, float]:
    """Centre of an H3 cell as ``(lat, lng)``."""
    return h3.cell_to_latlng(cell)


def ring_k_for_radius(radius_m: float) -> int:
    """Number of H3 ring steps that safely covers ``radius_m``.

    Deliberately over-covers by one ring; exact filtering is done with
    :func:`haversine_m` afterwards.
    """
    return math.ceil(radius_m / _RING_METRES) + 1


def cells_within(lat: float, lng: float, radius_m: float, resolution: int = H3_RESOLUTION) -> set[str]:
    """Every H3 cell that could hold a point within ``radius_m``."""
    origin = cell_for(lat, lng, resolution)
    return set(h3.grid_disk(origin, ring_k_for_radius(radius_m)))


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in metres between two ``(lat, lng)`` pairs."""
    lat1, lng1 = a
    lat2, lng2 = b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, h)))


def nearest(
    target: tuple[float, float],
    candidates: list[tuple[float, float]],
) -> int | None:
    """Index of the candidate closest to ``target``, or None when empty."""
    if not candidates:
        return None
    return min(range(len(candidates)), key=lambda i: haversine_m(target, candidates[i]))
