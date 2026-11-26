"""Upload the phone's address book (.vcf) directly from the dashboard.

Android and iOS cannot expose the contact list to a web page, but they can
export it as a vCard file.  Copying that file to the HA host is awkward on a
phone, so the card can POST the file contents here.  The view writes the file
to the configured path and imports/geocodes it immediately.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .archive import Archive
from .contacts import async_geocode_pending, async_load_contacts
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

MAX_CONTACTS_BYTES = 20 * 1024 * 1024


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


class ContactsImportView(HomeAssistantView):
    url = "/api/tracebook/contacts"
    name = "api:tracebook:contacts"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        user = request.get("hass_user")
        data = hass.data.get(DOMAIN) or {}

        allowed = data.get("allowed_user_ids") or set()
        if allowed and (
            user is None
            or (user.id not in allowed and not getattr(user, "is_admin", False))
        ):
            return web.Response(status=403, text="Geen toegang")

        archive: Archive | None = data.get("archive")
        if archive is None:
            return web.Response(status=503, text="Archief staat uit")

        body = await request.read()
        if not body:
            return web.Response(status=400, text="Leeg bestand")
        if len(body) > MAX_CONTACTS_BYTES:
            return web.Response(status=413, text="Bestand is te groot")
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return web.Response(status=400, text="Bestand is geen tekst (UTF-8)")

        if "BEGIN:VCARD" not in text.upper():
            return web.Response(status=400, text="Dit is geen vCard-bestand")

        path = Path(
            data.get("contacts_file")
            or hass.config.path("HA_timeline", "contacts.vcf")
        )
        try:
            await hass.async_add_executor_job(_write_file, path, text)
        except OSError as err:
            _LOGGER.warning("Contacten opslaan mislukt: %s", err)
            return web.Response(status=500, text="Opslaan mislukt")

        try:
            addresses = await async_load_contacts(hass, archive, str(path))
            stat = path.stat()
            await archive.async_set_meta(
                "contacts_signature", f"{stat.st_mtime}:{stat.st_size}"
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Contacten importeren mislukt: %s", err)
            return web.Response(status=500, text="Importeren mislukt")

        home = None
        zone = hass.states.get("zone.home")
        if zone is not None:
            try:
                home = (
                    float(zone.attributes["latitude"]),
                    float(zone.attributes["longitude"]),
                )
            except (KeyError, TypeError, ValueError):
                home = None
        hass.async_create_background_task(
            async_geocode_pending(hass, archive, home),
            "tracebook_contacts_geocode",
        )

        _LOGGER.info("Contacten: %s adressen geïmporteerd via dashboard", addresses)
        return web.json_response(
            {
                "ok": True,
                "addresses": addresses,
                "path": str(path),
            }
        )
