"""Websocket API for the local archive: day, edits, POI search and export."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from . import local_history
from .archive import Archive
from .geo import _distance_m
from .const import DOMAIN, JOURNEY_MODES
from .poi import async_search_places
from .poi_sync import async_sync_point
from .websocket import _authorized, _is_admin

_LOGGER = logging.getLogger(__name__)

MAX_EXPORT_POINTS = 150_000


def _archive(hass: HomeAssistant) -> Archive | None:
    return (hass.data.get(DOMAIN) or {}).get("archive")


def _trackers(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    return (hass.data.get(DOMAIN) or {}).get("trackers") or {}


def _entry(hass: HomeAssistant, entity_id: str) -> dict[str, Any] | None:
    return _trackers(hass).get(entity_id)


def _check_access(hass: HomeAssistant, connection, entity_id: str) -> bool:
    """Family timelines are admin-only; the own timeline needs authorization."""
    data = hass.data.get(DOMAIN) or {}
    if (data.get("family") or {}).get(entity_id) is not None:
        return _is_admin(connection)
    return _authorized(hass, connection)


def _send_unauthorized(connection, msg: dict, message: str) -> None:
    connection.send_error(msg["id"], websocket_api.ERR_UNAUTHORIZED, message)


def async_register_local_websocket_api(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, websocket_archive_status)
    websocket_api.async_register_command(hass, websocket_local_day)
    websocket_api.async_register_command(hass, websocket_local_month)
    websocket_api.async_register_command(hass, websocket_local_update_visit)
    websocket_api.async_register_command(hass, websocket_local_delete_visit)
    websocket_api.async_register_command(hass, websocket_local_merge_visits)
    websocket_api.async_register_command(hass, websocket_local_update_journey)
    websocket_api.async_register_command(hass, websocket_local_move_journey_part)
    websocket_api.async_register_command(hass, websocket_local_merge_journeys)
    websocket_api.async_register_command(hass, websocket_local_reset_day)
    websocket_api.async_register_command(hass, websocket_local_places)
    websocket_api.async_register_command(hass, websocket_local_save_place)
    websocket_api.async_register_command(hass, websocket_places_search)
    websocket_api.async_register_command(hass, websocket_places_near)
    websocket_api.async_register_command(hass, websocket_places_lookup)
    websocket_api.async_register_command(hass, websocket_contacts_near)
    websocket_api.async_register_command(hass, websocket_local_export)


async def _mutable_day(
    hass: HomeAssistant,
    archive: Archive,
    entity_id: str,
    day: str,
) -> dict[str, Any]:
    """Return the day including late archive data, ready for an edit.

    Starting from the raw locked snapshot would drop everything that arrived
    after the snapshot was created, so always go through ``get_local_day``
    which merges in the newer points.
    """
    return await local_history.get_local_day(hass, archive, entity_id, day)


@websocket_api.websocket_command({vol.Required("type"): "geopulse/archive_status"})
@websocket_api.async_response
async def websocket_archive_status(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _authorized(hass, connection):
        _send_unauthorized(connection, msg, "Geen toegang tot de tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_result(msg["id"], {"enabled": False})
        return
    status = await archive.async_status()
    progress = await archive.async_meta("import_progress")
    status["enabled"] = True
    status["progress"] = json.loads(progress) if progress else None
    if _is_admin(connection):
        status["trackers"] = {
            entry["entity_id"]: {"id": entry["id"], "name": entry["name"]}
            for entry in _trackers(hass).values()
        }
    else:
        # A regular user may see the total size but not the other
        # family members' data volumes.
        status.pop("per_entity", None)
    connection.send_result(msg["id"], status)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_day",
        vol.Required("date"): str,
        vol.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def websocket_local_day(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    try:
        date.fromisoformat(msg["date"])
    except ValueError:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Ongeldige datum")
        return
    try:
        result = await local_history.get_local_day(
            hass, archive, msg["entity_id"], msg["date"]
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Lokale dag opbouwen mislukt")
        connection.send_error(msg["id"], "archive_error", str(err))
        return
    connection.send_result(msg["id"], result)

    # Index the areas around the viewed day in the background, so searching
    # for a new place there works without a complete name next time.  Use the
    # visits themselves, not the bounding-box centre: a travel day from home
    # to Amsterdam has its centre somewhere along the motorway.
    bounds = result.get("bounds")
    if bounds and len(bounds) == 2 and archive is not None:
        candidates: list[tuple[float, float]] = []
        for entry in result.get("entries") or []:
            if entry.get("type") != "visit" or entry.get("is_home"):
                continue
            try:
                candidates.append(
                    (
                        float(entry["latitude"]),
                        float(entry["longitude"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        if len(candidates) < 4:
            # A travel day may pass through a city without a long stop.  Add
            # a few points along the route so those areas get indexed too.
            for route in result.get("routes") or []:
                coordinates = route.get("coordinates") or []
                if not coordinates:
                    continue
                middle = coordinates[len(coordinates) // 2]
                for point in (coordinates[0], middle, coordinates[-1]):
                    try:
                        candidates.append((float(point[0]), float(point[1])))
                    except (IndexError, TypeError, ValueError):
                        continue
                    if len(candidates) >= 6:
                        break
                if len(candidates) >= 6:
                    break
        if not candidates:
            candidates.append(
                (
                    (float(bounds[0][0]) + float(bounds[1][0])) / 2,
                    (float(bounds[0][1]) + float(bounds[1][1])) / 2,
                )
            )

        unique: list[tuple[float, float]] = []
        for latitude, longitude in candidates:
            if any(
                abs(latitude - lat) < 0.01 and abs(longitude - lon) < 0.01
                for lat, lon in unique
            ):
                continue
            unique.append((latitude, longitude))

        async def _index_day_areas() -> None:
            for latitude, longitude in unique[:5]:
                await async_sync_point(hass, archive, latitude, longitude)

        hass.async_create_task(_index_day_areas())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_month",
        vol.Required("year"): vol.All(int, vol.Range(min=2000, max=2100)),
        vol.Required("month"): vol.All(int, vol.Range(min=1, max=12)),
        vol.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def websocket_local_month(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    try:
        result = await local_history.get_local_month(
            hass, archive, msg["entity_id"], msg["year"], msg["month"]
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Lokale maand opbouwen mislukt")
        connection.send_error(msg["id"], "archive_error", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_update_visit",
        vol.Required("date"): str,
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("visit_id"): str,
        vol.Optional("name"): str,
        vol.Optional("note"): str,
        vol.Optional("place_id"): vol.Any(str, None),
        vol.Optional("status"): vol.In(["suggested", "confirmed", "declined"]),
    }
)
@websocket_api.async_response
async def websocket_local_update_visit(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    updates = {
        key: msg[key]
        for key in ("name", "note", "place_id", "status")
        if key in msg
    }
    if not updates:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Geen wijzigingen")
        return
    if updates.get("place_id") and "name" not in updates:
        for place in await archive.async_places(limit=2000):
            if str(place.get("id")) == str(updates["place_id"]):
                updates["name"] = place.get("name")
                break
    payload = await _mutable_day(hass, archive, msg["entity_id"], msg["date"])
    entry = local_history.update_visit(payload, msg["visit_id"], updates)
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Bezoek niet gevonden")
        return
    await archive.async_save_snapshot(msg["entity_id"], msg["date"], payload)
    connection.send_result(msg["id"], {"visit": entry, "day": payload})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_delete_visit",
        vol.Required("date"): str,
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("visit_id"): str,
    }
)
@websocket_api.async_response
async def websocket_local_delete_visit(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    payload = await _mutable_day(hass, archive, msg["entity_id"], msg["date"])
    if not local_history.delete_visit(payload, msg["visit_id"]):
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Bezoek niet gevonden")
        return
    await archive.async_save_snapshot(msg["entity_id"], msg["date"], payload)
    connection.send_result(msg["id"], {"day": payload})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_merge_visits",
        vol.Required("date"): str,
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("visit_ids"): vol.All(cv.ensure_list, [str]),
    }
)
@websocket_api.async_response
async def websocket_local_merge_visits(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    payload = await _mutable_day(hass, archive, msg["entity_id"], msg["date"])
    entry = local_history.merge_visits(payload, list(msg["visit_ids"]))
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Kies minimaal twee bezoeken")
        return
    await archive.async_save_snapshot(msg["entity_id"], msg["date"], payload)
    connection.send_result(msg["id"], {"visit": entry, "day": payload})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_update_journey",
        vol.Required("date"): str,
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("track_key"): str,
        vol.Optional("mode"): vol.In(JOURNEY_MODES),
        vol.Optional("note"): str,
    }
)
@websocket_api.async_response
async def websocket_local_update_journey(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    if msg.get("mode") is None and msg.get("note") is None:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Geen wijzigingen")
        return
    payload = await _mutable_day(hass, archive, msg["entity_id"], msg["date"])
    entry = local_history.update_journey(
        payload, msg["track_key"], msg.get("mode"), msg.get("note")
    )
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "Reis niet gevonden")
        return
    await archive.async_save_snapshot(msg["entity_id"], msg["date"], payload)
    connection.send_result(msg["id"], {"journey": entry, "day": payload})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_move_journey_part",
        vol.Required("date"): str,
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("track_key"): str,
        vol.Required("split_ts"): str,
        vol.Required("direction"): vol.In(
            ["tail_to_next", "head_to_previous"]
        ),
        vol.Optional("target_key"): str,
    }
)
@websocket_api.async_response
async def websocket_local_move_journey_part(
    hass: HomeAssistant, connection, msg: dict
) -> None:
    """Move the head or tail of a trip into the adjacent trip."""
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    payload = await _mutable_day(hass, archive, msg["entity_id"], msg["date"])
    result = local_history.move_journey_part(
        payload,
        msg["track_key"],
        msg["split_ts"],
        msg["direction"],
        msg.get("target_key"),
    )
    if result is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_INVALID_FORMAT,
            "Dit deel kan niet worden verplaatst",
        )
        return
    await archive.async_save_snapshot(msg["entity_id"], msg["date"], payload)
    connection.send_result(msg["id"], {"day": payload, **result})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_merge_journeys",
        vol.Required("date"): str,
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("keys"): vol.All(cv.ensure_list, [str]),
    }
)
@websocket_api.async_response
async def websocket_local_merge_journeys(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    payload = await _mutable_day(hass, archive, msg["entity_id"], msg["date"])
    entry = local_history.merge_journeys(payload, list(msg["keys"]))
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Kies minimaal twee reizen")
        return
    await archive.async_save_snapshot(msg["entity_id"], msg["date"], payload)
    connection.send_result(msg["id"], {"journey": entry, "day": payload})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_reset_day",
        vol.Required("date"): str,
        vol.Required("entity_id"): cv.entity_id,
    }
)
@websocket_api.async_response
async def websocket_local_reset_day(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    await archive.async_delete_snapshot(msg["entity_id"], msg["date"])
    result = await local_history.get_local_day(
        hass, archive, msg["entity_id"], msg["date"]
    )
    connection.send_result(msg["id"], {"day": result})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_places",
        vol.Optional("query"): str,
    }
)
@websocket_api.async_response
async def websocket_local_places(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _authorized(hass, connection):
        _send_unauthorized(connection, msg, "Geen toegang tot de tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_result(msg["id"], {"places": []})
        return
    places = await archive.async_places(msg.get("query"), limit=200)
    connection.send_result(msg["id"], {"places": places})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_save_place",
        vol.Required("name"): str,
        vol.Required("lat"): vol.Coerce(float),
        vol.Required("lon"): vol.Coerce(float),
        vol.Optional("radius"): vol.Coerce(float),
        vol.Optional("address"): vol.Any(str, None),
        vol.Optional("osm_type"): vol.Any(str, None),
        vol.Optional("osm_id"): vol.Any(str, int, None),
        vol.Optional("place_id"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def websocket_local_save_place(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _authorized(hass, connection):
        _send_unauthorized(connection, msg, "Geen toegang tot de tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    place = {
        "id": msg.get("place_id"),
        "name": msg["name"],
        "lat": msg["lat"],
        "lon": msg["lon"],
        "radius": msg.get("radius"),
        "address": msg.get("address"),
        "osm_type": msg.get("osm_type"),
        "osm_id": msg.get("osm_id"),
    }
    try:
        place = await archive.async_upsert_place(place)
    except (ValueError, KeyError) as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
        return
    await archive.async_upsert_place_index(
        [
            {
                "id": f"saved:{place['id']}",
                "name": place["name"],
                "lat": place["lat"],
                "lon": place["lon"],
                "address": place.get("address"),
                "source": "saved",
            }
        ]
    )
    connection.send_result(msg["id"], {"place": place})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/places_search",
        vol.Required("query"): str,
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("radius", default=75): vol.All(
            vol.Coerce(float), vol.Range(min=10, max=500)
        ),
    }
)
@websocket_api.async_response
async def websocket_places_search(hass: HomeAssistant, connection, msg: dict) -> None:
    """Search OSM places and count how often the person was within a radius."""
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return

    radius = float(msg.get("radius") or 75)
    candidates: list[dict[str, Any]] = []

    # Bias OSM results towards the area where this person actually is.
    near: tuple[float, float] | None = None
    last = await archive.async_last_point(msg["entity_id"])
    if last is not None:
        near = (float(last["lat"]), float(last["lon"]))
    else:
        home = hass.states.get("zone.home")
        if home is not None:
            try:
                near = (
                    float(home.attributes["latitude"]),
                    float(home.attributes["longitude"]),
                )
            except (KeyError, TypeError, ValueError):
                near = None

    # Saved places first, then the local index, then live OSM results.
    seen: set[str] = set()

    def add_candidate(item: dict[str, Any]) -> None:
        key = str(
            item.get("id")
            or f"{item.get('name')}|{item.get('lat')}|{item.get('lon')}"
        )
        if key in seen:
            return
        seen.add(key)
        candidates.append(item)

    for place in await archive.async_places(msg["query"], limit=20):
        add_candidate(
            {
                "id": place.get("id"),
                "name": place.get("name"),
                "address": place.get("address"),
                "lat": place.get("lat"),
                "lon": place.get("lon"),
                "saved": True,
                "type": None,
            }
        )

    local_count = 0
    if near is not None:
        for item in await archive.async_search_place_index(
            msg["query"], near[0], near[1], limit=6
        ):
            local_count += 1
            add_candidate(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "address": item.get("address"),
                    "lat": item.get("lat"),
                    "lon": item.get("lon"),
                    "saved": item.get("source") == "saved",
                    "type": item.get("source"),
                }
            )

    # The local index answers instantly.  Only call the live geocoders when
    # the archive has no coverage here yet (for example a brand-new trip).
    if local_count < 3:
        for place in await async_search_places(
            hass, msg["query"], limit=6, near=near, timeout=4.0
        ):
            add_candidate({**place, "saved": False})

    results: list[dict[str, Any]] = []
    for candidate in candidates[:14]:
        try:
            latitude = float(candidate["lat"])
            longitude = float(candidate["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        visits = await archive.async_visits_near(
            msg["entity_id"], latitude, longitude, radius=radius
        )
        results.append(
            {
                **candidate,
                "radius": radius,
                "visit_count": len(visits),
                "total_minutes": sum(item["minutes"] for item in visits),
                "first": visits[-1]["start"] if visits else None,
                "last": visits[0]["start"] if visits else None,
                "recent": visits[:6],
            }
        )

    results.sort(
        key=lambda item: (
            not item.get("saved"),
            -int(item.get("visit_count") or 0),
            str(item.get("name") or ""),
        )
    )
    connection.send_result(
        msg["id"],
        {"query": msg["query"], "radius": radius, "results": results},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/places_near",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("lat"): vol.Coerce(float),
        vol.Required("lon"): vol.Coerce(float),
        vol.Optional("radius", default=75): vol.All(
            vol.Coerce(float), vol.Range(min=10, max=1000)
        ),
        vol.Optional("limit", default=60): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=200)
        ),
    }
)
@websocket_api.async_response
async def websocket_places_near(
    hass: HomeAssistant, connection, msg: dict
) -> None:
    """All indexed POIs within a short radius of a visit."""
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_result(msg["id"], {"results": []})
        return
    results = await archive.async_place_index_near(
        float(msg["lat"]),
        float(msg["lon"]),
        float(msg.get("radius") or 75),
        limit=int(msg.get("limit") or 60),
    )
    connection.send_result(
        msg["id"],
        {"radius": float(msg.get("radius") or 75), "results": results},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/places_lookup",
        vol.Required("query"): str,
        vol.Optional("lat"): vol.Coerce(float),
        vol.Optional("lon"): vol.Coerce(float),
        vol.Optional("limit", default=8): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=20)
        ),
        vol.Optional("max_distance", default=250): vol.All(
            vol.Coerce(float), vol.Range(min=25, max=5000)
        ),
    }
)
@websocket_api.async_response
async def websocket_places_lookup(
    hass: HomeAssistant, connection, msg: dict
) -> None:
    """Lightweight OSM lookup for the visit edit dropdown.

    Text search around a visit only returns places within a short walk
    (``max_distance``, 250 m by default), so a common surname does not fill
    the dropdown with places hundreds of kilometres away.
    """
    if not _authorized(hass, connection):
        _send_unauthorized(connection, msg, "Geen toegang tot de tijdlijn")
        return
    near = None
    if msg.get("lat") is not None and msg.get("lon") is not None:
        near = (float(msg["lat"]), float(msg["lon"]))
    max_distance = float(msg.get("max_distance") or 250)
    local: list[dict[str, Any]] = []
    archive = _archive(hass)
    if archive is not None and near is not None:
        local = await archive.async_search_place_index(
            msg["query"],
            near[0],
            near[1],
            limit=12,
            max_distance_m=max_distance,
        )
    # Local results are authoritative and instant.  Live OSM is only needed
    # when the index has no nearby match (new area or not indexed yet).
    results = []
    if not local:
        results = await async_search_places(
            hass,
            msg["query"],
            limit=int(msg.get("limit") or 8),
            near=near,
            local_only=True,
            timeout=4.0,
        )
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in local + results:
        try:
            latitude = float(item["lat"])
            longitude = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        distance = (
            _distance_m(near, (latitude, longitude))
            if near is not None
            else None
        )
        if distance is not None and distance > max_distance:
            continue
        key = str(
            item.get("id")
            or f"{item.get('name')}|{round(latitude, 4)}|"
            f"{round(longitude, 4)}"
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            {
                **item,
                "lat": latitude,
                "lon": longitude,
                "distance": round(distance) if distance is not None else None,
            }
        )
    merged.sort(
        key=lambda item: (
            item.get("distance") if item.get("distance") is not None else 1e12
        )
    )
    connection.send_result(msg["id"], {"results": merged[:12]})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/contacts_near",
        vol.Required("lat"): vol.Coerce(float),
        vol.Required("lon"): vol.Coerce(float),
        vol.Optional("radius", default=150): vol.All(
            vol.Coerce(float), vol.Range(min=10, max=1000)
        ),
    }
)
@websocket_api.async_response
async def websocket_contacts_near(
    hass: HomeAssistant, connection, msg: dict
) -> None:
    """Contacts from the address book whose address is near a visit."""
    if not _authorized(hass, connection):
        _send_unauthorized(connection, msg, "Geen toegang tot de tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_result(msg["id"], {"contacts": []})
        return
    contacts = await archive.async_contacts_near(
        float(msg["lat"]), float(msg["lon"]), float(msg.get("radius") or 150)
    )
    connection.send_result(msg["id"], {"contacts": contacts})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/local_export",
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("start"): str,
        vol.Required("end"): str,
        vol.Optional("format", default="gpx"): vol.In(["gpx", "geojson"]),
    }
)
@websocket_api.async_response
async def websocket_local_export(hass: HomeAssistant, connection, msg: dict) -> None:
    if not _check_access(hass, connection, msg["entity_id"]):
        _send_unauthorized(connection, msg, "Geen toegang tot deze tijdlijn")
        return
    archive = _archive(hass)
    if archive is None:
        connection.send_error(msg["id"], "archive_disabled", "Archief staat uit")
        return
    tz = ZoneInfo(hass.config.time_zone)
    try:
        start = datetime.combine(
            date.fromisoformat(msg["start"]), dt_time.min, tzinfo=tz
        )
        end = datetime.combine(
            date.fromisoformat(msg["end"]), dt_time.min, tzinfo=tz
        ) + timedelta(days=1)
    except ValueError:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, "Ongeldige datum")
        return

    rows = await archive.async_export_rows(
        msg["entity_id"], start.timestamp(), end.timestamp()
    )
    if len(rows) > MAX_EXPORT_POINTS:
        connection.send_error(
            msg["id"],
            "export_too_large",
            f"Te veel punten ({len(rows)}). Kies een kortere periode.",
        )
        return

    entry = _entry(hass, msg["entity_id"]) or {}
    name = entry.get("name") or msg["entity_id"]
    if msg["format"] == "geojson":
        content = _geojson(rows, name)
        filename = f"{name}-{msg['start']}-{msg['end']}.geojson"
    else:
        content = _gpx(rows, name)
        filename = f"{name}-{msg['start']}-{msg['end']}.gpx"
    connection.send_result(
        msg["id"],
        {
            "format": msg["format"],
            "filename": filename,
            "points": len(rows),
            "content": content,
        },
    )


def _iso_utc(ts: float) -> str:
    return (
        datetime.fromtimestamp(ts, timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _gpx(rows: list[dict[str, Any]], name: str) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="TraceBook" '
        'xmlns="http://www.topografix.com/GPX/1/1">',
        f"<metadata><name>{name}</name></metadata>",
        f"<trk><name>{name}</name><trkseg>",
    ]
    for row in rows:
        moment = _iso_utc(float(row["ts"]))
        lines.append(
            f'<trkpt lat="{float(row["lat"]):.7f}" lon="{float(row["lon"]):.7f}">'
            f"<time>{moment}</time></trkpt>"
        )
    lines.append("</trkseg></trk></gpx>")
    return "\n".join(lines)


def _geojson(rows: list[dict[str, Any]], name: str) -> str:
    features = []
    for row in rows:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row["lon"]), float(row["lat"])],
                },
                "properties": {
                    "timestamp": _iso_utc(float(row["ts"])),
                    "accuracy": row.get("accuracy"),
                    "speed": row.get("speed"),
                    "altitude": row.get("altitude"),
                },
            }
        )
    return json.dumps(
        {"type": "FeatureCollection", "name": name, "features": features},
        ensure_ascii=False,
    )
