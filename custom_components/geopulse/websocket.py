"""Websocket API for TraceBook.

The timeline itself is served by ``websocket_local``.  This module holds the
shared authorization helpers and the recorder-backed commands for the family
tabs (people whose history is not in the local archive).
"""

from __future__ import annotations

import logging
from datetime import date

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .ha_history import get_ha_day, get_ha_month

_LOGGER = logging.getLogger(__name__)


def _authorized(hass: HomeAssistant, connection) -> bool:
    data = hass.data.get(DOMAIN)
    if data is None:
        return False

    allowed = data.get("allowed_user_ids") or set()
    if not allowed:
        return True

    return connection.user is not None and connection.user.id in allowed


def _is_admin(connection) -> bool:
    user = getattr(connection, "user", None)
    return bool(user is not None and getattr(user, "is_admin", False))


def _family_entry(hass: HomeAssistant, entity_id: str) -> dict | None:
    data = hass.data.get(DOMAIN) or {}
    return (data.get("family") or {}).get(entity_id)


def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the family-timeline websocket commands."""
    websocket_api.async_register_command(hass, websocket_ha_day)
    websocket_api.async_register_command(hass, websocket_ha_month)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/ha_day",
        vol.Required("date"): str,
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_ha_day(hass: HomeAssistant, connection, msg: dict) -> None:
    """Return the timeline for a family member from HA's recorder."""
    if not _is_admin(connection):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_UNAUTHORIZED,
            "Alleen de beheerder mag deze tijdlijn bekijken",
        )
        return

    entry = _family_entry(hass, msg["entity_id"])
    if entry is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Onbekende gezinsentiteit"
        )
        return

    try:
        date.fromisoformat(msg["date"])
    except ValueError:
        connection.send_error(
            msg["id"], websocket_api.ERR_INVALID_FORMAT, "Ongeldige datum"
        )
        return

    try:
        result = await get_ha_day(hass, msg["entity_id"], msg["date"])
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Fout bij ophalen HA-tijdlijn")
        connection.send_error(msg["id"], "recorder_error", str(err))
        return

    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "geopulse/ha_month",
        vol.Required("year"): vol.All(int, vol.Range(min=2000, max=2100)),
        vol.Required("month"): vol.All(int, vol.Range(min=1, max=12)),
        vol.Required("entity_id"): str,
    }
)
@websocket_api.async_response
async def websocket_ha_month(hass: HomeAssistant, connection, msg: dict) -> None:
    """Return calendar dots for a family member from HA's recorder."""
    if not _is_admin(connection):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_UNAUTHORIZED,
            "Alleen de beheerder mag deze tijdlijn bekijken",
        )
        return

    entry = _family_entry(hass, msg["entity_id"])
    if entry is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Onbekende gezinsentiteit"
        )
        return

    try:
        result = await get_ha_month(
            hass, msg["entity_id"], msg["year"], msg["month"]
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Fout bij ophalen HA-maand")
        connection.send_error(msg["id"], "recorder_error", str(err))
        return

    connection.send_result(msg["id"], result)
