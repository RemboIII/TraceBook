"""Small geometry helpers shared by the timeline builders."""

from __future__ import annotations

from datetime import datetime
from math import cos, radians


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Approximate distance in metres between two (lat, lng) tuples."""
    lat = radians((a[0] + b[0]) / 2)
    dx = (b[1] - a[1]) * 111_320 * cos(lat)
    dy = (b[0] - a[0]) * 110_540
    return (dx * dx + dy * dy) ** 0.5


def _simplify_path(
    coords: list[tuple[float, float]], min_m: float = 1.2, max_points: int = 1600
) -> list[list[float]]:
    """Remove GPS noise and cap the number of points sent to the browser."""
    if not coords:
        return []

    kept: list[tuple[float, float]] = [coords[0]]
    for coord in coords[1:]:
        if _distance_m(kept[-1], coord) >= min_m:
            kept.append(coord)

    if kept[-1] != coords[-1]:
        kept.append(coords[-1])

    if len(kept) > max_points:
        step = len(kept) / max_points
        sampled = [kept[min(int(i * step), len(kept) - 1)] for i in range(max_points - 1)]
        sampled.append(kept[-1])
        kept = sampled

    return [[round(lat, 5), round(lng, 5)] for lat, lng in kept]


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
