"""Background OSM POI index for future-proof place search.

Photon and Nominatim only match complete words ("Jumbo", not "Jum") and do not
handle typos.  To make the timeline search work for any place, now and later,
we keep a local index of named OSM places in the archive database.  It is
filled in the background from Overpass, tile by tile, around home and around
areas you view.  Searching then happens locally with prefix and fuzzy matching;
Photon remains the fallback for areas not indexed yet.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .archive import Archive
from .poi import USER_AGENT

_LOGGER = logging.getLogger(__name__)

OVERPASS_ENDPOINTS = [
    # NextGIS runs a current, reachable Overpass instance.  The classic
    # mirrors are regularly unreachable from home networks (timeouts/502).
    "https://overpass.nextgis.com/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
SYNC_TTL_SECONDS = 30 * 24 * 3600
MAX_TILES_PER_RUN = 18
NIGHTLY_TILES = 240
TILE_KM = 5.0
#: Bump when the Overpass filters below change, so already indexed tiles are
#: fetched again with the new categories.
INDEX_VERSION = 2
HOME_RADIUS_KM = 25.0
POINT_RADIUS_KM = 4.0
QUERY_TIMEOUT = 20

_LOCK = asyncio.Lock()
_working_endpoint: str | None = None


def _tile_steps(lat: float, size_km: float) -> tuple[float, float]:
    lat_step = size_km / 111.32
    lon_step = size_km / (
        111.32 * max(0.15, math.cos(math.radians(lat)))
    )
    return lat_step, lon_step


def _tile_key(lat: float, lon: float, size_km: float) -> str:
    lat_step, lon_step = _tile_steps(lat, size_km)
    return (
        f"poi_tile:v{INDEX_VERSION}:{size_km:g}:"
        f"{int(lat / lat_step)}:{int(lon / lon_step)}"
    )


def _tile_center(lat: float, lon: float, size_km: float) -> tuple[float, float]:
    lat_step, lon_step = _tile_steps(lat, size_km)
    return (
        (int(lat / lat_step) + 0.5) * lat_step,
        (int(lon / lon_step) + 0.5) * lon_step,
    )


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 6371000.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def _address(tags: dict[str, Any]) -> str:
    street = tags.get("addr:street")
    number = tags.get("addr:housenumber")
    city = tags.get("addr:city")
    parts = []
    if street:
        parts.append(f"{street} {number}" if number else str(street))
    if city:
        parts.append(str(city))
    return ", ".join(parts)


def _build_query(lat: float, lon: float, radius_km: float) -> str:
    lat_delta = radius_km / 111.32
    lon_delta = radius_km / (
        111.32 * max(0.15, math.cos(math.radians(lat)))
    )
    south = lat - lat_delta
    north = lat + lat_delta
    west = lon - lon_delta
    east = lon + lon_delta
    bbox = f"{south:.5f},{west:.5f},{north:.5f},{east:.5f}"
    # Include offices (notaries, lawyers, doctors) and other named services,
    # not just shops and amenities: "Schäfer Notarissen" is tagged as
    # office=notary and was invisible to the search before.
    categories = (
        "amenity",
        "shop",
        "leisure",
        "tourism",
        "office",
        "healthcare",
        "craft",
        "club",
        "historic",
        "public_transport",
        "railway",
        "aeroway",
    )
    filters = [
        f'{kind}["name"]["{category}"]({bbox});'
        for category in categories
        for kind in ("node", "way")
    ]
    return (
        "[out:json][timeout:30];(" + "".join(filters) + ");"
        "out center 10000;"
    )


async def _overpass(session, query: str) -> dict[str, Any] | None:
    global _working_endpoint
    endpoints = list(OVERPASS_ENDPOINTS)
    if _working_endpoint in endpoints:
        endpoints.remove(_working_endpoint)
        endpoints.insert(0, _working_endpoint)
    for url in endpoints:
        try:
            async with session.post(
                url,
                data={"data": query},
                headers={"User-Agent": USER_AGENT},
                timeout=QUERY_TIMEOUT,
            ) as response:
                if response.status != 200:
                    _LOGGER.debug("Overpass %s gaf status %s", url, response.status)
                    continue
                payload = await response.json()
                stamp = str(
                    (payload.get("osm3s") or {}).get("timestamp_osm_base") or ""
                )
                if stamp.isdigit() and int(stamp) < 1_000_000_000:
                    # Broken/stale instance (e.g. an empty 1970 database).
                    _LOGGER.debug("Overpass %s heeft een lege database", url)
                    continue
                _working_endpoint = url
                return payload
        except Exception as err:  # noqa: BLE001 - try the next mirror
            _LOGGER.debug("Overpass %s mislukt: %s", url, err)
    return None


async def _sync_tile(
    hass: HomeAssistant,
    archive: Archive,
    lat: float,
    lon: float,
    size_km: float,
) -> int:
    key = _tile_key(lat, lon, size_km)
    synced = await archive.async_meta(key)
    if synced:
        try:
            if time.time() - float(synced) < SYNC_TTL_SECONDS:
                return 0
        except ValueError:
            pass

    center_lat, center_lon = _tile_center(lat, lon, size_km)
    session = async_get_clientsession(hass)
    payload = await _overpass(
        session, _build_query(center_lat, center_lon, size_km / 2)
    )
    if payload is None:
        return 0

    rows: list[dict[str, Any]] = []
    for element in payload.get("elements") or []:
        tags = element.get("tags") or {}
        name = tags.get("name") or tags.get("name:nl")
        if not name:
            continue
        if element.get("type") == "node":
            latitude = element.get("lat")
            longitude = element.get("lon")
        else:
            center = element.get("center") or {}
            latitude = center.get("lat")
            longitude = center.get("lon")
        if latitude is None or longitude is None:
            continue
        rows.append(
            {
                "id": f"osm:{element.get('type')}:{element.get('id')}",
                "name": str(name),
                "lat": float(latitude),
                "lon": float(longitude),
                "address": _address(tags),
                "source": "osm",
            }
        )

    if rows:
        await archive.async_upsert_place_index(rows)
    await archive.async_set_meta(key, str(time.time()))
    _LOGGER.debug(
        "POI-index: %s plekken in tegel %s", len(rows), key
    )
    return len(rows)


async def async_sync_point(
    hass: HomeAssistant,
    archive: Archive,
    lat: float,
    lon: float,
    radius_km: float = POINT_RADIUS_KM,
) -> int:
    """Index the tile around one point (used when a new area is viewed)."""
    async with _LOCK:
        return await _sync_tile(hass, archive, lat, lon, radius_km * 2)


async def async_sync_home(
    hass: HomeAssistant,
    archive: Archive,
    lat: float,
    lon: float,
    radius_km: float = HOME_RADIUS_KM,
    max_tiles: int = MAX_TILES_PER_RUN,
) -> int:
    lat_step, lon_step = _tile_steps(lat, TILE_KM)
    lat_min = int((lat - radius_km / 111.32) / lat_step) - 1
    lat_max = int((lat + radius_km / 111.32) / lat_step) + 1
    lon_range = radius_km / (
        111.32 * max(0.15, math.cos(math.radians(lat)))
    )
    lon_min = int((lon - lon_range) / lon_step) - 1
    lon_max = int((lon + lon_range) / lon_step) + 1

    tiles: list[tuple[float, float, float]] = []
    for lat_index in range(lat_min, lat_max + 1):
        for lon_index in range(lon_min, lon_max + 1):
            center_lat = (lat_index + 0.5) * lat_step
            center_lon = (lon_index + 0.5) * lon_step
            distance = _distance_m((lat, lon), (center_lat, center_lon))
            if distance > radius_km * 1000:
                continue
            tiles.append((distance, center_lat, center_lon))
    tiles.sort()

    done = 0
    async with _LOCK:
        for _distance, center_lat, center_lon in tiles:
            key = _tile_key(center_lat, center_lon, TILE_KM)
            synced = await archive.async_meta(key)
            if synced:
                try:
                    if time.time() - float(synced) < SYNC_TTL_SECONDS:
                        continue
                except ValueError:
                    pass
            count = await _sync_tile(
                hass, archive, center_lat, center_lon, TILE_KM
            )
            done += 1
            if count:
                _LOGGER.info(
                    "POI-index: %s plekken toegevoegd (%s/%s tegels)",
                    count,
                    done,
                    max_tiles,
                )
            if done >= max_tiles:
                break
            await asyncio.sleep(1.0)
    return done


async def async_sync_archive_tiles(
    hass: HomeAssistant,
    archive: Archive,
    max_tiles: int | None = None,
) -> int:
    """Index tiles from everywhere in the archive, newest places first.

    This is what keeps the search future-proof: Amsterdam, Vienna or any other
    place you have visit points for is queued automatically, regardless of
    distance from home.  A limited batch runs at startup and every night; the
    remaining tiles follow on later runs.
    """
    if max_tiles is None:
        max_tiles = MAX_TILES_PER_RUN
    cells = await archive.async_poi_cells(limit=20000)
    if not cells:
        return 0

    done = 0
    async with _LOCK:
        for cell in cells:
            key = _tile_key(cell["lat"], cell["lon"], TILE_KM)
            synced = await archive.async_meta(key)
            if synced:
                try:
                    if time.time() - float(synced) < SYNC_TTL_SECONDS:
                        continue
                except ValueError:
                    pass
            count = await _sync_tile(
                hass, archive, cell["lat"], cell["lon"], TILE_KM
            )
            done += 1
            if count:
                _LOGGER.info(
                    "POI-index: %s plekken toegevoegd (%s/%s tegels deze ronde)",
                    count,
                    done,
                    max_tiles,
                )
            if done >= max_tiles:
                break
            await asyncio.sleep(1.0)
    return done
