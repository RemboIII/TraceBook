"""GeoPulse: a Google Timeline-style day view for Home Assistant.

Everything runs on a local SQLite archive with the location points of the
configured trackers.  No external location service is needed; only place-name
lookups (Photon/Overpass) and address geocoding use the internet.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.typing import ConfigType

from .archive import Archive
from .contacts import async_geocode_pending, async_load_contacts
from .const import (
    CONF_ALLOWED_USER_IDS,
    CONF_ARCHIVE,
    CONF_ARCHIVE_DATABASE,
    CONF_ARCHIVE_ENABLED,
    CONF_BACKFILL_DAYS,
    CONF_CONTACTS_FILE,
    CONF_FAMILY,
    CONF_GEOCODE,
    CONF_POI_SYNC,
    CONF_TRACKERS,
    DOMAIN,
)
from .contacts_view import ContactsImportView
from .export_view import TimelineExportView
from .import_view import GeoPulseImportView, async_cleanup_uploads
from .importer import backfill_recorder
from .poi_sync import NIGHTLY_TILES, async_sync_archive_tiles, async_sync_home
from .websocket import async_register_websocket_api
from .websocket_local import async_register_local_websocket_api

_LOGGER = logging.getLogger(__name__)

VERSION = "0.2.2"

STATIC_URL = "/geopulse_static"
CARD_URL = f"{STATIC_URL}/geopulse-card.js?v={VERSION}"

TRACKER_SCHEMA = vol.Schema(
    {
        vol.Required("id"): cv.slug,
        vol.Required("name"): cv.string,
        vol.Required("entity_id"): cv.entity_id,
    }
)

ARCHIVE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ARCHIVE_ENABLED, default=True): cv.boolean,
        vol.Optional(CONF_BACKFILL_DAYS, default=10): vol.All(
            int, vol.Range(min=0, max=365)
        ),
        vol.Optional(CONF_ARCHIVE_DATABASE): cv.string,
        vol.Optional(CONF_CONTACTS_FILE): cv.string,
        vol.Optional(CONF_POI_SYNC, default=True): cv.boolean,
        vol.Optional(CONF_TRACKERS, default=[]): vol.All(
            cv.ensure_list, [TRACKER_SCHEMA]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_ALLOWED_USER_IDS, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_GEOCODE, default=True): cv.boolean,
                vol.Optional(CONF_FAMILY, default=[]): vol.All(
                    cv.ensure_list,
                    [
                        vol.Schema(
                            {
                                vol.Required("id"): cv.slug,
                                vol.Required("name"): cv.string,
                                vol.Required("entity_id"): cv.entity_id,
                            }
                        )
                    ],
                ),
                vol.Optional(CONF_ARCHIVE, default={}): ARCHIVE_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _resolve_trackers(
    archive_conf: dict, family: dict[str, dict]
) -> dict[str, dict]:
    configured = list(archive_conf.get(CONF_TRACKERS) or [])

    existing = {item["entity_id"] for item in configured}
    for item in family.values():
        if item["entity_id"] in existing:
            continue
        configured.append(
            {
                "id": item["id"],
                "name": item["name"],
                "entity_id": item["entity_id"],
            }
        )

    trackers: dict[str, dict] = {}
    for item in configured:
        entry = dict(item)
        trackers[entry["entity_id"]] = entry
    return trackers


async def _async_setup_shared(hass: HomeAssistant) -> None:
    """Register views, websocket commands and the frontend once."""
    if not hass.data.get(f"{DOMAIN}_websocket_registered"):
        async_register_websocket_api(hass)
        async_register_local_websocket_api(hass)
        hass.data[f"{DOMAIN}_websocket_registered"] = True

    if not hass.data.get(f"{DOMAIN}_export_registered"):
        hass.http.register_view(TimelineExportView())
        hass.data[f"{DOMAIN}_export_registered"] = True

    if not hass.data.get(f"{DOMAIN}_contacts_view_registered"):
        hass.http.register_view(ContactsImportView())
        hass.data[f"{DOMAIN}_contacts_view_registered"] = True

    if not hass.data.get(f"{DOMAIN}_import_view_registered"):
        hass.http.register_view(GeoPulseImportView())
        async_cleanup_uploads(hass)
        hass.data[f"{DOMAIN}_import_view_registered"] = True

    if not hass.data.get(f"{DOMAIN}_static_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    STATIC_URL,
                    str(Path(__file__).parent / "frontend"),
                    cache_headers=False,
                )
            ]
        )
        hass.data[f"{DOMAIN}_static_registered"] = True

    if not hass.data.get(f"{DOMAIN}_frontend_registered"):
        # Load the card for every dashboard, including YAML-mode dashboards.
        frontend.add_extra_js_url(hass, CARD_URL)
        hass.data[f"{DOMAIN}_frontend_registered"] = True


async def _async_apply(
    hass: HomeAssistant, conf: dict, source: str
) -> None:
    """Apply one configuration (YAML or a config entry)."""
    family = {
        item["entity_id"]: item for item in (conf.get(CONF_FAMILY) or [])
    }
    archive_conf = conf.get(CONF_ARCHIVE) or {}

    trackers = _resolve_trackers(archive_conf, family)
    if not trackers:
        _LOGGER.warning(
            "GeoPulse: geen trackers geconfigureerd; voeg er minimaal één toe "
            "in de integratie-instellingen"
        )

    archive: Archive | None = None
    if archive_conf.get(CONF_ARCHIVE_ENABLED, True):
        archive = Archive(hass, archive_conf.get(CONF_ARCHIVE_DATABASE))
        try:
            await archive.async_init()
        except Exception as err:  # noqa: BLE001 - never break HA startup
            _LOGGER.exception("Lokaal archief openen mislukt: %s", err)
            archive = None

    hass.data[DOMAIN] = {
        "allowed_user_ids": set(conf.get(CONF_ALLOWED_USER_IDS) or []),
        "family": family,
        "geocode": bool(conf.get(CONF_GEOCODE, True)),
        "archive": archive,
        "trackers": trackers,
        "contacts_file": archive_conf.get(CONF_CONTACTS_FILE),
    }
    hass.data[f"{DOMAIN}_source"] = source

    await _async_setup_shared(hass)

    if source == "entry":
        hass.data[f"{DOMAIN}_unsubs"] = []
        hass.data[f"{DOMAIN}_tasks"] = []

    def _track_task(task) -> None:
        hass.data.setdefault(f"{DOMAIN}_tasks", []).append(task)

    if archive is None:
        _LOGGER.info(
            "GeoPulse gereed (archief: uit, trackers: %s)", len(trackers)
        )
        return

    @callback
    def _state_changed(event) -> None:
        entity_id = event.data.get("entity_id")
        entry = trackers.get(entity_id)
        new_state = event.data.get("new_state")
        if entry is None or new_state is None:
            return
        old_state = event.data.get("old_state")
        if old_state is not None:
            old_attrs = old_state.attributes or {}
            new_attrs = new_state.attributes or {}
            if (
                old_attrs.get("latitude") == new_attrs.get("latitude")
                and old_attrs.get("longitude") == new_attrs.get("longitude")
                and old_state.state == new_state.state
            ):
                # Attribute-only update (battery, accuracy, ...): the
                # position did not change, so do not store a point.
                return
        timestamp = new_state.last_updated or new_state.last_changed
        if timestamp is None:
            return
        from .importer import _point_row

        row = _point_row(
            entry["id"],
            entity_id,
            timestamp.timestamp(),
            new_state.attributes or {},
            "live",
        )
        if row is not None:
            _track_task(hass.async_create_task(archive.async_add_points([row])))

    if trackers:
        unsub = async_track_state_change_event(
            hass, list(trackers.keys()), _state_changed
        )
        hass.data.setdefault(f"{DOMAIN}_unsubs", []).append(unsub)

    async def _async_prime_archive() -> None:
        days = int(archive_conf.get(CONF_BACKFILL_DAYS, 10))
        for entry in trackers.values():
            try:
                count = await backfill_recorder(hass, archive, entry, days)
                _LOGGER.info(
                    "Archief: %s recorder-punten toegevoegd voor %s",
                    count,
                    entry["name"],
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Archief: recorder-backfill voor %s mislukt: %s",
                    entry["name"],
                    err,
                )

    _track_task(
        hass.async_create_background_task(
            _async_prime_archive(), "geopulse_archive_prime"
        )
    )

    async def _async_prime_contacts() -> None:
        contacts_file = archive_conf.get(CONF_CONTACTS_FILE) or hass.config.path(
            "HA_timeline", "contacts.vcf"
        )
        try:
            stat = Path(contacts_file).stat()
            signature = f"{stat.st_mtime}:{stat.st_size}"
        except OSError:
            return
        last = await archive.async_meta("contacts_signature")
        if last != signature:
            try:
                await async_load_contacts(hass, archive, contacts_file)
                await archive.async_set_meta("contacts_signature", signature)
                _LOGGER.info("Contacten: adresboek bijgewerkt")
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Contacten laden mislukt: %s", err)
                return
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
        try:
            await async_geocode_pending(hass, archive, home)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Contacten geocoderen mislukt: %s", err)

    async def _async_prime_poi_index(max_tiles: int | None = None) -> None:
        if not archive_conf.get(CONF_POI_SYNC, True):
            return
        try:
            done = await async_sync_archive_tiles(
                hass, archive, max_tiles=max_tiles
            )
            if done:
                return
            # Empty archive or everything already fresh: still make sure
            # the home area is covered.
            zone = hass.states.get("zone.home")
            if zone is None:
                return
            latitude = float(zone.attributes["latitude"])
            longitude = float(zone.attributes["longitude"])
            await async_sync_home(hass, archive, latitude, longitude)
        except (KeyError, TypeError, ValueError):
            return
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("POI-index synchroniseren mislukt: %s", err)

    nightly_lock = asyncio.Lock()

    async def _async_nightly() -> None:
        if nightly_lock.locked():
            return
        async with nightly_lock:
            _LOGGER.info("Nachtelijke synchronisatie: contacten en POI-index")
            await _async_prime_contacts()
            # A night is long enough for a much bigger batch, so areas
            # from past trips (Amsterdam, Vienna, ...) get indexed too.
            await _async_prime_poi_index(NIGHTLY_TILES)

    @callback
    def _schedule_nightly(now) -> None:
        _track_task(hass.async_create_task(_async_nightly()))

    unsub = async_track_time_change(
        hass, _schedule_nightly, hour=3, minute=0, second=0
    )
    hass.data.setdefault(f"{DOMAIN}_unsubs", []).append(unsub)
    _LOGGER.info(
        "Nachtelijke synchronisatie gepland om 03:00 (contacten + POI-index)"
    )

    _track_task(
        hass.async_create_background_task(
            _async_prime_contacts(), "geopulse_contacts_prime"
        )
    )
    _track_task(
        hass.async_create_background_task(
            _async_prime_poi_index(), "geopulse_poi_index_prime"
        )
    )

    _LOGGER.info(
        "GeoPulse gereed (archief: aan, trackers: %s)", len(trackers)
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up GeoPulse from configuration.yaml (legacy mode)."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    if hass.config_entries.async_entries(DOMAIN):
        _LOGGER.warning(
            "GeoPulse: configuration.yaml wordt genegeerd omdat de integratie "
            "al via de gebruikersinterface is ingesteld"
        )
        return True

    await _async_apply(hass, conf, "yaml")
    return True


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up GeoPulse from a config entry."""
    if hass.data.get(f"{DOMAIN}_source") == "yaml":
        _LOGGER.warning(
            "GeoPulse: verwijder het geopulse-blok uit configuration.yaml om "
            "de instellingen uit de gebruikersinterface te gebruiken"
        )
        return True

    conf = {**entry.data, **entry.options}
    await _async_apply(hass, conf, "entry")

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry and stop its listeners and background tasks."""
    if hass.data.get(f"{DOMAIN}_source") != "entry":
        return True

    for unsub in hass.data.pop(f"{DOMAIN}_unsubs", []):
        try:
            unsub()
        except Exception:  # noqa: BLE001 - listener may already be gone
            pass
    for task in hass.data.pop(f"{DOMAIN}_tasks", []):
        task.cancel()
    hass.data.pop(DOMAIN, None)
    hass.data.pop(f"{DOMAIN}_source", None)
    return True


async def _async_update_listener(hass: HomeAssistant, entry) -> None:
    """Reload the entry after its options changed."""
    await hass.config_entries.async_reload(entry.entry_id)
