"""Place search for the timeline: Photon (nearby) + Nominatim (world).

Photon is an OSM geocoder with location bias.  It finds named POIs that
Nominatim's search index sometimes misses (for example a bowling alley tagged
only with ``leisure=bowling_alley``), and it is fast enough for a type-ahead.

Search strategy:
1. Photon with the person's coordinates, filtered to a 5 km radius.
2. Nominatim restricted to the same small area.
3. Only if nothing is found nearby: Nominatim worldwide (unless the caller
   asked for local results only).
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

PHOTON_URL = "https://photon.komoot.io/api/"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_MIN_INTERVAL = 1.1
USER_AGENT = "TraceBook/1.7 (Home Assistant)"
CACHE_TTL_SECONDS = 3600
# Photon is regularly unreachable from some networks.  Keep its timeout short
# and skip it for a while after a failure, otherwise every keystroke in the
# place picker would wait 20+ seconds.
PHOTON_TIMEOUT = 4
PHOTON_DOWN_SECONDS = 600
# Live lookups must never block the UI; the local index answers immediately.
LIVE_SEARCH_TIMEOUT = 4.0

_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_photon_lock = asyncio.Lock()
_lock = asyncio.Lock()
_last_request = 0.0
_photon_down_until = 0.0

OSM_TYPES = {"N": "node", "W": "way", "R": "relation"}


def _short_name(payload: dict[str, Any]) -> str:
    name = payload.get("name")
    if name:
        return str(name)
    display = str(payload.get("display_name") or "").split(",")
    return display[0].strip() if display else "Onbekende plek"


def _result(payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        latitude = float(payload["lat"])
        longitude = float(payload["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    osm_type = payload.get("osm_type")
    osm_id = payload.get("osm_id")
    identifier = f"osm:{osm_type}:{osm_id}" if osm_type and osm_id else None
    return {
        "id": identifier,
        "name": _short_name(payload),
        "display_name": payload.get("display_name"),
        "address": payload.get("display_name"),
        "lat": latitude,
        "lon": longitude,
        "type": payload.get("type"),
        "category": payload.get("category"),
        "osm_type": osm_type,
        "osm_id": osm_id,
    }


def _distance_m(
    first: tuple[float, float], second: tuple[float, float]
) -> float:
    radius = 6371000.0
    lat1, lon1 = math.radians(first[0]), math.radians(first[1])
    lat2, lon2 = math.radians(second[0]), math.radians(second[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def _photon_address(props: dict[str, Any]) -> str:
    parts = []
    street = props.get("street")
    number = props.get("housenumber")
    if street:
        parts.append(f"{street} {number}" if number else str(street))
    city = props.get("city") or props.get("locality")
    if city:
        parts.append(str(city))
    return ", ".join(parts)


async def _photon_search(
    session,
    query: str,
    near: tuple[float, float] | None,
    radius: int,
    limit: int,
) -> list[dict[str, Any]]:
    global _photon_down_until
    if time.monotonic() < _photon_down_until:
        return []

    params: dict[str, Any] = {"q": query, "limit": 30}
    if near is not None:
        params["lat"] = f"{near[0]:.6f}"
        params["lon"] = f"{near[1]:.6f}"

    async with _photon_lock:
        if time.monotonic() < _photon_down_until:
            return []
        try:
            async with session.get(
                PHOTON_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=PHOTON_TIMEOUT,
            ) as response:
                if response.status != 200:
                    _LOGGER.debug("Photon gaf status %s", response.status)
                    _photon_down_until = time.monotonic() + PHOTON_DOWN_SECONDS
                    return []
                payload = await response.json()
        except Exception as err:  # noqa: BLE001 - search is optional
            _LOGGER.debug("Photon zoeken mislukt voor %r: %s", query, err)
            _photon_down_until = time.monotonic() + PHOTON_DOWN_SECONDS
            return []
    if payload is None:
        return []

    results: list[dict[str, Any]] = []
    for feature in payload.get("features") or []:
        props = feature.get("properties") or {}
        name = props.get("name")
        if not name:
            continue
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        if len(coordinates) < 2:
            continue
        try:
            longitude = float(coordinates[0])
            latitude = float(coordinates[1])
        except (TypeError, ValueError):
            continue
        if near is not None and _distance_m(near, (latitude, longitude)) > radius:
            continue
        osm_type = OSM_TYPES.get(str(props.get("osm_type") or "").upper())
        osm_id = props.get("osm_id")
        category = props.get("osm_value") or props.get("osm_key")
        results.append(
            {
                "id": f"osm:{osm_type}:{osm_id}" if osm_type and osm_id else None,
                "name": str(name),
                "display_name": _photon_address(props),
                "address": _photon_address(props),
                "lat": latitude,
                "lon": longitude,
                "type": category,
                "category": category,
                "osm_type": osm_type,
                "osm_id": osm_id,
            }
        )

    if near is not None:
        results.sort(key=lambda item: _distance_m(near, (item["lat"], item["lon"])))
    return results[:limit]


async def _nominatim_search(
    session, params: dict[str, Any], query: str
) -> list[dict[str, Any]]:
    global _last_request
    wait = NOMINATIM_MIN_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        await asyncio.sleep(wait)
    results: list[dict[str, Any]] = []
    try:
        async with session.get(
            NOMINATIM_SEARCH_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        ) as response:
            if response.status == 200:
                for payload in await response.json():
                    item = _result(payload)
                    if item is not None:
                        results.append(item)
            else:
                _LOGGER.debug(
                    "Nominatim zoeken gaf status %s voor %r",
                    response.status,
                    query,
                )
    except Exception as err:  # noqa: BLE001 - search is optional
        _LOGGER.debug("Nominatim zoeken mislukt voor %r: %s", query, err)
    finally:
        _last_request = time.monotonic()
    return results


def _dedupe(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in results:
        key = str(item.get("id") or f"{item.get('name')}|{item.get('lat')}")
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


async def async_search_places(
    hass: HomeAssistant,
    query: str,
    limit: int = 8,
    near: tuple[float, float] | None = None,
    local_only: bool = False,
    timeout: float | None = LIVE_SEARCH_TIMEOUT,
) -> list[dict[str, Any]]:
    """Search live geocoders, but never block longer than ``timeout``.

    The caller normally already has results from the local OSM index; this
    function only fills the gaps for areas that are not indexed yet.
    """
    try:
        if timeout is None:
            return await _search_places_live(hass, query, limit, near, local_only)
        return await asyncio.wait_for(
            _search_places_live(hass, query, limit, near, local_only),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        _LOGGER.debug("Live plaatszoeken duurde te lang voor %r", query)
        return []


async def _search_places_live(
    hass: HomeAssistant,
    query: str,
    limit: int = 8,
    near: tuple[float, float] | None = None,
    local_only: bool = False,
) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []

    key = (
        f"{query.lower()}|{limit}|{near[0]:.3f},{near[1]:.3f}|{local_only}"
        if near
        else f"{query.lower()}|{limit}|{local_only}"
    )
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    session = async_get_clientsession(hass)
    results: list[dict[str, Any]] = []

    if near is not None:
        results.extend(
            await _photon_search(session, query, near, 5000, max(limit, 12))
        )
        params: dict[str, Any] = {
            "format": "jsonv2",
            "q": query,
            "limit": limit,
            "addressdetails": 1,
            "dedupe": 1,
            "accept-language": "nl",
            "viewbox": (
                f"{near[1] - 0.05:.4f},{near[0] + 0.035:.4f},"
                f"{near[1] + 0.05:.4f},{near[0] - 0.035:.4f}"
            ),
            "bounded": 1,
        }
        results.extend(await _nominatim_search(session, params, query))
        results = _dedupe(results)
        if not results:
            # Broaden the Nominatim search within the same map area. This is
            # the fallback when Photon is unavailable.
            broad = dict(params)
            broad["bounded"] = 0
            extra = await _nominatim_search(session, broad, query)
            results.extend(
                item
                for item in extra
                if _distance_m(near, (item["lat"], item["lon"])) <= 25_000
            )
            results = _dedupe(results)
        if results:
            results.sort(
                key=lambda item: _distance_m(
                    near, (item["lat"], item["lon"])
                )
            )
            _cache[key] = (time.monotonic(), results[:limit])
            return results[:limit]
        if local_only:
            _cache[key] = (time.monotonic(), [])
            return []

    params = {
        "format": "jsonv2",
        "q": query,
        "limit": limit,
        "addressdetails": 1,
        "dedupe": 1,
        "accept-language": "nl",
    }
    results = _dedupe(await _nominatim_search(session, params, query))
    _cache[key] = (time.monotonic(), results)
    return results
