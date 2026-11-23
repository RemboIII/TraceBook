"""Timeline for family members based on Home Assistant's recorder.

Some household members have no points in the local archive; their location
history lives in Home Assistant's device_tracker entities.  This module turns
that history into the same day structure the Lovelace card already understands,
so they get the same map/calendar/timeline experience.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from functools import partial
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .geo import _distance_m, _simplify_path_with_times, _smooth_path
from .const import DOMAIN, MODE_COLORS

_LOGGER = logging.getLogger(__name__)

STAY_RADIUS_M = 120
STAY_MIN_MINUTES = 8
STAY_MERGE_RADIUS_M = 200
STAY_MERGE_GAP_MINUTES = 30
STAY_EDGE_SPEED_MPS = 1.0
ZONE_MERGE_GAP_MINUTES = 10
ZONE_MERGE_SLACK_M = 50
PLACE_RADIUS_M = 300
JOURNEY_MIN_METERS = 50
JOURNEY_MIN_AVG_KMH = 1.0
HOME_RADIUS_M = 150
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_MIN_INTERVAL = 1.1
NOMINATIM_USER_AGENT = "GeoPulse/2.0 (Home Assistant)"


@dataclass(slots=True)
class Point:
    """One GPS observation from the recorder."""

    time: datetime
    latitude: float
    longitude: float
    state: str
    speed: float | None = None


@dataclass(slots=True)
class Zone:
    """A Home Assistant zone."""

    name: str
    latitude: float | None
    longitude: float | None
    radius: float


def _zone_lookup(hass: HomeAssistant) -> dict[str, Zone]:
    zones: dict[str, Zone] = {}
    for state in hass.states.async_all("zone"):
        slug = state.entity_id.split(".", 1)[1]
        name = str(state.attributes.get("friendly_name") or slug)
        try:
            latitude = float(state.attributes["latitude"])
            longitude = float(state.attributes["longitude"])
            radius = float(state.attributes.get("radius") or 100)
        except (KeyError, TypeError, ValueError):
            latitude = longitude = None
            radius = 100
        zone = Zone(name=name, latitude=latitude, longitude=longitude, radius=radius)
        zones[slug.lower()] = zone
        zones[name.lower()] = zone
    return zones


def _home_coordinates(hass: HomeAssistant) -> tuple[float, float] | None:
    zone = hass.states.get("zone.home")
    if zone is None:
        return None
    try:
        return (
            float(zone.attributes["latitude"]),
            float(zone.attributes["longitude"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _is_home(
    latitude: float,
    longitude: float,
    home: tuple[float, float] | None,
) -> bool:
    if home is None:
        return False
    return _distance_m((latitude, longitude), home) <= HOME_RADIUS_M


async def _async_states(
    hass: HomeAssistant,
    entity_id: str,
    start: datetime,
    end: datetime,
) -> dict[str, list[Any]]:
    recorder = get_instance(hass)
    job = partial(
        get_significant_states,
        hass,
        start,
        end,
        [entity_id],
        include_start_time_state=True,
        significant_changes_only=False,
    )
    return await recorder.async_add_executor_job(job)


def _build_points(
    states: list[Any], start: datetime, end: datetime
) -> list[Point]:
    points: list[Point] = []
    for state in states:
        attributes = state.attributes or {}
        latitude = attributes.get("latitude")
        longitude = attributes.get("longitude")
        if latitude is None or longitude is None:
            continue
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            continue

        timestamp = state.last_updated or state.last_changed
        if timestamp is None:
            continue
        if timestamp < start:
            timestamp = start
        if timestamp > end:
            continue
        speed = attributes.get("speed")
        try:
            speed = float(speed) if speed is not None else None
        except (TypeError, ValueError):
            speed = None
        points.append(
            Point(
                time=timestamp,
                latitude=latitude,
                longitude=longitude,
                state=str(state.state or ""),
                speed=speed,
            )
        )

    points.sort(key=lambda item: item.time)
    return points


def _gap_within_zone(
    points: list[Point],
    begin: datetime,
    finish: datetime,
    zone: Zone,
) -> bool:
    """Return False when points between two zone stays leave the zone.

    A short walk can start and end inside the same zone within ten minutes.
    Merging those two stays would hide the walk, so only join a gap when all
    points in it are still close to the zone centre.
    """
    if zone.latitude is None or zone.longitude is None:
        return True
    limit = zone.radius + ZONE_MERGE_SLACK_M
    for point in points:
        if begin < point.time < finish and _distance_m(
            (point.latitude, point.longitude),
            (zone.latitude, zone.longitude),
        ) > limit:
            return False
    return True


def _zone_visits(
    points: list[Point],
    zones: dict[str, Zone],
    home: tuple[float, float] | None,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    periods: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for point in points:
        zone = zones.get(point.state.lower())
        if zone is not None:
            if current is not None and current["name"] == zone.name:
                current["end"] = point.time
            else:
                if current is not None:
                    periods.append(current)
                latitude = zone.latitude if zone.latitude is not None else point.latitude
                longitude = (
                    zone.longitude if zone.longitude is not None else point.longitude
                )
                current = {
                    "name": zone.name,
                    "start": point.time,
                    "end": point.time,
                    "latitude": latitude,
                    "longitude": longitude,
                    "is_home": zone.name.lower() in ("thuis", "home")
                    or _is_home(latitude, longitude, home),
                    "zone": True,
                }
        elif current is not None:
            periods.append(current)
            current = None
    if current is not None:
        periods.append(current)

    result: list[dict[str, Any]] = []
    for period in periods:
        if period["end"] < start or period["start"] > end:
            continue
        if (period["end"] - period["start"]) < timedelta(minutes=5):
            continue
        period["start"] = max(period["start"], start)
        period["end"] = min(period["end"], end)
        result.append(period)

    result.sort(key=lambda item: item["start"])
    merged: list[dict[str, Any]] = []
    for period in result:
        if merged and merged[-1]["name"] == period["name"]:
            gap = period["start"] - merged[-1]["end"]
            zone = zones.get(period["name"].lower())
            if gap <= timedelta(minutes=ZONE_MERGE_GAP_MINUTES) and (
                zone is None
                or _gap_within_zone(
                    points, merged[-1]["end"], period["start"], zone
                )
            ):
                merged[-1]["end"] = period["end"]
                continue
        merged.append(period)

    # If the last sample still reports a zone, the person stayed there until
    # the end of the day as far as Home Assistant knows.
    if merged and points and points[-1].state.lower() in zones:
        last_zone = zones[points[-1].state.lower()]
        if merged[-1]["name"] == last_zone.name and (
            end - merged[-1]["end"]
        ) <= timedelta(hours=8):
            merged[-1]["end"] = end

    return merged


def _step_speed_mps(first: Point, second: Point) -> float:
    seconds = (second.time - first.time).total_seconds()
    if seconds <= 0:
        return 0.0
    return (
        _distance_m(
            (first.latitude, first.longitude),
            (second.latitude, second.longitude),
        )
        / seconds
    )


def _gps_stays(
    points: list[Point],
    occupied: list[tuple[datetime, datetime]],
    zones: dict[str, Zone],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Find stationary periods in the points that are not inside a zone."""

    def inside_occupied(moment: datetime) -> bool:
        return any(begin <= moment <= finish for begin, finish in occupied)

    free = [point for point in points if not inside_occupied(point.time)]
    stays: list[dict[str, Any]] = []

    index = 0
    while index < len(free):
        base = free[index]
        last = index
        while last + 1 < len(free):
            candidate = free[last + 1]
            if (
                _distance_m(
                    (base.latitude, base.longitude),
                    (candidate.latitude, candidate.longitude),
                )
                <= STAY_RADIUS_M
                and (candidate.time - base.time) <= timedelta(hours=12)
            ):
                last += 1
            else:
                break

        duration = free[last].time - base.time
        if duration >= timedelta(minutes=STAY_MIN_MINUTES):
            # Walking out of a stay stays within the search radius for a
            # while.  Trim those moving edges so the walk becomes a route
            # instead of being swallowed by the visit.
            begin, finish = index, last
            while begin < finish and (
                _step_speed_mps(free[begin], free[begin + 1])
                > STAY_EDGE_SPEED_MPS
            ):
                begin += 1
            while finish > begin and (
                _step_speed_mps(free[finish - 1], free[finish])
                > STAY_EDGE_SPEED_MPS
            ):
                finish -= 1
            if (
                free[finish].time - free[begin].time
                >= timedelta(minutes=STAY_MIN_MINUTES)
            ):
                segment = free[begin : finish + 1]
                states = [point.state for point in segment if point.state]
                stays.append(
                    {
                        "start": free[begin].time,
                        "end": free[finish].time,
                        "latitude": mean(point.latitude for point in segment),
                        "longitude": mean(point.longitude for point in segment),
                        "count": len(segment),
                        "states": states,
                    }
                )
                index = finish + 1
            else:
                index = last + 1
        else:
            index += 1

    stays.sort(key=lambda item: item["start"])
    merged: list[dict[str, Any]] = []
    for stay in stays:
        if (
            merged
            and _distance_m(
                (merged[-1]["latitude"], merged[-1]["longitude"]),
                (stay["latitude"], stay["longitude"]),
            )
            <= STAY_MERGE_RADIUS_M
            and (stay["start"] - merged[-1]["end"])
            <= timedelta(minutes=STAY_MERGE_GAP_MINUTES)
        ):
            previous = merged[-1]
            total = previous["count"] + stay["count"]
            previous["latitude"] = (
                previous["latitude"] * previous["count"]
                + stay["latitude"] * stay["count"]
            ) / total
            previous["longitude"] = (
                previous["longitude"] * previous["count"]
                + stay["longitude"] * stay["count"]
            ) / total
            previous["end"] = stay["end"]
            previous["count"] = total
            previous["states"].extend(stay["states"])
        else:
            merged.append(stay)

    result: list[dict[str, Any]] = []
    for stay in merged:
        stay["start"] = max(stay["start"], start)
        stay["end"] = min(stay["end"], end)
        stay["name"] = _stay_zone_name(stay.get("states") or [], zones)
        stay["is_home"] = _is_home(
            stay["latitude"], stay["longitude"], _home_coordinates_cache
        )
        stay["zone"] = False
        result.append(stay)
    return [stay for stay in result if stay["end"] > stay["start"]]


def _stay_zone_name(states: list[str], zones: dict[str, Zone]) -> str:
    if not states:
        return ""
    common = max(set(states), key=states.count)
    zone = zones.get(common.lower())
    return zone.name if zone is not None else ""


def _nearest_place(
    places: list[dict[str, Any]], latitude: float, longitude: float
) -> dict[str, Any] | None:
    best = None
    best_distance = PLACE_RADIUS_M
    for place in places:
        place_lat = place.get("latitude")
        place_lng = place.get("longitude")
        if place_lat is None or place_lng is None:
            continue
        distance = _distance_m(
            (latitude, longitude), (float(place_lat), float(place_lng))
        )
        if distance < best_distance:
            best_distance = distance
            best = place
    return best


def _journey_mode(
    distance_m: float, duration_s: float, p75_kmh: float
) -> str | None:
    if duration_s <= 0:
        return None
    average = distance_m / duration_s * 3.6
    if distance_m < JOURNEY_MIN_METERS or average < JOURNEY_MIN_AVG_KMH:
        return None
    speed = p75_kmh if p75_kmh > 0 else average
    if speed <= 7:
        return "walking"
    if speed <= 20:
        return "cycling"
    return "driving"


def _step_class(speed: float) -> str:
    if speed <= 2.5:
        return "walking"
    if speed <= 7.0:
        return "cycling"
    return "driving"


def _split_group_by_mode(points: list[Point]) -> list[list[Point]]:
    """Split one movement group into walking/cycling/driving parts.

    The archive only contains raw points, so a rolling median of the step
    speed is used to find the moments
    where someone parked the car and continued on foot, without splitting on
    a single noisy GPS fix.
    """
    if len(points) < 6:
        return [points]

    speeds: list[float] = []
    for first, second in zip(points, points[1:]):
        distance = _distance_m(
            (first.latitude, first.longitude),
            (second.latitude, second.longitude),
        )
        seconds = (second.time - first.time).total_seconds()
        speeds.append(distance / seconds if seconds > 0 else 0.0)

    classes: list[str] = []
    for index in range(len(speeds)):
        window = sorted(speeds[max(0, index - 2) : index + 3])
        classes.append(_step_class(window[len(window) // 2]))

    raw: list[tuple[int, int, str]] = []
    start = 0
    for index in range(1, len(classes)):
        if classes[index] != classes[start]:
            raw.append((start, index, classes[start]))
            start = index
    raw.append((start, len(classes), classes[start]))

    merged: list[tuple[int, int, str]] = []
    carry: int | None = None
    for segment in raw:
        if merged and (segment[1] - segment[0]) < 3:
            previous = merged[-1]
            merged[-1] = (previous[0], segment[1], previous[2])
        elif (
            not merged
            and (segment[1] - segment[0]) < 3
            and len(raw) > 1
        ):
            # Short noisy start: fold its points into the next segment.
            # Skipping it entirely left a hole at the start of the route
            # (for example the first kilometre after leaving a visit).
            if carry is None:
                carry = segment[0]
            continue
        else:
            begin = carry if carry is not None else segment[0]
            carry = None
            merged.append((begin, segment[1], segment[2]))

    if not merged:
        return [points]

    groups: list[list[Point]] = []
    for begin, finish, _mode in merged:
        group = points[begin : finish + 1]
        if len(group) >= 2:
            groups.append(group)
    return groups or [points]


def _snap_routes_to_visits(
    routes: list[dict[str, Any]],
    visits: list[dict[str, Any]],
    max_distance_m: float = 400.0,
    max_gap_minutes: float = 15.0,
) -> None:
    """Connect a route's ends to the visit just before/after it.

    Stop detection keeps the GPS points around a visit out of the journey, so
    the drawn route can stop a few hundred metres short of the visit pin.
    Adding the visit coordinate closes that gap without changing distances.
    """

    def moment(value: Any) -> datetime | None:
        try:
            return datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None

    for route in routes:
        coordinates = route.get("coordinates") or []
        if not coordinates:
            continue
        times = list(route.get("times") or [])
        start = moment(route.get("start"))
        end = moment(route.get("end"))

        def best_match(
            target: datetime, attribute: str
        ) -> tuple[dict[str, Any], tuple[float, float]] | None:
            """Pick the nearest visit in time, not every visit within range."""
            best: tuple[dict[str, Any], tuple[float, float]] | None = None
            best_delta: float | None = None
            for visit in visits:
                visit_moment = moment(visit.get(attribute))
                if visit_moment is None:
                    continue
                delta = abs((visit_moment - target).total_seconds())
                if delta > max_gap_minutes * 60:
                    continue
                try:
                    center = (
                        float(visit["latitude"]),
                        float(visit["longitude"]),
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                point = coordinates[-1] if attribute == "start" else coordinates[0]
                if not 2 < _distance_m((point[0], point[1]), center) <= max_distance_m:
                    continue
                if best_delta is None or delta < best_delta:
                    best = (visit, center)
                    best_delta = delta
            return best

        if end is not None:
            match = best_match(end, "start")
            if match is not None:
                visit, center = match
                coordinates.append([round(center[0], 5), round(center[1], 5)])
                if times:
                    times.append(
                        str(visit.get("start") or route.get("end") or "")
                    )
        if start is not None:
            match = best_match(start, "end")
            if match is not None:
                visit, center = match
                coordinates.insert(
                    0, [round(center[0], 5), round(center[1], 5)]
                )
                if times:
                    times.insert(
                        0, str(visit.get("end") or route.get("start") or "")
                    )
        route["coordinates"] = coordinates
        if times:
            route["times"] = times


def _journey_stats(points: list[Point]) -> tuple[float, float, float]:
    distance = 0.0
    speeds: list[float] = []
    for first, second in zip(points, points[1:]):
        segment = _distance_m(
            (first.latitude, first.longitude),
            (second.latitude, second.longitude),
        )
        distance += segment
        seconds = (second.time - first.time).total_seconds()
        if seconds >= 5:
            speeds.append(segment / seconds * 3.6)
    duration = (points[-1].time - points[0].time).total_seconds()
    speeds.sort()
    p75 = speeds[int(len(speeds) * 0.75)] if speeds else 0.0
    return distance, duration, p75


def _drop_overlapping_visits(
    visits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep zone visits when a GPS stay happens to overlap one."""
    result: list[dict[str, Any]] = []
    for visit in sorted(visits, key=lambda item: (not item.get("zone"), item["start"])):
        if any(
            visit["start"] < other["end"] and other["start"] < visit["end"]
            for other in result
        ):
            continue
        result.append(visit)
    result.sort(key=lambda item: item["start"])
    return result


def _merge_visits_without_journey(
    visits: list[dict[str, Any]], journeys: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge same-place visits when no journey was detected in between.

    This removes artificial splits caused by a short GPS dropout, without
    hiding real trips (those have a journey row between the visits).
    """
    if len(visits) < 2:
        return visits

    journey_times = [
        (datetime.fromisoformat(item["start"]), datetime.fromisoformat(item["end"]))
        for item in journeys
    ]
    merged: list[dict[str, Any]] = []
    for visit in visits:
        if not merged:
            merged.append(visit)
            continue
        previous = merged[-1]
        previous_end = datetime.fromisoformat(previous["end"])
        current_start = datetime.fromisoformat(visit["start"])
        gap = current_start - previous_end
        has_journey = any(
            begin < current_start and finish > previous_end
            for begin, finish in journey_times
        )
        same_place = (
            previous["name"] == visit["name"]
            and _distance_m(
                (previous["latitude"], previous["longitude"]),
                (visit["latitude"], visit["longitude"]),
            )
            <= 300
        )
        if same_place and gap <= timedelta(minutes=90) and not has_journey:
            previous["end"] = visit["end"]
            previous["duration_minutes"] = int(
                (
                    datetime.fromisoformat(previous["end"])
                    - datetime.fromisoformat(previous["start"])
                ).total_seconds()
                / 60
            )
            continue
        merged.append(visit)
    return merged


def _visit_subtitle(
    visit: dict[str, Any], places: list[dict[str, Any]]
) -> str:
    if visit.get("is_home"):
        return "Thuiszone"
    place = _nearest_place(places, visit["latitude"], visit["longitude"])
    if place is not None and place.get("name") != visit.get("name"):
        return str(place.get("name") or "")
    return f"{visit['latitude']:.4f}, {visit['longitude']:.4f}"


_geocode_cache: dict[str, str | None] = {}
_geocode_lock = asyncio.Lock()
_geocode_last_request = 0.0


def _geocode_key(latitude: float, longitude: float) -> str:
    return f"{latitude:.3f},{longitude:.3f}"


def _geocode_label(payload: dict[str, Any]) -> str | None:
    """Turn a Nominatim response into a short, readable Dutch label."""
    address = payload.get("address") or {}
    local = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("suburb")
    )

    for key in ("amenity", "shop", "tourism", "leisure", "building", "square"):
        candidate = address.get(key)
        if candidate:
            label = str(candidate).strip()
            if label and label.lower() not in {"locatie", "unknown"}:
                if local and local.lower() not in label.lower():
                    return f"{label}, {local}"
                return label

    road = (
        address.get("road")
        or address.get("pedestrian")
        or address.get("footway")
        or address.get("square")
    )
    if road:
        label = str(road).strip()
        house_number = address.get("house_number")
        if house_number:
            label = f"{label} {house_number}"
        if local and local.lower() not in label.lower():
            return f"{label}, {local}"
        return label

    name = payload.get("name")
    if name:
        label = str(name).strip()
        if local and local.lower() not in label.lower():
            return f"{label}, {local}"
        return label

    return str(local).strip() if local else None


async def _async_reverse_geocode(
    hass: HomeAssistant, latitude: float, longitude: float
) -> str | None:
    """Look up a place name for an unknown location, with a small cache."""
    key = _geocode_key(latitude, longitude)
    if key in _geocode_cache:
        return _geocode_cache[key]

    global _geocode_last_request
    async with _geocode_lock:
        if key in _geocode_cache:
            return _geocode_cache[key]

        wait = NOMINATIM_MIN_INTERVAL - (time.monotonic() - _geocode_last_request)
        if wait > 0:
            await asyncio.sleep(wait)

        session = async_get_clientsession(hass)
        label: str | None = None
        try:
            async with session.get(
                NOMINATIM_URL,
                params={
                    "format": "jsonv2",
                    "lat": f"{latitude:.6f}",
                    "lon": f"{longitude:.6f}",
                    "zoom": 18,
                    "addressdetails": 1,
                    "accept-language": "nl",
                },
                headers={"User-Agent": NOMINATIM_USER_AGENT},
                timeout=10,
            ) as response:
                if response.status == 200:
                    label = _geocode_label(await response.json())
                else:
                    _LOGGER.debug(
                        "Nominatim gaf status %s voor %s", response.status, key
                    )
        except Exception as err:  # noqa: BLE001 - geocoding is optional
            _LOGGER.debug("Nominatim reverse geocoding mislukt voor %s: %s", key, err)
        finally:
            _geocode_last_request = time.monotonic()

    _geocode_cache[key] = label
    return label


async def _async_apply_geocoding(
    hass: HomeAssistant, day: dict[str, Any]
) -> None:
    """Replace generic "Locatie" visits with a real place name."""
    for entry in day.get("entries") or []:
        if entry.get("type") != "visit" or entry.get("is_home"):
            continue
        if entry.get("name") != "Locatie":
            continue
        latitude = entry.get("latitude")
        longitude = entry.get("longitude")
        if latitude is None or longitude is None:
            continue
        label = await _async_reverse_geocode(
            hass, float(latitude), float(longitude)
        )
        if not label:
            continue
        entry["name"] = label
        entry["place_name"] = label
        entry["subtitle"] = ""

    day["summary"]["places"] = len(
        {
            entry.get("name")
            for entry in day.get("entries") or []
            if entry.get("type") == "visit" and entry.get("name")
        }
    )


def _bounds(points: list[Point]) -> list[list[float]] | None:
    if not points:
        return None
    return [
        [
            min(point.latitude for point in points),
            min(point.longitude for point in points),
        ],
        [
            max(point.latitude for point in points),
            max(point.longitude for point in points),
        ],
    ]


def _empty_day(day: date) -> dict[str, Any]:
    return {
        "date": day.isoformat(),
        "summary": {
            "distance": 0,
            "unit": "km",
            "places": 0,
            "moving_minutes": 0,
            "stationary_minutes": 0,
            "suggested": 0,
            "confirmed": 0,
            "modes": [],
        },
        "bounds": None,
        "entries": [],
        "routes": [],
    }


_home_coordinates_cache: tuple[float, float] | None = None


def _build_day(
    hass: HomeAssistant,
    entity_id: str,
    day: date,
    points: list[Point],
    places: list[dict[str, Any]],
    tz: ZoneInfo,
) -> dict[str, Any]:
    global _home_coordinates_cache

    start = datetime.combine(day, dt_time.min, tzinfo=tz)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    home = _home_coordinates(hass)
    _home_coordinates_cache = home
    zones = _zone_lookup(hass)

    day_points = [point for point in points if start <= point.time <= end]
    if not day_points:
        return _empty_day(day)

    zone_visits = _zone_visits(day_points, zones, home, start, end)
    occupied = [(visit["start"], visit["end"]) for visit in zone_visits]
    gps_visits = _gps_stays(day_points, occupied, zones, start, end)

    visits = _drop_overlapping_visits(zone_visits + gps_visits)

    for index, visit in enumerate(visits):
        visit["type"] = "visit"
        visit["key"] = f"ha-visit-{index}"
        visit["visit_id"] = visit["key"]
        visit["status"] = "confirmed"
        visit["confidence"] = "high"
        visit["place_id"] = None
        visit["editable"] = False
        visit["editable_name"] = None
        visit["suggested_places"] = []
        if not visit.get("name"):
            place = _nearest_place(places, visit["latitude"], visit["longitude"])
            if place is not None:
                visit["name"] = place["name"]
                visit["place_id"] = place.get("id")
            else:
                visit["name"] = "Locatie"
        if visit.get("is_home"):
            visit["name"] = "Thuis"
        visit["place_name"] = visit["name"]
        visit["subtitle"] = _visit_subtitle(visit, places)
        visit["duration_minutes"] = int(
            (visit["end"] - visit["start"]).total_seconds() / 60
        )
        visit["start"] = visit["start"].isoformat()
        visit["end"] = visit["end"].isoformat()

    # Points outside the visits are journeys.
    visit_times = [
        (
            datetime.fromisoformat(visit["start"]),
            datetime.fromisoformat(visit["end"]),
        )
        for visit in visits
    ]
    outside = [
        point
        for point in day_points
        if not any(begin <= point.time <= finish for begin, finish in visit_times)
    ]

    groups: list[list[Point]] = []
    current: list[Point] = []
    for point in outside:
        if current:
            gap = point.time - current[-1].time
            crossed_visit = any(
                current[-1].time < begin and finish < point.time
                for begin, finish in visit_times
            )
            if gap > timedelta(hours=2) or crossed_visit:
                groups.append(current)
                current = []
        current.append(point)
    if current:
        groups.append(current)

    parts: list[tuple[list[Point], float, float, float, str]] = []
    for group in groups:
        for segment in _split_group_by_mode(group):
            if len(segment) < 2:
                continue
            distance, duration, p75 = _journey_stats(segment)
            mode = _journey_mode(distance, duration, p75)
            if mode is None:
                continue
            parts.append((segment, distance, duration, p75, mode))

    # Short slow stretches (traffic lights, parking) can look like a different
    # mode.  Join consecutive pieces again when the final mode matches and the
    # pause between them is small, so one drive stays one block.
    merged_parts: list[tuple[list[Point], float, float, float, str]] = []
    for part in parts:
        if (
            merged_parts
            and merged_parts[-1][4] == part[4]
            and (part[0][0].time - merged_parts[-1][0][-1].time)
            <= timedelta(minutes=10)
        ):
            previous = merged_parts[-1]
            combined = previous[0] + part[0]
            distance, duration, p75 = _journey_stats(combined)
            merged_parts[-1] = (combined, distance, duration, p75, previous[4])
        else:
            merged_parts.append(part)

    journeys: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []
    journey_index = 0
    for segment, distance, duration, _p75, mode in merged_parts:
            index = journey_index
            journey_index += 1
            track_id = f"ha-{entity_id.replace('.', '-')}-{index}"
            start_iso = segment[0].time.isoformat()
            end_iso = segment[-1].time.isoformat()
            journey = {
                "type": "journey",
                "key": f"ha-journey-{index}",
                "track_id": track_id,
                "track_ids": [track_id],
                "mode": mode,
                "color": MODE_COLORS.get(mode, MODE_COLORS["unknown"]),
                "start": start_iso,
                "end": end_iso,
                "duration_seconds": int(duration),
                "distance": round(distance / 1000, 1),
                "distance_unit": "km",
                "continued": False,
                "editable": False,
                "note": "",
                "merged": False,
            }
            journeys.append(journey)
            raw_coords = [
                (point.latitude, point.longitude) for point in segment
            ]
            raw_times = [point.time.isoformat() for point in segment]
            if mode in ("walking", "running"):
                # Walking tracks are short and benefit from more detail and a
                # light smoothing pass; driving tracks stay compact.
                raw_coords = _smooth_path(raw_coords, passes=1)
                min_m = 0.7
                max_points = 3000
            else:
                min_m = 1.2
                max_points = 1600
            coordinates, times = _simplify_path_with_times(
                raw_coords,
                raw_times,
                min_m=min_m,
                max_points=max_points,
            )
            routes.append(
                {
                    "track_id": track_id,
                    "mode": mode,
                    "color": MODE_COLORS.get(mode, MODE_COLORS["unknown"]),
                    "coordinates": coordinates,
                    "times": times,
                    "distance": journey["distance"],
                    "duration_seconds": journey["duration_seconds"],
                    "start": start_iso,
                    "end": end_iso,
                }
            )

    _snap_routes_to_visits(routes, visits)

    visits = _merge_visits_without_journey(visits, journeys)

    entries = visits + journeys
    entries.sort(key=lambda item: item["start"])

    mode_totals: dict[str, float] = {}
    for journey in journeys:
        mode = journey["mode"]
        if mode in ("stationary", "unknown", "mixed"):
            continue
        mode_totals[mode] = mode_totals.get(mode, 0.0) + float(
            journey["distance"]
        )

    distance_total = round(sum(float(item["distance"]) for item in journeys), 1)
    moving_minutes = int(
        round(sum(float(item["duration_seconds"]) for item in journeys) / 60)
    )
    stationary_minutes = int(
        round(
            sum(
                float(item["duration_minutes"])
                for item in visits
                if item["type"] == "visit"
            )
        )
    )

    return {
        "date": day.isoformat(),
        "summary": {
            "distance": distance_total,
            "unit": "km",
            "places": len({visit["name"] for visit in visits}),
            "moving_minutes": moving_minutes,
            "stationary_minutes": stationary_minutes,
            "suggested": 0,
            "confirmed": 0,
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
        },
        "bounds": _bounds(day_points),
        "entries": entries,
        "routes": routes,
    }


async def _local_places(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Saved places from the local archive, in the shape ``_build_day`` wants."""
    archive = (hass.data.get(DOMAIN) or {}).get("archive")
    if archive is None:
        return []
    try:
        rows = await archive.async_places(limit=500)
    except Exception as err:  # noqa: BLE001 - places are a nice-to-have
        _LOGGER.debug("Kon opgeslagen plekken niet laden: %s", err)
        return []
    return [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "latitude": row.get("lat"),
            "longitude": row.get("lon"),
        }
        for row in rows
        if row.get("lat") is not None and row.get("lon") is not None
    ]


async def get_ha_day(
    hass: HomeAssistant,
    entity_id: str,
    day_str: str,
) -> dict[str, Any]:
    tz = ZoneInfo(hass.config.time_zone)
    day = date.fromisoformat(day_str)
    start = datetime.combine(day, dt_time.min, tzinfo=tz)
    end = start + timedelta(days=1) - timedelta(seconds=1)

    states_by_entity = await _async_states(hass, entity_id, start, end)
    points = _build_points(states_by_entity.get(entity_id, []), start, end)

    places = await _local_places(hass)

    result = _build_day(hass, entity_id, day, points, places, tz)
    if (hass.data.get(DOMAIN) or {}).get("geocode", True):
        await _async_apply_geocoding(hass, result)
    return result


async def get_ha_month(
    hass: HomeAssistant,
    entity_id: str,
    year: int,
    month: int,
) -> dict[str, Any]:
    tz = ZoneInfo(hass.config.time_zone)
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    start = datetime.combine(first, dt_time.min, tzinfo=tz)
    end = datetime.combine(last, dt_time.min, tzinfo=tz) + timedelta(
        days=1
    ) - timedelta(seconds=1)

    states_by_entity = await _async_states(hass, entity_id, start, end)
    points = _build_points(states_by_entity.get(entity_id, []), start, end)

    places = await _local_places(hass)

    by_day: dict[date, list[Point]] = {}
    for point in points:
        local = point.time.astimezone(tz).date()
        by_day.setdefault(local, []).append(point)

    previous: Point | None = None
    summaries: dict[str, Any] = {}
    current = first
    while current <= last:
        day_points = list(by_day.get(current, []))
        if previous is not None:
            day_start = datetime.combine(current, dt_time.min, tzinfo=tz)
            if day_start - previous.time <= timedelta(hours=6):
                day_points.insert(
                    0,
                    Point(
                        time=day_start,
                        latitude=previous.latitude,
                        longitude=previous.longitude,
                        state=previous.state,
                        speed=previous.speed,
                    ),
                )
        if day_points:
            built = _build_day(
                hass, entity_id, current, day_points, places, tz
            )
            summaries[current.isoformat()] = {
                "visits": sum(
                    1 for item in built["entries"] if item.get("type") == "visit"
                ),
                "journeys": sum(
                    1 for item in built["entries"] if item.get("type") == "journey"
                ),
                "distance": built["summary"]["distance"],
                "suggested": 0,
            }
            previous = day_points[-1]
        current += timedelta(days=1)

    return {"year": year, "month": month, "days": summaries}
