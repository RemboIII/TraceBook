"""Local SQLite archive for location points, visits and journey edits.

Home Assistant's recorder keeps only a limited retention window.  This module
keeps *every* location report from the configured trackers in a small,
self-contained SQLite file, independent of the recorder retention.

The archive is deliberately compact: one row per GPS report with the fields we
actually use.  That keeps a family of three well under a gigabyte per year.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
import sqlite3
import time
import unicodedata
from datetime import date, datetime, time as dt_time, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

SCHEMA_VERSION = 2

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS points (
    id INTEGER PRIMARY KEY,
    person TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    ts REAL NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    accuracy REAL,
    speed REAL,
    altitude REAL,
    battery REAL,
    source TEXT NOT NULL DEFAULT 'live'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_points_unique ON points(entity_id, ts);
CREATE INDEX IF NOT EXISTS idx_points_entity_ts ON points(entity_id, ts);
CREATE INDEX IF NOT EXISTS idx_points_entity_lat ON points(entity_id, lat, lon);

CREATE TABLE IF NOT EXISTS places (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    radius REAL NOT NULL DEFAULT 75,
    osm_type TEXT,
    osm_id TEXT,
    address TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_places_name ON places(name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS day_snapshots (
    entity_id TEXT NOT NULL,
    day TEXT NOT NULL,
    payload TEXT NOT NULL,
    locked INTEGER NOT NULL DEFAULT 1,
    updated_at REAL NOT NULL,
    PRIMARY KEY (entity_id, day)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
    address_key TEXT PRIMARY KEY,
    address TEXT,
    street TEXT,
    city TEXT,
    postcode TEXT,
    country TEXT,
    names TEXT,
    display TEXT,
    lat REAL,
    lon REAL,
    geocoded_at REAL
);
CREATE INDEX IF NOT EXISTS idx_contacts_lat ON contacts(lat, lon);

CREATE TABLE IF NOT EXISTS place_index (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_norm TEXT,
    lat REAL,
    lon REAL,
    address TEXT,
    source TEXT,
    updated_at REAL
);
CREATE INDEX IF NOT EXISTS idx_place_index_name ON place_index(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_place_index_lat_lon ON place_index(lat, lon);
"""

#: Letters that do not decompose into an ASCII base letter.  Search should
#: find "Schafer" for "Schäfer", "Strasser" for "Straßer", etc.
_TRANSLITERATIONS = {
    "ß": "ss",
    "æ": "ae",
    "œ": "oe",
    "ø": "o",
    "ł": "l",
    "đ": "d",
    "ð": "d",
    "þ": "th",
    "ı": "i",
    "ĳ": "ij",
    "ħ": "h",
    "ŧ": "t",
    "ŋ": "n",
}


def normalize_search_text(value: Any) -> str:
    """Normalise text for case-, accent- and ligature-insensitive search."""
    text = str(value or "")
    for source, target in _TRANSLITERATIONS.items():
        text = text.replace(source, target)
        text = text.replace(source.upper(), target.upper())
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = re.sub(r"[^0-9a-z]+", " ", text)
    return " ".join(text.split())


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Haversine distance in metres."""
    radius = 6371000.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(
        dlon / 2
    ) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def stable_key(prefix: str, *parts: Any) -> str:
    """Build a short, deterministic key from the content of an entry."""
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


class Archive:
    """Read/write wrapper around the local SQLite archive."""

    def __init__(self, hass: HomeAssistant, path: str | None = None) -> None:
        self._hass = hass
        self._path = Path(path or hass.config.path("HA_timeline", "archive.db"))
        self._lock = asyncio.Lock()
        self._ready = False

    @property
    def path(self) -> Path:
        return self._path

    # ------------------------------------------------------------------
    # Low level helpers
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    async def async_init(self) -> None:
        if self._ready:
            return
        await self._hass.async_add_executor_job(self._init_sync)
        self._ready = True

    def _init_sync(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(place_index)")
            }
            if "name_norm" not in columns:
                connection.execute(
                    "ALTER TABLE place_index ADD COLUMN name_norm TEXT"
                )
            # Fill the normalised name once for the existing index.  Without
            # it, "schafer" would not match "Schäfer" because SQLite's NOCASE
            # only folds ASCII case.
            missing = connection.execute(
                "SELECT id, name FROM place_index WHERE name_norm IS NULL"
            ).fetchall()
            if missing:
                connection.executemany(
                    "UPDATE place_index SET name_norm = ? WHERE id = ?",
                    [
                        (normalize_search_text(row["name"]), row["id"])
                        for row in missing
                    ],
                )
                _LOGGER.info(
                    "Plaatsindex: %s namen genormaliseerd voor zoeken",
                    len(missing),
                )
            row = connection.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )
            else:
                connection.execute(
                    "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                    (str(SCHEMA_VERSION),),
                )
            connection.commit()

    async def _run(self, function, *args):
        return await self._hass.async_add_executor_job(function, *args)

    # ------------------------------------------------------------------
    # Points
    # ------------------------------------------------------------------
    async def async_add_points(self, points: Iterable[dict[str, Any]]) -> int:
        rows = list(points)
        if not rows:
            return 0
        async with self._lock:
            return await self._run(self._add_points_sync, rows)

    def _add_points_sync(self, rows: list[dict[str, Any]]) -> int:
        inserted = 0
        with self._connect() as connection:
            for row in rows:
                try:
                    cursor = connection.execute(
                        """
                        INSERT OR IGNORE INTO points
                            (person, entity_id, ts, lat, lon, accuracy, speed,
                             altitude, battery, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["person"],
                            row["entity_id"],
                            float(row["ts"]),
                            float(row["lat"]),
                            float(row["lon"]),
                            row.get("accuracy"),
                            row.get("speed"),
                            row.get("altitude"),
                            row.get("battery"),
                            row.get("source", "live"),
                        ),
                    )
                    inserted += cursor.rowcount
                except (KeyError, TypeError, ValueError) as err:
                    _LOGGER.debug("Ongeldig locatiepunt overgeslagen: %s", err)
            connection.commit()
        return inserted

    async def async_points(
        self, entity_id: str, start_ts: float, end_ts: float
    ) -> list[dict[str, Any]]:
        return await self._run(self._points_sync, entity_id, start_ts, end_ts)

    def _points_sync(
        self, entity_id: str, start_ts: float, end_ts: float
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT ts, lat, lon, accuracy, speed, altitude, battery
                FROM points
                WHERE entity_id = ? AND ts >= ? AND ts <= ?
                ORDER BY ts
                """,
                (entity_id, start_ts, end_ts),
            )
            return [dict(row) for row in cursor.fetchall()]

    async def async_last_point(self, entity_id: str) -> dict[str, Any] | None:
        return await self._run(self._last_point_sync, entity_id)

    def _last_point_sync(self, entity_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT ts, lat, lon FROM points WHERE entity_id = ? "
                "ORDER BY ts DESC LIMIT 1",
                (entity_id,),
            ).fetchone()
            return dict(row) if row else None

    async def async_first_point(self, entity_id: str) -> dict[str, Any] | None:
        return await self._run(self._first_point_sync, entity_id)

    def _first_point_sync(self, entity_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT ts, lat, lon FROM points WHERE entity_id = ? "
                "ORDER BY ts ASC LIMIT 1",
                (entity_id,),
            ).fetchone()
            return dict(row) if row else None

    async def async_days(
        self, entity_id: str, start_ts: float, end_ts: float
    ) -> dict[str, int]:
        """Return the number of points per local day in a range."""
        return await self._run(
            self._days_sync,
            entity_id,
            start_ts,
            end_ts,
            str(ZoneInfo(self._hass.config.time_zone)),
        )

    def _days_sync(
        self, entity_id: str, start_ts: float, end_ts: float, timezone: str
    ) -> dict[str, int]:
        tz = ZoneInfo(timezone)
        result: dict[str, int] = {}
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT ts FROM points WHERE entity_id = ? AND ts >= ? AND ts <= ?",
                (entity_id, start_ts, end_ts),
            )
            for row in cursor.fetchall():
                day = datetime.fromtimestamp(row["ts"], tz).date().isoformat()
                result[day] = result.get(day, 0) + 1
        return result

    async def async_point_count(self, entity_id: str | None = None) -> int:
        return await self._run(self._point_count_sync, entity_id)

    def _point_count_sync(self, entity_id: str | None) -> int:
        with self._connect() as connection:
            if entity_id:
                row = connection.execute(
                    "SELECT COUNT(*) AS n FROM points WHERE entity_id = ?",
                    (entity_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT COUNT(*) AS n FROM points"
                ).fetchone()
            return int(row["n"] if row else 0)

    # ------------------------------------------------------------------
    # Day snapshots (locked days with user edits)
    # ------------------------------------------------------------------
    async def async_snapshot(
        self, entity_id: str, day: str
    ) -> dict[str, Any] | None:
        return await self._run(self._snapshot_sync, entity_id, day)

    def _snapshot_sync(
        self, entity_id: str, day: str
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload, locked FROM day_snapshots "
                "WHERE entity_id = ? AND day = ?",
                (entity_id, day),
            ).fetchone()
            if row is None:
                return None
            return {
                "payload": json.loads(row["payload"]),
                "locked": bool(row["locked"]),
            }

    async def async_save_snapshot(
        self, entity_id: str, day: str, payload: dict[str, Any], locked: bool = True
    ) -> None:
        async with self._lock:
            await self._run(
                self._save_snapshot_sync, entity_id, day, payload, locked
            )

    def _save_snapshot_sync(
        self,
        entity_id: str,
        day: str,
        payload: dict[str, Any],
        locked: bool,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO day_snapshots(entity_id, day, payload, locked, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entity_id, day) DO UPDATE SET
                    payload = excluded.payload,
                    locked = excluded.locked,
                    updated_at = excluded.updated_at
                """,
                (
                    entity_id,
                    day,
                    json.dumps(payload, ensure_ascii=False),
                    1 if locked else 0,
                    time.time(),
                ),
            )
            connection.commit()

    async def async_delete_snapshot(self, entity_id: str, day: str) -> None:
        async with self._lock:
            await self._run(self._delete_snapshot_sync, entity_id, day)

    def _delete_snapshot_sync(self, entity_id: str, day: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM day_snapshots WHERE entity_id = ? AND day = ?",
                (entity_id, day),
            )
            connection.commit()

    async def async_drop_snapshots(
        self, entity_id: str, first_day: str, last_day: str
    ) -> int:
        """Rebuild days after an import, but keep manual user edits."""
        async with self._lock:
            return await self._run(
                self._drop_snapshots_sync, entity_id, first_day, last_day
            )

    def _drop_snapshots_sync(
        self, entity_id: str, first_day: str, last_day: str
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                DELETE FROM day_snapshots
                WHERE entity_id = ? AND day BETWEEN ? AND ?
                  AND payload NOT LIKE '%"user_edited"%'
                  AND payload NOT LIKE '%"user_merged"%'
                  AND payload NOT LIKE '%"deleted_keys"%'
                """,
                (entity_id, first_day, last_day),
            )
            connection.commit()
            return cursor.rowcount

    # ------------------------------------------------------------------
    # Places
    # ------------------------------------------------------------------
    async def async_places(
        self, query: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        return await self._run(self._places_sync, query, limit)

    def _places_sync(
        self, query: str | None, limit: int
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if query:
                cursor = connection.execute(
                    "SELECT * FROM places WHERE name LIKE ? "
                    "ORDER BY name COLLATE NOCASE LIMIT ?",
                    (f"%{query}%", limit),
                )
            else:
                cursor = connection.execute(
                    "SELECT * FROM places ORDER BY name COLLATE NOCASE LIMIT ?",
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]

    async def async_upsert_place(self, place: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            return await self._run(self._upsert_place_sync, place)

    def _upsert_place_sync(self, place: dict[str, Any]) -> dict[str, Any]:
        name = str(place.get("name") or "").strip()
        if not name:
            raise ValueError("Plaatsnaam ontbreekt")
        lat = float(place["lat"])
        lon = float(place["lon"])
        radius = float(place.get("radius") or 75)
        place_id = place.get("id") or stable_key(
            "place-", name.lower(), f"{lat:.5f}", f"{lon:.5f}"
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO places(id, name, lat, lon, radius, osm_type, osm_id,
                                   address, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    lat = excluded.lat,
                    lon = excluded.lon,
                    radius = excluded.radius,
                    address = excluded.address
                """,
                (
                    place_id,
                    name,
                    lat,
                    lon,
                    radius,
                    place.get("osm_type"),
                    place.get("osm_id"),
                    place.get("address"),
                    time.time(),
                ),
            )
            connection.commit()
        return {
            "id": place_id,
            "name": name,
            "lat": lat,
            "lon": lon,
            "radius": radius,
            "address": place.get("address"),
        }

    # ------------------------------------------------------------------
    # Local place index (visited, saved and imported places)
    # ------------------------------------------------------------------
    async def async_upsert_place_index(
        self, places: Iterable[dict[str, Any]]
    ) -> int:
        rows = list(places)
        if not rows:
            return 0
        async with self._lock:
            return await self._run(self._upsert_place_index_sync, rows)

    def _upsert_place_index_sync(self, rows: list[dict[str, Any]]) -> int:
        changed = 0
        with self._connect() as connection:
            for row in rows:
                name = str(row.get("name") or "").strip()
                if not name:
                    continue
                latitude = row.get("lat")
                longitude = row.get("lon")
                if latitude is None or longitude is None:
                    continue
                identifier = row.get("id") or stable_key(
                    "place-",
                    row.get("source") or "visit",
                    name.lower(),
                    f"{float(latitude):.5f}",
                    f"{float(longitude):.5f}",
                )
                cursor = connection.execute(
                    """
                    INSERT INTO place_index(id, name, name_norm, lat, lon,
                                            address, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        name_norm = excluded.name_norm,
                        lat = excluded.lat,
                        lon = excluded.lon,
                        address = excluded.address,
                        source = excluded.source,
                        updated_at = excluded.updated_at
                    """,
                    (
                        identifier,
                        name,
                        normalize_search_text(name),
                        float(latitude),
                        float(longitude),
                        row.get("address"),
                        row.get("source") or "visit",
                        time.time(),
                    ),
                )
                changed += cursor.rowcount
            connection.commit()
        return changed

    async def async_search_place_index(
        self,
        query: str,
        lat: float | None = None,
        lon: float | None = None,
        limit: int = 12,
        max_distance_m: float | None = None,
    ) -> list[dict[str, Any]]:
        return await self._run(
            self._search_place_index_sync,
            query,
            lat,
            lon,
            limit,
            max_distance_m,
        )

    def _search_place_index_sync(
        self,
        query: str,
        lat: float | None,
        lon: float | None,
        limit: int,
        max_distance_m: float | None = None,
    ) -> list[dict[str, Any]]:
        normalised = normalize_search_text(query)
        if not normalised:
            return []
        words = normalised.split()
        if not words:
            return []

        # Only fetch a candidate set: the first four characters of every word
        # is enough to catch prefixes and small typos, and keeps the index
        # fast even with hundreds of thousands of OSM places.  The normalised
        # column makes this work for accents and ligatures as well.
        needles = [
            word if len(word) <= 4 else word[:4] for word in words
        ]
        params = [f"%{needle}%" for needle in needles]

        def fetch(operator: str, limit: int) -> list[sqlite3.Row]:
            where = f" {operator} ".join(
                "name_norm LIKE ?" for _ in needles
            )
            with self._connect() as connection:
                return connection.execute(
                    "SELECT id, name, name_norm, lat, lon, address, source "
                    f"FROM place_index WHERE {where} LIMIT {limit}",
                    params,
                ).fetchall()

        def score_rows(
            rows: list[sqlite3.Row],
        ) -> list[tuple[float, float, dict[str, Any]]]:
            scored: list[tuple[float, float, dict[str, Any]]] = []
            for row in rows:
                name = str(row["name"] or "")
                name_norm = str(row["name_norm"] or "")
                name_words = name_norm.split()
                score = 0.0
                if name_norm == normalised:
                    score = 120.0
                elif name_norm.startswith(normalised):
                    score = 110.0
                elif all(
                    any(word.startswith(part) for word in name_words)
                    for part in words
                ):
                    score = 95.0
                elif normalised in name_norm:
                    score = 85.0
                else:
                    # Per-word fuzzy matching: "schafer notarissen" should
                    # still find "Schäfer" even though the second word is
                    # not part of the OSM name.
                    ratios = [
                        max(
                            (
                                SequenceMatcher(None, part, word).ratio()
                                for word in name_words
                            ),
                            default=0.0,
                        )
                        for part in words
                    ]
                    matched = sum(1 for ratio in ratios if ratio >= 0.8)
                    if matched == len(words):
                        score = 50.0 + (sum(ratios) / len(ratios)) * 30.0
                    elif matched and matched / len(words) >= 0.5:
                        score = 40.0 + max(ratios) * 25.0
                if score <= 0:
                    continue
                distance = None
                if (
                    lat is not None
                    and lon is not None
                    and row["lat"] is not None
                    and row["lon"] is not None
                ):
                    distance = _distance_m(
                        (lat, lon), (float(row["lat"]), float(row["lon"]))
                    )
                    if (
                        max_distance_m is not None
                        and distance > max_distance_m
                    ):
                        continue
                elif max_distance_m is not None:
                    continue
                scored.append(
                    (
                        -score,
                        distance if distance is not None else 1e12,
                        {
                            "id": row["id"],
                            "name": name,
                            "lat": float(row["lat"]),
                            "lon": float(row["lon"]),
                            "address": row["address"],
                            "source": row["source"],
                            "distance": round(distance)
                            if distance is not None
                            else None,
                        },
                    )
                )
            scored.sort(key=lambda item: (item[0], item[1]))
            return scored

        scored = score_rows(fetch("AND", 4000))
        if not scored and len(needles) > 1:
            # Every word was required above; retry with any word so an extra
            # word that is not part of the name ("notarissen") does not hide
            # the actual place.
            scored = score_rows(fetch("OR", 6000))
        return [item[2] for item in scored[:limit]]

    async def async_place_index_near(
        self,
        lat: float,
        lon: float,
        radius_m: float = 75.0,
        limit: int = 80,
    ) -> list[dict[str, Any]]:
        """Named places from the index within ``radius_m`` of a point."""
        return await self._run(
            self._place_index_near_sync, lat, lon, radius_m, limit
        )

    def _place_index_near_sync(
        self,
        lat: float,
        lon: float,
        radius_m: float,
        limit: int,
    ) -> list[dict[str, Any]]:
        lat_delta = radius_m / 111_320.0
        lon_delta = radius_m / (
            111_320.0 * max(0.05, math.cos(math.radians(lat)))
        )
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, lat, lon, address, source
                FROM place_index
                WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
                """,
                (
                    lat - lat_delta,
                    lat + lat_delta,
                    lon - lon_delta,
                    lon + lon_delta,
                ),
            ).fetchall()

        found: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            if row["lat"] is None or row["lon"] is None:
                continue
            distance = _distance_m(
                (lat, lon), (float(row["lat"]), float(row["lon"]))
            )
            if distance > radius_m:
                continue
            found.append(
                (
                    distance,
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"]),
                        "address": row["address"],
                        "source": row["source"],
                        "distance": round(distance),
                    },
                )
            )
        found.sort(key=lambda item: (item[0], str(item[1].get("name") or "")))
        return [item[1] for item in found[:limit]]

    async def async_place_index_count(self) -> int:
        return await self._run(self._place_index_count_sync)

    def _place_index_count_sync(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM place_index"
            ).fetchone()
            return int(row["n"] if row else 0)

    async def async_poi_cells(self, limit: int = 2000) -> list[dict[str, Any]]:
        """Distinct ~5 km cells from all archived points, newest first."""
        return await self._run(self._poi_cells_sync, limit)

    def _poi_cells_sync(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT CAST(ROUND(lat * 20) AS INTEGER) AS la,
                       CAST(ROUND(lon * 20) AS INTEGER) AS lo,
                       COUNT(*) AS n,
                       MAX(ts) AS last
                FROM points
                GROUP BY la, lo
                HAVING n >= 2
                ORDER BY last DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "lat": row["la"] / 20.0,
                "lon": row["lo"] / 20.0,
                "points": int(row["n"]),
                "last": float(row["last"]),
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Contacts (from the phone's address book, via vCard)
    # ------------------------------------------------------------------
    async def async_upsert_contacts(
        self, contacts: Iterable[dict[str, Any]]
    ) -> int:
        rows = list(contacts)
        if not rows:
            return 0
        async with self._lock:
            return await self._run(self._upsert_contacts_sync, rows)

    def _upsert_contacts_sync(self, rows: list[dict[str, Any]]) -> int:
        changed = 0
        with self._connect() as connection:
            for row in rows:
                key = row.get("address_key")
                if not key:
                    continue
                cursor = connection.execute(
                    """
                    INSERT INTO contacts(address_key, address, street, city,
                                         postcode, country, names, display)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(address_key) DO UPDATE SET
                        names = excluded.names,
                        display = excluded.display,
                        lat = CASE
                            WHEN contacts.address = excluded.address
                            THEN contacts.lat ELSE NULL END,
                        lon = CASE
                            WHEN contacts.address = excluded.address
                            THEN contacts.lon ELSE NULL END,
                        geocoded_at = CASE
                            WHEN contacts.address = excluded.address
                            THEN contacts.geocoded_at ELSE NULL END,
                        address = excluded.address,
                        street = excluded.street,
                        city = excluded.city,
                        postcode = excluded.postcode,
                        country = excluded.country
                    """,
                    (
                        key,
                        row.get("address"),
                        row.get("street"),
                        row.get("city"),
                        row.get("postcode"),
                        row.get("country"),
                        json.dumps(row.get("names") or [], ensure_ascii=False),
                        row.get("display"),
                    ),
                )
                changed += cursor.rowcount
            connection.commit()
        return changed

    async def async_pending_contacts(
        self, limit: int = 50
    ) -> list[dict[str, Any]]:
        return await self._run(self._pending_contacts_sync, limit)

    def _pending_contacts_sync(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            cursor = connection.execute(
                "SELECT * FROM contacts "
                "WHERE lat IS NULL OR lon IS NULL "
                "ORDER BY address_key LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    async def async_set_contact_location(
        self, address_key: str, lat: float, lon: float
    ) -> None:
        async with self._lock:
            await self._run(
                self._set_contact_location_sync, address_key, lat, lon
            )

    def _set_contact_location_sync(
        self, address_key: str, lat: float, lon: float
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE contacts SET lat = ?, lon = ?, geocoded_at = ? "
                "WHERE address_key = ?",
                (lat, lon, time.time(), address_key),
            )
            connection.commit()

    async def async_contacts_near(
        self, lat: float, lon: float, radius: float = 150
    ) -> list[dict[str, Any]]:
        return await self._run(
            self._contacts_near_sync, lat, lon, radius
        )

    def _contacts_near_sync(
        self, lat: float, lon: float, radius: float
    ) -> list[dict[str, Any]]:
        lat_delta = radius / 111320.0
        lon_delta = radius / (
            111320.0 * max(0.2, math.cos(math.radians(lat)))
        )
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT * FROM contacts
                WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
                """,
                (
                    lat - lat_delta,
                    lat + lat_delta,
                    lon - lon_delta,
                    lon + lon_delta,
                ),
            )
            rows = cursor.fetchall()

        groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            distance = _distance_m(
                (lat, lon), (float(row["lat"]), float(row["lon"]))
            )
            if distance > radius:
                continue
            key = row["address_key"]
            names = json.loads(row["names"] or "[]")
            group = groups.get(key)
            if group is None:
                group = {
                    "id": key,
                    "name": "",
                    "address": row["address"],
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "distance": round(distance),
                    "names": [],
                }
                groups[key] = group
            for name in names:
                if name not in group["names"]:
                    group["names"].append(name)
        result = []
        for group in groups.values():
            group["name"] = " & ".join(group["names"]) or group["address"]
            result.append(group)
        result.sort(key=lambda item: item["distance"])
        return result

    async def async_contact_count(self) -> int:
        return await self._run(self._contact_count_sync)

    def _contact_count_sync(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM contacts"
            ).fetchone()
            return int(row["n"] if row else 0)

    async def async_prune_contacts(self, keep_keys: Iterable[str]) -> int:
        keys = list(keep_keys)
        if not keys:
            # A failed/empty export should never wipe the address book.
            return 0
        async with self._lock:
            return await self._run(self._prune_contacts_sync, keys)

    def _prune_contacts_sync(self, keys: list[str]) -> int:
        with self._connect() as connection:
            placeholders = ",".join("?" for _ in keys)
            cursor = connection.execute(
                f"DELETE FROM contacts WHERE address_key NOT IN ({placeholders})",
                keys,
            )
            connection.commit()
            return int(cursor.rowcount or 0)

    # ------------------------------------------------------------------
    # POI visit lookup
    # ------------------------------------------------------------------
    async def async_visits_near(
        self,
        entity_id: str,
        lat: float,
        lon: float,
        radius: float = 75,
        min_minutes: float = 5,
        max_visits: int = 2000,
    ) -> list[dict[str, Any]]:
        return await self._run(
            self._visits_near_sync,
            entity_id,
            lat,
            lon,
            radius,
            min_minutes,
            max_visits,
        )

    def _visits_near_sync(
        self,
        entity_id: str,
        lat: float,
        lon: float,
        radius: float,
        min_minutes: float,
        max_visits: int,
    ) -> list[dict[str, Any]]:
        """Group points around a POI into stays.

        A stay is a run of points within ``radius`` of the POI, allowing gaps
        of up to 30 minutes (the same order of magnitude as the phone's
        reporting interval).  This does not need the day derivation and is
        therefore fast enough for years of history.
        """
        lat_delta = radius / 111320.0
        lon_delta = radius / (
            111320.0 * max(0.2, math.cos(math.radians(lat)))
        )

        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT ts, lat, lon FROM points
                WHERE entity_id = ?
                  AND lat BETWEEN ? AND ?
                  AND lon BETWEEN ? AND ?
                ORDER BY ts
                """,
                (
                    entity_id,
                    lat - lat_delta,
                    lat + lat_delta,
                    lon - lon_delta,
                    lon + lon_delta,
                ),
            )
            rows = cursor.fetchall()

        visits: list[dict[str, Any]] = []
        current: list[sqlite3.Row] = []

        def flush() -> None:
            if not current:
                return
            start = current[0]["ts"]
            end = current[-1]["ts"]
            if end - start < min_minutes * 60:
                return
            visits.append(
                {
                    "start": datetime.fromtimestamp(start).isoformat(),
                    "end": datetime.fromtimestamp(end).isoformat(),
                    "start_ts": start,
                    "end_ts": end,
                    "minutes": int((end - start) / 60),
                    "points": len(current),
                    "lat": sum(row["lat"] for row in current) / len(current),
                    "lon": sum(row["lon"] for row in current) / len(current),
                }
            )

        for row in rows:
            if _distance_m((lat, lon), (row["lat"], row["lon"])) > radius:
                continue
            if current and row["ts"] - current[-1]["ts"] > 30 * 60:
                flush()
                current = []
            current.append(row)
        flush()

        visits.sort(key=lambda item: item["start_ts"], reverse=True)
        return visits[:max_visits]

    # ------------------------------------------------------------------
    # Meta
    # ------------------------------------------------------------------
    async def async_meta(self, key: str) -> str | None:
        return await self._run(self._meta_get_sync, key)

    def _meta_get_sync(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM meta WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else None

    async def async_set_meta(self, key: str, value: str) -> None:
        async with self._lock:
            await self._run(self._meta_set_sync, key, value)

    def _meta_set_sync(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            connection.commit()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    async def async_export_rows(
        self, entity_id: str, start_ts: float, end_ts: float
    ) -> list[dict[str, Any]]:
        return await self._run(
            self._export_rows_sync, entity_id, start_ts, end_ts
        )

    def _export_rows_sync(
        self, entity_id: str, start_ts: float, end_ts: float
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                SELECT ts, lat, lon, accuracy, speed, altitude
                FROM points
                WHERE entity_id = ? AND ts >= ? AND ts <= ?
                ORDER BY ts
                """,
                (entity_id, start_ts, end_ts),
            )
            return [dict(row) for row in cursor.fetchall()]

    async def async_status(self) -> dict[str, Any]:
        return await self._run(self._status_sync)

    def _status_sync(self) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n, MIN(ts) AS first, MAX(ts) AS last FROM points"
            ).fetchone()
            per_entity = {
                item["entity_id"]: item["n"]
                for item in connection.execute(
                    "SELECT entity_id, COUNT(*) AS n FROM points GROUP BY entity_id"
                ).fetchall()
            }
            size = self._path.stat().st_size if self._path.exists() else 0
        return {
            "points": int(row["n"] or 0),
            "first": datetime.fromtimestamp(row["first"]).isoformat()
            if row["first"]
            else None,
            "last": datetime.fromtimestamp(row["last"]).isoformat()
            if row["last"]
            else None,
            "per_entity": per_entity,
            "bytes": size,
            "path": str(self._path),
        }


def day_range(day: date, tz: ZoneInfo) -> tuple[float, float]:
    """Unix timestamps for a local calendar day (inclusive start/end)."""
    start = datetime.combine(day, dt_time.min, tzinfo=tz)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return start.timestamp(), end.timestamp()
