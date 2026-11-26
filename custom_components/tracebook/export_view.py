"""Streaming GPX/GeoJSON export of the local archive.

A websocket message would have to hold the complete file in memory, which is
not workable for years of points.  This view streams the download instead, so
the archive can be exported in pieces per person and date range.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CHUNK = 2000


def _iso(ts: float) -> str:
    return (
        datetime.fromtimestamp(ts, timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class TimelineExportView(HomeAssistantView):
    url = "/api/tracebook/export/{entity_id}/{fmt}"
    name = "api:tracebook:export"
    requires_auth = True

    async def get(self, request: web.Request, entity_id: str, fmt: str) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        if fmt not in ("gpx", "geojson"):
            return web.Response(status=404, text="Onbekend formaat")
        if not self._allowed(hass, request, entity_id):
            return web.Response(status=403, text="Geen toegang")

        archive = (hass.data.get(DOMAIN) or {}).get("archive")
        if archive is None:
            return web.Response(status=503, text="Archief staat uit")

        tz = ZoneInfo(hass.config.time_zone)
        try:
            start = datetime.combine(
                date.fromisoformat(request.query["start"]), dt_time.min, tzinfo=tz
            )
            end = datetime.combine(
                date.fromisoformat(request.query["end"]), dt_time.min, tzinfo=tz
            ) + timedelta(days=1)
        except (KeyError, ValueError):
            return web.Response(status=400, text="Ongeldige periode")

        rows = await archive.async_export_rows(
            entity_id, start.timestamp(), end.timestamp()
        )
        if not rows:
            return web.Response(status=404, text="Geen punten in deze periode")

        entry = ((hass.data.get(DOMAIN) or {}).get("trackers") or {}).get(
            entity_id
        ) or {}
        name = str(entry.get("name") or entity_id)
        filename = f"{name}-{request.query['start']}-{request.query['end']}.{fmt}"

        response = web.StreamResponse(
            headers={
                "Content-Type": (
                    "application/gpx+xml; charset=utf-8"
                    if fmt == "gpx"
                    else "application/geo+json; charset=utf-8"
                ),
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            }
        )
        await response.prepare(request)

        try:
            if fmt == "gpx":
                await response.write(
                    (
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<gpx version="1.1" creator="TraceBook" '
                        'xmlns="http://www.topografix.com/GPX/1/1">\n'
                        f"<metadata><name>{name}</name></metadata>\n"
                        f"<trk><name>{name}</name><trkseg>\n"
                    ).encode("utf-8")
                )
                for row in rows:
                    await response.write(
                        (
                            f'<trkpt lat="{float(row["lat"]):.7f}" '
                            f'lon="{float(row["lon"]):.7f}">'
                            f"<time>{_iso(float(row['ts']))}</time></trkpt>\n"
                        ).encode("utf-8")
                    )
                await response.write(b"</trkseg></trk></gpx>\n")
            else:
                await response.write(
                    (
                        '{"type":"FeatureCollection","name":'
                        + json.dumps(name, ensure_ascii=False)
                        + ',"features":['
                    ).encode("utf-8")
                )
                first = True
                for index, row in enumerate(rows):
                    feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [
                                float(row["lon"]),
                                float(row["lat"]),
                            ],
                        },
                        "properties": {
                            "timestamp": _iso(float(row["ts"])),
                            "accuracy": row.get("accuracy"),
                            "speed": row.get("speed"),
                            "altitude": row.get("altitude"),
                        },
                    }
                    prefix = "" if first else ","
                    first = False
                    await response.write(
                        (prefix + json.dumps(feature, ensure_ascii=False)).encode(
                            "utf-8"
                        )
                    )
                    if index % CHUNK == 0:
                        await response.drain()
                await response.write(b"]}")
        except Exception as err:  # noqa: BLE001 - client may disconnect
            _LOGGER.debug("Export afgebroken: %s", err)

        await response.write_eof()
        return response

    def _allowed(self, hass: HomeAssistant, request: web.Request, entity_id: str) -> bool:
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
