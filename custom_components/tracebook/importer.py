"""Recorder backfill for the local archive.

The archive only starts collecting when it is first installed.  To avoid
losing the past, this module copies the still-retained recorder history into
the archive.  Older history can be imported from GPX, GeoJSON or Google
Timeline exports via the import view.
"""

from __future__ import annotations

import logging
from datetime import datetime, time as dt_time, timedelta
from functools import partial
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.core import HomeAssistant

from .archive import Archive

_LOGGER = logging.getLogger(__name__)

IMPORT_BATCH = 2000
RECORDER_BATCH_DAYS = 1


def _point_row(
    person: str,
    entity_id: str,
    timestamp: float,
    attributes: dict[str, Any],
    source: str,
) -> dict[str, Any] | None:
    latitude = attributes.get("latitude")
    longitude = attributes.get("longitude")
    if latitude is None or longitude is None:
        return None
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return None

    def number(key: str) -> float | None:
        value = attributes.get(key)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    return {
        "person": person,
        "entity_id": entity_id,
        "ts": float(timestamp),
        "lat": latitude,
        "lon": longitude,
        "accuracy": number("gps_accuracy") or number("accuracy"),
        "speed": number("speed"),
        "altitude": number("altitude"),
        "battery": number("battery_level") or number("battery"),
        "source": source,
    }


async def backfill_recorder(
    hass: HomeAssistant,
    archive: Archive,
    entry: dict[str, Any],
    days: int = 10,
) -> int:
    """Copy the still-retained recorder history for one tracker."""
    if days <= 0:
        return 0
    entity_id = entry["entity_id"]
    person = entry["id"]
    tz = ZoneInfo(hass.config.time_zone)
    today = datetime.now(tz).date()
    total = 0

    recorder = get_instance(hass)
    for offset in range(days):
        day = today - timedelta(days=offset)
        start = datetime.combine(day, dt_time.min, tzinfo=tz)
        end = start + timedelta(days=1) - timedelta(seconds=1)
        job = partial(
            get_significant_states,
            hass,
            start,
            end,
            [entity_id],
            include_start_time_state=True,
            significant_changes_only=False,
        )
        try:
            states_by_entity = await recorder.async_add_executor_job(job)
        except Exception as err:  # noqa: BLE001 - recorder may be purging
            _LOGGER.debug("Recorder-backfill %s mislukt: %s", day, err)
            continue

        rows: list[dict[str, Any]] = []
        for state in states_by_entity.get(entity_id, []):
            timestamp = state.last_updated or state.last_changed
            if timestamp is None:
                continue
            row = _point_row(
                person,
                entity_id,
                timestamp.timestamp(),
                state.attributes or {},
                "recorder",
            )
            if row is not None:
                rows.append(row)
        if rows:
            total += await archive.async_add_points(rows)
    return total
