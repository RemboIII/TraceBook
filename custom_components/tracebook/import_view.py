"""Upload endpoint for importing historical location data.

Accepts GPX, GeoJSON and Google Timeline exports (single file or a ZIP with
several files) and stores the points in the local archive.  Importing is
authorized exactly like exporting: the owner or administrator for their own
tracker, administrators only for family timelines.

Home Assistant's HTTP server caps a single request at 16 MB, while a full
Google Takeout archive is often much larger.  The card therefore uploads big
files in chunks; every chunk is appended to a temporary file and the last one
triggers the actual import.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .importers import parse_upload

_LOGGER = logging.getLogger(__name__)

#: A full Google Takeout archive with years of raw points is large; this is a
#: guard against accidental uploads of unrelated files.
MAX_UPLOAD_BYTES = 512 * 1024 * 1024

UPLOAD_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def _append_chunk(path: Path, data: bytes, truncate: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb" if truncate else "ab") as handle:
        handle.write(data)


def _read_and_remove(path: Path) -> bytes:
    try:
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


class TraceBookImportView(HomeAssistantView):
    url = "/api/tracebook/import/{entity_id}"
    name = "api:tracebook:import"
    requires_auth = True

    async def post(self, request: web.Request, entity_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        if not self._allowed(hass, request, entity_id):
            return web.json_response({"error": "Geen toegang"}, status=403)

        data = (hass.data.get(DOMAIN) or {})
        archive = data.get("archive")
        entry = (data.get("trackers") or {}).get(entity_id)
        if archive is None:
            return web.json_response({"error": "Archief staat uit"}, status=503)
        if entry is None:
            return web.json_response(
                {"error": "Onbekende tracker"}, status=404
            )

        name = request.query.get("name") or "upload"
        upload_id = request.query.get("upload_id")
        total_size = request.query.get("size")

        if total_size is not None:
            try:
                if int(total_size) > MAX_UPLOAD_BYTES:
                    return web.json_response(
                        {"error": "Bestand is groter dan 512 MB"}, status=413
                    )
            except ValueError:
                return web.json_response(
                    {"error": "Ongeldige bestandsgrootte"}, status=400
                )

        if upload_id:
            return await self._post_chunk(
                hass, request, archive, entry, name, upload_id
            )

        payload = await request.read()
        if not payload:
            return web.json_response({"error": "Leeg bestand"}, status=400)
        if len(payload) > MAX_UPLOAD_BYTES:
            return web.json_response(
                {"error": "Bestand is groter dan 512 MB"}, status=413
            )
        return await self._import(hass, archive, entry, name, payload)

    async def _post_chunk(
        self,
        hass: HomeAssistant,
        request: web.Request,
        archive,
        entry: dict,
        name: str,
        upload_id: str,
    ) -> web.Response:
        if not UPLOAD_ID_RE.match(upload_id):
            return web.json_response(
                {"error": "Ongeldige upload-id"}, status=400
            )
        try:
            index = int(request.query.get("chunk", "0"))
            count = int(request.query.get("chunks", "1"))
        except ValueError:
            return web.json_response(
                {"error": "Ongeldige chunkparameters"}, status=400
            )
        if index < 0 or count < 1 or index >= count:
            return web.json_response(
                {"error": "Ongeldige chunkparameters"}, status=400
            )

        chunk = await request.read()
        folder = Path(hass.config.path("HA_timeline", "imports"))
        path = folder / f"{upload_id}.part"
        await hass.async_add_executor_job(
            _append_chunk, path, chunk, index == 0
        )

        if index + 1 < count:
            return web.json_response(
                {"received": index + 1, "chunks": count}, status=200
            )

        payload = await hass.async_add_executor_job(_read_and_remove, path)
        if not payload:
            return web.json_response({"error": "Leeg bestand"}, status=400)
        if len(payload) > MAX_UPLOAD_BYTES:
            return web.json_response(
                {"error": "Bestand is groter dan 512 MB"}, status=413
            )
        return await self._import(hass, archive, entry, name, payload)

    async def _import(
        self,
        hass: HomeAssistant,
        archive,
        entry: dict,
        name: str,
        payload: bytes,
    ) -> web.Response:
        points, places, files = await hass.async_add_executor_job(
            parse_upload, name, payload
        )
        if not points:
            return web.json_response(
                {
                    "error": (
                        "Geen locatiepunten gevonden. Ondersteund: GPX, "
                        "GeoJSON en Google Timeline-export (JSON of ZIP)."
                    )
                },
                status=400,
            )

        person = entry["id"]
        rows = [
            {
                "person": person,
                "entity_id": entry["entity_id"],
                "ts": point["ts"],
                "lat": point["lat"],
                "lon": point["lon"],
                "accuracy": point.get("accuracy"),
                "speed": point.get("speed"),
                "altitude": point.get("altitude"),
                "battery": None,
                "source": point.get("source") or "import",
            }
            for point in points
        ]
        inserted = await archive.async_add_points(rows)

        imported_places = 0
        if places:
            index_rows = []
            for place in places:
                index_rows.append(
                    {
                        "id": (
                            "import:"
                            f"{str(place['name']).lower()}:"
                            f"{place['lat']:.5f}:{place['lon']:.5f}"
                        ),
                        "name": place["name"],
                        "lat": place["lat"],
                        "lon": place["lon"],
                        "address": place.get("address"),
                        "source": "import",
                    }
                )
            try:
                imported_places = await archive.async_upsert_place_index(
                    index_rows
                )
            except Exception as err:  # noqa: BLE001 - points matter most
                _LOGGER.warning("Plekken uit import opslaan mislukt: %s", err)

        tz = ZoneInfo(hass.config.time_zone)
        first = min(point["ts"] for point in points)
        last = max(point["ts"] for point in points)
        first_day = datetime.fromtimestamp(first, tz).date().isoformat()
        last_day = datetime.fromtimestamp(last, tz).date().isoformat()
        snapshots = await archive.async_drop_snapshots(
            entry["entity_id"], first_day, last_day
        )

        _LOGGER.info(
            "Import %s: %s punten (%s bestanden, %s plekken), dagen %s..%s",
            name,
            inserted,
            files,
            imported_places,
            first_day,
            last_day,
        )
        return web.json_response(
            {
                "imported": inserted,
                "parsed": len(points),
                "files": files,
                "places": imported_places,
                "snapshots_dropped": snapshots,
                "first_day": first_day,
                "last_day": last_day,
            }
        )

    def _allowed(
        self, hass: HomeAssistant, request: web.Request, entity_id: str
    ) -> bool:
        user = request.get("hass_user")
        if user is None:
            return False
        data = hass.data.get(DOMAIN) or {}
        if entity_id in (data.get("family") or {}):
            return bool(getattr(user, "is_admin", False))
        allowed = data.get("allowed_user_ids") or set()
        if not allowed:
            return True
        return user.id in allowed


def async_cleanup_uploads(hass: HomeAssistant) -> None:
    """Remove half-finished uploads from a previous run."""

    def _cleanup() -> None:
        folder = Path(hass.config.path("HA_timeline", "imports"))
        if not folder.is_dir():
            return
        for path in folder.glob("*.part"):
            try:
                path.unlink()
            except OSError:
                pass

    hass.async_add_executor_job(_cleanup)
