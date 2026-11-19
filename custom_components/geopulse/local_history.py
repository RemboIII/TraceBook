"""Build timeline days from the local archive instead of the recorder.

The heavy lifting (zones, GPS stays, journeys, mode estimation) already exists
in :mod:`ha_history`.  This module feeds it archive points, gives every visit
and journey a stable key, and keeps user edits in locked day snapshots.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time as dt_time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant

from .archive import Archive, stable_key
from .geo import _distance_m
from .const import MODE_COLORS
from .ha_history import (
    Point,
    _async_apply_geocoding,
    _build_day,
    _zone_lookup,
)

_LOGGER = logging.getLogger(__name__)

POI_RADIUS_M = 75


def _point_state(latitude: float, longitude: float, zones) -> str:
    """Return the zone name for a coordinate, or an empty string."""
    for zone in zones.values():
        if zone.latitude is None or zone.longitude is None:
            continue
        if _distance_m((latitude, longitude), (zone.latitude, zone.longitude)) <= zone.radius:
            return zone.name
    return ""


def _archive_places(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adapt archive places to the shape ha_history expects."""
    result = []
    for place in places:
        result.append(
            {
                "id": place.get("id"),
                "name": place.get("name"),
                "latitude": place.get("lat"),
                "longitude": place.get("lon"),
            }
        )
    return result


def _rekey_day(
    hass: HomeAssistant,
    entity_id: str,
    day_payload: dict[str, Any],
) -> None:
    """Give entries deterministic keys and mark them editable."""
    zones = _zone_lookup(hass)
    routes_by_track: dict[str, dict[str, Any]] = {}
    for route in day_payload.get("routes") or []:
        track = route.get("track_id")
        if track is not None:
            routes_by_track[str(track)] = route

    for entry in day_payload.get("entries") or []:
        if entry.get("type") == "visit":
            start = str(entry.get("start") or "")
            key = stable_key(
                "local-visit-",
                entity_id,
                start,
                f"{float(entry.get('latitude') or 0):.5f}",
                f"{float(entry.get('longitude') or 0):.5f}",
            )
            entry["key"] = key
            entry["visit_id"] = key
            entry["editable"] = True
            entry["editable_name"] = entry.get("name") or ""
            entry.setdefault("suggested_places", [])
            entry.setdefault("place_id", None)
            entry.setdefault("status", "confirmed")
        elif entry.get("type") == "journey":
            start = str(entry.get("start") or "")
            end = str(entry.get("end") or "")
            key = stable_key("local-journey-", entity_id, start, end)
            old_track_ids = [str(item) for item in (entry.get("track_ids") or [])]
            entry["track_id"] = key
            entry["track_ids"] = [key]
            entry["key"] = key
            entry["editable"] = True
            for old in old_track_ids:
                route = routes_by_track.get(old)
                if route is not None:
                    route["track_id"] = key
            if entry.get("mode") not in MODE_COLORS:
                entry["mode"] = "unknown"
            entry["color"] = MODE_COLORS.get(
                entry["mode"], MODE_COLORS["unknown"]
            )
            for route in day_payload.get("routes") or []:
                if route.get("track_id") == key and route.get("mode") not in MODE_COLORS:
                    route["mode"] = entry["mode"]


def _recompute_summary(payload: dict[str, Any]) -> None:
    entries = payload.get("entries") or []
    journeys = [entry for entry in entries if entry.get("type") == "journey"]
    visits = [entry for entry in entries if entry.get("type") == "visit"]

    mode_totals: dict[str, float] = {}
    distance = 0.0
    moving_seconds = 0.0
    for journey in journeys:
        mode = journey.get("mode") or "unknown"
        value = float(journey.get("distance") or 0)
        distance += value
        moving_seconds += float(journey.get("duration_seconds") or 0)
        if mode not in ("stationary", "unknown", "mixed"):
            mode_totals[mode] = mode_totals.get(mode, 0.0) + value

    stationary_minutes = 0
    for visit in visits:
        stationary_minutes += int(visit.get("duration_minutes") or 0)

    payload["summary"] = {
        "distance": round(distance, 1),
        "unit": "km",
        "places": len({visit.get("name") for visit in visits if visit.get("name")}),
        "moving_minutes": int(round(moving_seconds / 60)),
        "stationary_minutes": stationary_minutes,
        "suggested": 0,
        "confirmed": len(visits),
        "modes": [
            {
                "mode": mode,
                "distance": round(value, 1),
                "color": MODE_COLORS.get(mode, MODE_COLORS["unknown"]),
            }
            for mode, value in sorted(
                mode_totals.items(), key=lambda item: item[1], reverse=True
            )
            if value > 0
        ],
    }


async def _index_visits(archive: Archive, payload: dict[str, Any]) -> None:
    rows: list[dict[str, Any]] = []
    for entry in payload.get("entries") or []:
        if entry.get("type") != "visit":
            continue
        name = str(entry.get("name") or "").strip()
        if not name or name in ("Locatie", "Thuis"):
            continue
        latitude = entry.get("latitude")
        longitude = entry.get("longitude")
        if latitude is None or longitude is None:
            continue
        rows.append(
            {
                "id": f"visit:{entry.get('key')}",
                "name": name,
                "lat": latitude,
                "lon": longitude,
                "address": entry.get("subtitle") or "",
                "source": "visit",
            }
        )
    if rows:
        await archive.async_upsert_place_index(rows)


async def build_local_day(
    hass: HomeAssistant,
    archive: Archive,
    entity_id: str,
    day_str: str,
) -> dict[str, Any]:
    """Derive a fresh (unlocked) day from archived points."""
    tz = ZoneInfo(hass.config.time_zone)
    day = date.fromisoformat(day_str)
    start = datetime.combine(day, dt_time.min, tzinfo=tz)
    end = start + timedelta(days=1) - timedelta(seconds=1)

    rows = await archive.async_points(entity_id, start.timestamp(), end.timestamp())
    zones = _zone_lookup(hass)
    points = [
        Point(
            time=datetime.fromtimestamp(row["ts"], tz),
            latitude=float(row["lat"]),
            longitude=float(row["lon"]),
            state=_point_state(float(row["lat"]), float(row["lon"]), zones),
            speed=float(row["speed"]) if row.get("speed") is not None else None,
        )
        for row in rows
    ]

    places = _archive_places(await archive.async_places(limit=500))
    payload = _build_day(hass, entity_id, day, points, places, tz)
    _rekey_day(hass, entity_id, payload)
    if bool((hass.data.get("geopulse") or {}).get("geocode", True)):
        await _async_apply_geocoding(hass, payload)
    await _index_visits(archive, payload)
    return payload


#: Journeys are re-detected on every build; their start time can drift a
#: little while points are still arriving.  Treat them as the same journey
#: when the starts are within this many seconds.
_JOURNEY_MATCH_SECONDS = 180


def _entry_start_end(
    entry: dict[str, Any],
) -> tuple[datetime | None, datetime | None]:
    """Return the start and end of an entry as datetimes."""
    try:
        start = datetime.fromisoformat(str(entry.get("start")))
    except (TypeError, ValueError):
        start = None
    try:
        end = datetime.fromisoformat(str(entry.get("end")))
    except (TypeError, ValueError):
        end = start
    return start, end


def _overlaps(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    left_start, left_end = _entry_start_end(left)
    right_start, right_end = _entry_start_end(right)
    if left_start is None or right_start is None:
        return False
    if left_end is None:
        left_end = left_start
    if right_end is None:
        right_end = right_start
    return left_start < right_end and left_end > right_start


def _merge_bounds(
    old: list[list[float]] | None,
    fresh: list[list[float]] | None,
) -> list[list[float]] | None:
    points = [point for point in (old or []) + (fresh or []) if len(point) == 2]
    if not points:
        return old or fresh
    return [
        [min(point[0] for point in points), min(point[1] for point in points)],
        [max(point[0] for point in points), max(point[1] for point in points)],
    ]


def _route_for(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    for route in payload.get("routes") or []:
        if str(route.get("track_id")) == key:
            return route
    return None


def _match_locked(
    entry: dict[str, Any],
    locked: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find the locked entry that belongs to a freshly built entry."""
    key = str(entry.get("key"))
    for candidate in locked:
        if candidate.get("type") != entry.get("type"):
            continue
        if entry.get("type") == "visit" and str(candidate.get("key")) == key:
            return candidate
    if entry.get("type") != "journey":
        return None
    start, _ = _entry_start_end(entry)
    if start is None:
        return None
    for candidate in locked:
        if candidate.get("type") != "journey":
            continue
        other, _ = _entry_start_end(candidate)
        if other is None:
            continue
        if abs((other - start).total_seconds()) <= _JOURNEY_MATCH_SECONDS:
            return candidate
    return None


def _merge_locked_snapshot(
    old: dict[str, Any],
    fresh: dict[str, Any],
) -> dict[str, Any]:
    """Grow a locked day with newly arrived archive points.

    Locking a day used to freeze it completely: an edit early in the day hid
    every registration that arrived later.  A locked snapshot only has to
    protect the user's changes, not stop the day from growing.  New entries
    (later in the day or imported late) are appended and existing entries get
    their dynamic values updated, while names, notes and manual merges from
    the snapshot win.
    """
    if not old.get("entries"):
        return fresh

    entries = [dict(entry) for entry in old["entries"]]
    routes = [dict(route) for route in old.get("routes") or []]
    routes_by_key = {
        str(route.get("track_id")): route for route in routes
    }
    deleted = {str(key) for key in old.get("deleted_keys") or []}
    merged_from = {
        str(key)
        for entry in entries
        for key in entry.get("merged_from") or []
    }

    changed = False
    dynamic_fields = (
        "end",
        "duration_minutes",
        "duration_seconds",
        "distance",
        "end_latitude",
        "end_longitude",
        "end_state",
        "address",
        "subtitle",
        "speed_max",
        "mode",
        "color",
    )

    for entry in fresh.get("entries") or []:
        key = str(entry.get("key"))
        if key in deleted or key in merged_from:
            # The user removed or merged this entry; do not resurrect it.
            changed = True
            continue

        match = _match_locked(entry, entries)
        if match is not None:
            if match.get("user_merged") or match.get("merged"):
                # A manual merge owns this time span until the user resets
                # the day; do not split it up again.
                continue
            old_start, old_end = _entry_start_end(match)
            new_start, new_end = _entry_start_end(entry)
            for field in dynamic_fields:
                if field not in entry:
                    continue
                if field in ("mode", "color") and match.get("user_edited"):
                    continue
                if (
                    field in ("end", "duration_minutes", "duration_seconds")
                    and old_end is not None
                    and new_end is not None
                    and new_end < old_end
                    and match.get("type") == "visit"
                ):
                    # Never shrink a visit that the user merged by hand.
                    continue
                if match.get(field) != entry.get(field):
                    match[field] = entry[field]
                    changed = True
            if entry.get("type") == "journey":
                fresh_route = _route_for(fresh, key)
                if fresh_route is not None:
                    route = dict(fresh_route)
                    route["track_id"] = str(match.get("key"))
                    target_key = str(match.get("key"))
                    existing = routes_by_key.get(target_key)
                    if existing is None:
                        routes.append(route)
                        routes_by_key[target_key] = route
                    elif existing != route:
                        index = routes.index(existing)
                        routes[index] = route
                        routes_by_key[target_key] = route
                    changed = True
            continue

        # A brand-new entry.  Append it when it lies after everything the
        # snapshot already covers, or when it fills a gap that no locked
        # entry covers (late-imported points).
        start, _ = _entry_start_end(entry)
        covered_ends = [
            end for end in (_entry_start_end(item)[1] for item in entries)
            if end is not None
        ]
        covered_end = max(covered_ends) if covered_ends else None
        in_gap = not any(_overlaps(entry, item) for item in entries)
        after_end = (
            start is not None
            and covered_end is not None
            and start >= covered_end - timedelta(seconds=30)
        )
        if in_gap or after_end:
            entries.append(dict(entry))
            route = _route_for(fresh, key)
            if route is not None:
                routes.append(dict(route))
                routes_by_key[key] = routes[-1]
            changed = True

    if not changed:
        return old

    payload = dict(old)
    payload["entries"] = sorted(
        entries, key=lambda item: str(item.get("start") or "")
    )
    payload["routes"] = routes
    payload["bounds"] = _merge_bounds(old.get("bounds"), fresh.get("bounds"))
    if old.get("deleted_keys"):
        payload["deleted_keys"] = old["deleted_keys"]
    _recompute_summary(payload)
    return payload


async def get_local_day(
    hass: HomeAssistant,
    archive: Archive,
    entity_id: str,
    day_str: str,
) -> dict[str, Any]:
    """Return a day, keeping user edits while new archive points come in."""
    snapshot = await archive.async_snapshot(entity_id, day_str)
    if snapshot and snapshot.get("locked"):
        # Rebuild from the archive and re-apply the locked snapshot so a day
        # that was edited early keeps growing during the rest of the day.
        fresh = await build_local_day(hass, archive, entity_id, day_str)
        merged = _merge_locked_snapshot(snapshot["payload"], fresh)
        if merged is not snapshot["payload"] and merged != snapshot["payload"]:
            await archive.async_save_snapshot(
                entity_id, day_str, merged, locked=True
            )
        await _index_visits(archive, merged)
        return merged
    return await build_local_day(hass, archive, entity_id, day_str)


async def lock_day(
    hass: HomeAssistant,
    archive: Archive,
    entity_id: str,
    day_str: str,
) -> dict[str, Any]:
    """Freeze a freshly derived day so later edits keep stable IDs."""
    payload = await build_local_day(hass, archive, entity_id, day_str)
    await archive.async_save_snapshot(entity_id, day_str, payload, locked=True)
    return payload


async def get_local_month(
    hass: HomeAssistant,
    archive: Archive,
    entity_id: str,
    year: int,
    month: int,
) -> dict[str, Any]:
    tz = ZoneInfo(hass.config.time_zone)
    first = date(year, month, 1)
    last = (
        date(year + 1, 1, 1)
        if month == 12
        else date(year, month + 1, 1)
    ) - timedelta(days=1)
    start = datetime.combine(first, dt_time.min, tzinfo=tz)
    end = datetime.combine(last, dt_time.min, tzinfo=tz) + timedelta(
        days=1
    ) - timedelta(seconds=1)
    counts = await archive.async_days(
        entity_id, start.timestamp(), end.timestamp()
    )
    return {
        "year": year,
        "month": month,
        "days": {day: {"points": count} for day, count in counts.items()},
    }


# ----------------------------------------------------------------------
# Snapshot mutations
# ----------------------------------------------------------------------
def _find(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    for entry in payload.get("entries") or []:
        if entry.get("key") == key:
            return entry
    return None


def _remove(payload: dict[str, Any], key: str) -> None:
    payload["entries"] = [
        entry for entry in payload.get("entries") or [] if entry.get("key") != key
    ]
    payload["routes"] = [
        route for route in payload.get("routes") or [] if str(route.get("track_id")) != key
    ]


def update_visit(
    payload: dict[str, Any],
    key: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    entry = _find(payload, key)
    if entry is None or entry.get("type") != "visit":
        return None
    if "name" in updates:
        name = str(updates["name"]).strip()
        if name and not entry.get("is_home"):
            entry["name"] = name
            entry["place_name"] = name
            entry["subtitle"] = ""
    if "place_id" in updates:
        entry["place_id"] = updates["place_id"]
    if "note" in updates:
        entry["note"] = updates["note"]
    if "status" in updates:
        entry["status"] = updates["status"]
    entry["user_edited"] = True
    _recompute_summary(payload)
    return entry


def delete_visit(payload: dict[str, Any], key: str) -> bool:
    entry = _find(payload, key)
    if entry is None or entry.get("type") != "visit":
        return False
    _remove(payload, key)
    # Remember the removal: the visit will be detected again when the day is
    # rebuilt from the archive and must not reappear.
    deleted = payload.setdefault("deleted_keys", [])
    if key not in deleted:
        deleted.append(key)
    _recompute_summary(payload)
    return True


def merge_visits(payload: dict[str, Any], keys: list[str]) -> dict[str, Any] | None:
    selected = [
        entry
        for entry in payload.get("entries") or []
        if entry.get("key") in keys and entry.get("type") == "visit"
    ]
    if len(selected) < 2:
        return None
    selected.sort(key=lambda item: item.get("start") or "")
    first = selected[0]
    last = selected[-1]
    durations = [max(1, int(item.get("duration_minutes") or 1)) for item in selected]
    total = sum(durations)
    first["start"] = first.get("start")
    first["end"] = last.get("end")
    first["latitude"] = sum(
        float(item.get("latitude") or 0) * weight
        for item, weight in zip(selected, durations, strict=False)
    ) / total
    first["longitude"] = sum(
        float(item.get("longitude") or 0) * weight
        for item, weight in zip(selected, durations, strict=False)
    ) / total
    try:
        begin = datetime.fromisoformat(first["start"])
        finish = datetime.fromisoformat(first["end"])
        first["duration_minutes"] = int((finish - begin).total_seconds() / 60)
    except (KeyError, TypeError, ValueError):
        first["duration_minutes"] = total
    first["user_merged"] = True
    first["merged_from"] = [str(item.get("key")) for item in selected]
    for entry in selected[1:]:
        _remove(payload, entry["key"])
    _recompute_summary(payload)
    return first


def update_journey(
    payload: dict[str, Any],
    key: str,
    mode: str | None = None,
    note: str | None = None,
) -> dict[str, Any] | None:
    entry = _find(payload, key)
    if entry is None or entry.get("type") != "journey":
        return None
    if mode:
        entry["mode"] = mode
        entry["color"] = MODE_COLORS.get(mode, MODE_COLORS["unknown"])
        for route in payload.get("routes") or []:
            if str(route.get("track_id")) == key:
                route["mode"] = mode
                route["color"] = entry["color"]
    if note is not None:
        entry["note"] = note
    entry["user_edited"] = True
    _recompute_summary(payload)
    return entry


def merge_journeys(payload: dict[str, Any], keys: list[str]) -> dict[str, Any] | None:
    selected = [
        entry
        for entry in payload.get("entries") or []
        if entry.get("key") in keys and entry.get("type") == "journey"
    ]
    if len(selected) < 2:
        return None
    selected.sort(key=lambda item: item.get("start") or "")
    first = selected[0]
    last = selected[-1]
    distance = sum(float(item.get("distance") or 0) for item in selected)
    duration = sum(float(item.get("duration_seconds") or 0) for item in selected)
    first["end"] = last.get("end")
    first["distance"] = round(distance, 1)
    first["duration_seconds"] = int(duration)
    first["merged"] = True
    first["user_merged"] = True
    first["merged_from"] = [str(item.get("key")) for item in selected]
    first["track_ids"] = [item.get("key") for item in selected]
    first["note"] = " ".join(
        str(item.get("note")) for item in selected if item.get("note")
    ).strip()
    # Keep the routes of every part, but point them at the merged entry.
    for item in selected[1:]:
        for route in payload.get("routes") or []:
            if str(route.get("track_id")) == item.get("key"):
                route["track_id"] = first.get("key")
        _remove(payload, item["key"])
    _recompute_summary(payload)
    return first


def reset_day(payload: dict[str, Any]) -> None:
    """Placeholder for a future 'recalculate day' action."""
    _recompute_summary(payload)
