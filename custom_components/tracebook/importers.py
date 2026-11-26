"""Import location history from GPX, GeoJSON and Google Timeline exports.

The archive is the only location store TraceBook uses, so there is no API
coupling with other services.  Historical data is imported from files instead:

* GPX (track points, route points and waypoints with a timestamp)
* GeoJSON (point features, or line features with ``coordTimes``)
* Google Timeline exports:
  - ``Records.json`` from Google Takeout (legacy raw points)
  - ``Semantic Location History/YYYY/YYYY_MONTH.json`` (legacy visits/trips)
  - ``Timeline.json`` from the Android Timeline export
  - ``location-history.json`` from the iOS Timeline export
* A ZIP with any combination of the above.

Every format is reduced to the same thing: timestamped points.  Visits and
journeys are derived from those points by the normal timeline builder.
"""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree

_LOGGER = logging.getLogger(__name__)

#: Files in a Google Takeout archive that never contain location history.
SKIP_NAMES = {"settings.json", "timeline edits.json", "readme.md"}

MAX_POINTS_PER_FILE = 5_000_000

Point = dict[str, Any]


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp(value: Any) -> float | None:
    """Parse an ISO string, epoch seconds or epoch milliseconds."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        # Milliseconds are ~1e12, seconds ~1e9.
        if number > 10_000_000_000:
            number /= 1000.0
        return number if number > 0 else None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return _timestamp(float(text))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _point(
    ts: float | None,
    lat: Any,
    lon: Any,
    *,
    accuracy: Any = None,
    speed: Any = None,
    altitude: Any = None,
    source: str = "import",
) -> Point | None:
    latitude = _number(lat)
    longitude = _number(lon)
    if ts is None or latitude is None or longitude is None:
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    if latitude == 0 and longitude == 0:
        return None
    return {
        "ts": float(ts),
        "lat": latitude,
        "lon": longitude,
        "accuracy": _number(accuracy),
        "speed": _number(speed),
        "altitude": _number(altitude),
        "source": source,
    }


def _coordinate(value: Any) -> tuple[float, float] | None:
    """Parse the coordinate shapes used by the Timeline exports."""
    if value is None:
        return None
    if isinstance(value, dict):
        if "latLng" in value:
            return _coordinate(value["latLng"])
        latitude = _number(value.get("lat") or value.get("latitude"))
        longitude = _number(value.get("lon") or value.get("lng") or value.get("longitude"))
        if latitude is not None and longitude is not None:
            return latitude, longitude
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        latitude = _number(value[0])
        longitude = _number(value[1])
        if latitude is not None and longitude is not None:
            return latitude, longitude
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("geo:", "").replace("°", "")
    parts = [part for part in re.split(r"[, ]+", text) if part]
    if len(parts) < 2:
        return None
    latitude = _number(parts[0])
    longitude = _number(parts[1])
    if latitude is None or longitude is None:
        return None
    return latitude, longitude


def _e7(latitude: Any, longitude: Any) -> tuple[float, float] | None:
    lat = _number(latitude)
    lon = _number(longitude)
    if lat is None or lon is None:
        return None
    return lat / 10_000_000, lon / 10_000_000


# ---------------------------------------------------------------------------
# GPX
# ---------------------------------------------------------------------------


def parse_gpx(text: str) -> list[Point]:
    points: list[Point] = []
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as err:
        _LOGGER.debug("GPX parsefout: %s", err)
        return points

    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in ("trkpt", "rtpt", "wpt"):
            continue
        latitude = element.get("lat")
        longitude = element.get("lon")
        stamp = None
        accuracy = None
        altitude = None
        for child in element:
            child_tag = child.tag.rsplit("}", 1)[-1]
            if child_tag == "time" and child.text:
                stamp = _timestamp(child.text)
            elif child_tag == "ele" and child.text:
                altitude = child.text
        point = _point(
            stamp,
            latitude,
            longitude,
            accuracy=accuracy,
            altitude=altitude,
            source="gpx",
        )
        if point is not None:
            points.append(point)
    return points


# ---------------------------------------------------------------------------
# GeoJSON
# ---------------------------------------------------------------------------


def _geojson_line(feature: dict[str, Any]) -> list[Point]:
    geometry = feature.get("geometry") or {}
    kind = geometry.get("type")
    properties = feature.get("properties") or {}
    times = (
        properties.get("coordTimes")
        or properties.get("times")
        or properties.get("timestamps")
        or properties.get("timestampsMs")
    )
    points: list[Point] = []

    def add(coords: Any, stamps: Any = None) -> None:
        if not isinstance(coords, list):
            return
        for index, coordinate in enumerate(coords):
            if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
                continue
            stamp = None
            if isinstance(stamps, list) and index < len(stamps):
                stamp = _timestamp(stamps[index])
            if stamp is None:
                stamp = _timestamp(
                    properties.get("timestamp") or properties.get("time")
                )
            point = _point(
                stamp,
                coordinate[1],
                coordinate[0],
                altitude=coordinate[2] if len(coordinate) > 2 else None,
                source="geojson",
            )
            if point is not None:
                points.append(point)

    if kind == "LineString":
        add(geometry.get("coordinates"), times)
    elif kind == "MultiLineString":
        for index, line in enumerate(geometry.get("coordinates") or []):
            stamps = times[index] if isinstance(times, list) and index < len(times) else None
            add(line, stamps)
    return points


def parse_geojson(document: Any) -> list[Point]:
    features: list[dict[str, Any]] = []
    if isinstance(document, dict):
        if document.get("type") == "FeatureCollection":
            features = list(document.get("features") or [])
        elif document.get("type") == "Feature":
            features = [document]
        elif "features" in document:
            features = list(document.get("features") or [])
        else:
            return []
    elif isinstance(document, list):
        features = [item for item in document if isinstance(item, dict)]

    points: list[Point] = []
    for feature in features:
        geometry = (feature.get("geometry") or {}) if isinstance(feature, dict) else {}
        kind = geometry.get("type")
        if kind == "Point":
            coordinates = geometry.get("coordinates") or []
            properties = feature.get("properties") or {}
            if len(coordinates) >= 2:
                point = _point(
                    _timestamp(
                        properties.get("timestamp")
                        or properties.get("time")
                        or properties.get("ts")
                    ),
                    coordinates[1],
                    coordinates[0],
                    altitude=coordinates[2] if len(coordinates) > 2 else None,
                    accuracy=properties.get("accuracy"),
                    speed=properties.get("speed"),
                    source="geojson",
                )
                if point is not None:
                    points.append(point)
        else:
            points.extend(_geojson_line(feature))
    return points


# ---------------------------------------------------------------------------
# Google Timeline
# ---------------------------------------------------------------------------


def _google_place(visit: dict[str, Any]) -> dict[str, Any] | None:
    candidate = (visit or {}).get("topCandidate") or {}
    location = candidate.get("placeLocation")
    coordinate = _coordinate(location) if location is not None else None
    if coordinate is None:
        location = (visit or {}).get("location") or {}
        coordinate = _e7(location.get("latitudeE7"), location.get("longitudeE7"))
        name = location.get("name")
        address = location.get("address")
    else:
        name = candidate.get("name")
        address = candidate.get("address")
    if coordinate is None:
        return None
    place = {
        "name": (name or "").strip(),
        "lat": coordinate[0],
        "lon": coordinate[1],
        "address": (address or "").strip() or None,
    }
    return place if place["name"] else None


def parse_google(document: Any) -> tuple[list[Point], list[dict[str, Any]]]:
    """Parse Android/iOS/legacy Google Timeline exports."""
    points: list[Point] = []
    places: list[dict[str, Any]] = []

    if isinstance(document, dict) and "locations" in document:
        for entry in document.get("locations") or []:
            if not isinstance(entry, dict):
                continue
            coordinate = _e7(entry.get("latitudeE7"), entry.get("longitudeE7"))
            if coordinate is None:
                continue
            stamp = _timestamp(
                entry.get("timestamp")
                or entry.get("timestampMs")
                or entry.get("timestamp_ms")
            )
            point = _point(
                stamp,
                coordinate[0],
                coordinate[1],
                accuracy=entry.get("accuracy"),
                altitude=entry.get("altitude"),
                speed=entry.get("velocity"),
                source="google",
            )
            if point is not None:
                points.append(point)
        return points, places

    if isinstance(document, dict) and "timelineObjects" in document:
        for item in document.get("timelineObjects") or []:
            if not isinstance(item, dict):
                continue
            visit = item.get("placeVisit") or {}
            if visit:
                location = visit.get("location") or {}
                coordinate = _e7(
                    location.get("latitudeE7"), location.get("longitudeE7")
                )
                duration = visit.get("duration") or {}
                stamp = _timestamp(duration.get("startTimestamp"))
                if coordinate is not None and stamp is not None:
                    point = _point(
                        stamp,
                        coordinate[0],
                        coordinate[1],
                        source="google",
                    )
                    if point is not None:
                        points.append(point)
                place = _google_place(visit)
                if place is not None:
                    places.append(place)
                continue

            segment = item.get("activitySegment") or {}
            if not segment:
                continue
            duration = segment.get("duration") or {}
            start = _timestamp(duration.get("startTimestamp"))
            end = _timestamp(duration.get("endTimestamp"))
            for key, stamp in (
                ("startLocation", start),
                ("endLocation", end),
            ):
                location = segment.get(key) or {}
                coordinate = _e7(
                    location.get("latitudeE7"), location.get("longitudeE7")
                )
                if coordinate is not None:
                    point = _point(
                        stamp, coordinate[0], coordinate[1], source="google"
                    )
                    if point is not None:
                        points.append(point)
            raw = (segment.get("simplifiedRawPath") or {}).get("points") or []
            for entry in raw:
                coordinate = _e7(entry.get("latE7"), entry.get("lngE7"))
                if coordinate is None:
                    continue
                point = _point(
                    _timestamp(entry.get("timestamp")),
                    coordinate[0],
                    coordinate[1],
                    accuracy=entry.get("accuracyMeters"),
                    source="google",
                )
                if point is not None:
                    points.append(point)
        return points, places

    segments: list[Any] = []
    if isinstance(document, dict):
        segments = list(document.get("semanticSegments") or [])
        raw_signals = list(document.get("rawSignals") or [])
    elif isinstance(document, list):
        segments = document
        raw_signals = []

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        start = _timestamp(segment.get("startTime"))

        for path in segment.get("timelinePath") or []:
            coordinate = _coordinate(path.get("point"))
            if coordinate is None:
                continue
            stamp = _timestamp(path.get("time"))
            if stamp is None:
                relative = _number(path.get("durationMinutesOffsetFromStartTime"))
                if start is not None and relative is not None:
                    stamp = start + relative * 60
            point = _point(
                stamp, coordinate[0], coordinate[1], source="google"
            )
            if point is not None:
                points.append(point)

        visit = segment.get("visit")
        if visit:
            coordinate = _coordinate(
                ((visit.get("topCandidate") or {}).get("placeLocation"))
            )
            if coordinate is not None:
                point = _point(
                    start, coordinate[0], coordinate[1], source="google"
                )
                if point is not None:
                    points.append(point)
                place = _google_place(visit)
                if place is not None:
                    places.append(place)

        activity = segment.get("activity")
        if activity:
            end = _timestamp(segment.get("endTime"))
            for key, stamp in (("start", start), ("end", end)):
                coordinate = _coordinate((activity.get(key) or {}).get("latLng"))
                if coordinate is None:
                    coordinate = _coordinate(activity.get(key))
                if coordinate is not None:
                    point = _point(
                        stamp, coordinate[0], coordinate[1], source="google"
                    )
                    if point is not None:
                        points.append(point)

    for signal in raw_signals:
        position = (signal or {}).get("position") or {}
        coordinate = _coordinate(
            position.get("LatLng") or position.get("latLng")
        )
        if coordinate is None:
            continue
        point = _point(
            _timestamp(position.get("timestamp")),
            coordinate[0],
            coordinate[1],
            accuracy=position.get("accuracyMeters"),
            altitude=position.get("altitudeMeters"),
            source="google",
        )
        if point is not None:
            points.append(point)

    return points, places


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def parse_document(name: str, data: bytes) -> tuple[list[Point], list[dict[str, Any]]]:
    """Parse one uploaded file.  Returns (points, named places)."""
    lowered = (name or "").lower()
    text = data.decode("utf-8", errors="replace").lstrip("\ufeff").strip()
    if not text:
        return [], []

    if lowered.endswith(".gpx") or text.startswith("<?xml") or text.startswith("<gpx"):
        return parse_gpx(text), []

    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        # Large Takeout files can contain concatenated JSON objects.
        _LOGGER.debug("JSON in %s niet in één keer te lezen", name)
        return [], []

    if isinstance(document, dict) and document.get("type") in (
        "FeatureCollection",
        "Feature",
    ):
        return parse_geojson(document), []

    if isinstance(document, dict) and document.get("type") in (
        "Point",
        "LineString",
        "MultiLineString",
    ):
        return parse_geojson({"type": "Feature", "geometry": document}), []

    return parse_google(document)


def _zip_members(data: bytes) -> list[tuple[str, bytes]]:
    members: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                name = info.filename
                lowered = name.lower()
                if info.is_dir() or lowered.rsplit("/", 1)[-1] in SKIP_NAMES:
                    continue
                if not lowered.endswith((".json", ".gpx", ".geojson")):
                    continue
                members.append((name, archive.read(info)))
    except zipfile.BadZipFile:
        return []
    return members


def parse_upload(
    name: str, data: bytes
) -> tuple[list[Point], list[dict[str, Any]], int]:
    """Parse a single file or a ZIP with multiple exports.

    Returns the points, named places and the number of files that were read.
    """
    members = _zip_members(data) if data[:2] == b"PK" else [(name, data)]
    if not members:
        members = [(name, data)]

    points: list[Point] = []
    places: list[dict[str, Any]] = []
    files = 0
    for member_name, payload in members:
        try:
            found, named = parse_document(member_name, payload)
        except Exception as err:  # noqa: BLE001 - one bad file must not stop the rest
            _LOGGER.warning("Bestand %s overslaan: %s", member_name, err)
            continue
        files += 1
        points.extend(found)
        places.extend(named)
        if len(points) > MAX_POINTS_PER_FILE:
            _LOGGER.warning("Import afgekapt op %s punten", MAX_POINTS_PER_FILE)
            break
    return points, places, files
