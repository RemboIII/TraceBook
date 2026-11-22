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


def _simplify_path_with_times(
    coords: list[tuple[float, float]],
    times: list[str],
    min_m: float = 1.2,
    max_points: int = 1600,
) -> tuple[list[list[float]], list[str]]:
    """Simplify a path while keeping one timestamp per coordinate."""
    if not coords:
        return [], []
    if len(times) != len(coords):
        times = [""] * len(coords)

    kept: list[tuple[float, float]] = [coords[0]]
    kept_times: list[str] = [times[0]]
    for coord, stamp in zip(coords[1:], times[1:], strict=False):
        if _distance_m(kept[-1], coord) >= min_m:
            kept.append(coord)
            kept_times.append(stamp)

    if kept[-1] != coords[-1]:
        kept.append(coords[-1])
        kept_times.append(times[-1])

    if len(kept) > max_points:
        step = len(kept) / max_points
        sampled: list[tuple[float, float]] = []
        sampled_times: list[str] = []
        for index in range(max_points - 1):
            position = min(int(index * step), len(kept) - 1)
            sampled.append(kept[position])
            sampled_times.append(kept_times[position])
        sampled.append(kept[-1])
        sampled_times.append(kept_times[-1])
        kept = sampled
        kept_times = sampled_times

    return (
        [[round(lat, 5), round(lng, 5)] for lat, lng in kept],
        kept_times,
    )


def _smooth_path(
    coords: list[tuple[float, float]], passes: int = 1
) -> list[tuple[float, float]]:
    """Lightly smooth GPS jitter without moving the endpoints."""
    if len(coords) < 3 or passes <= 0:
        return coords
    result = [(float(lat), float(lng)) for lat, lng in coords]
    for _ in range(passes):
        smoothed = [result[0]]
        for index in range(1, len(result) - 1):
            previous = result[index - 1]
            current = result[index]
            following = result[index + 1]
            smoothed.append(
                (
                    (previous[0] + 2 * current[0] + following[0]) / 4,
                    (previous[1] + 2 * current[1] + following[1]) / 4,
                )
            )
        smoothed.append(result[-1])
        result = smoothed
    return result
