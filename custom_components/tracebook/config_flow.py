"""Config and options flow for TraceBook."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_ALLOWED_USER_IDS,
    CONF_ARCHIVE,
    CONF_ARCHIVE_ENABLED,
    CONF_BACKFILL_DAYS,
    CONF_CONTACTS_FILE,
    CONF_FAMILY,
    CONF_GEOCODE,
    CONF_POI_SYNC,
    CONF_TRACKERS,
    DOMAIN,
)


def _people(
    hass: HomeAssistant,
    entity_ids: list[str],
    existing: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Turn selected entity ids into TraceBook tracker records."""
    result: list[dict[str, str]] = []
    used: set[str] = set()

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        current = existing.get(entity_id) or {}
        name = (
            (state.attributes.get("friendly_name") if state else None)
            or current.get("name")
            or entity_id.split(".", 1)[-1].replace("_", " ").title()
        )
        base = (
            slugify(str(name))
            or slugify(entity_id.split(".", 1)[-1])
            or "tracker"
        )
        person_id = base
        suffix = 2
        while person_id in used:
            person_id = f"{base}_{suffix}"
            suffix += 1
        used.add(person_id)
        result.append(
            {"id": person_id, "name": str(name), "entity_id": entity_id}
        )
    return result


def _existing_people(conf: dict[str, Any]) -> dict[str, dict[str, Any]]:
    archive = conf.get(CONF_ARCHIVE) or {}
    people = list(archive.get(CONF_TRACKERS) or []) + list(
        conf.get(CONF_FAMILY) or []
    )
    return {item["entity_id"]: item for item in people}


def _schema(conf: dict[str, Any]) -> vol.Schema:
    archive = conf.get(CONF_ARCHIVE) or {}
    trackers = [item["entity_id"] for item in archive.get(CONF_TRACKERS) or []]
    family = [item["entity_id"] for item in conf.get(CONF_FAMILY) or []]

    return vol.Schema(
        {
            vol.Required(CONF_TRACKERS, default=trackers): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="device_tracker", multiple=True
                )
            ),
            vol.Optional(CONF_FAMILY, default=family): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="device_tracker", multiple=True
                )
            ),
            vol.Optional(
                CONF_GEOCODE, default=bool(conf.get(CONF_GEOCODE, True))
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ARCHIVE_ENABLED,
                default=bool(archive.get(CONF_ARCHIVE_ENABLED, True)),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_BACKFILL_DAYS,
                default=int(archive.get(CONF_BACKFILL_DAYS, 10)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=365, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                CONF_CONTACTS_FILE,
                default=str(archive.get(CONF_CONTACTS_FILE) or ""),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_POI_SYNC,
                default=bool(archive.get(CONF_POI_SYNC, True)),
            ): selector.BooleanSelector(),
        }
    )


def _build_data(
    hass: HomeAssistant, conf: dict[str, Any], user_input: dict[str, Any]
) -> dict[str, Any]:
    existing = _existing_people(conf)
    contacts = str(user_input.get(CONF_CONTACTS_FILE) or "").strip()
    return {
        CONF_ALLOWED_USER_IDS: list(conf.get(CONF_ALLOWED_USER_IDS) or []),
        CONF_GEOCODE: bool(user_input.get(CONF_GEOCODE, True)),
        CONF_FAMILY: _people(
            hass, list(user_input.get(CONF_FAMILY) or []), existing
        ),
        CONF_ARCHIVE: {
            CONF_ARCHIVE_ENABLED: bool(
                user_input.get(CONF_ARCHIVE_ENABLED, True)
            ),
            CONF_BACKFILL_DAYS: int(user_input.get(CONF_BACKFILL_DAYS, 10)),
            CONF_CONTACTS_FILE: contacts or None,
            CONF_POI_SYNC: bool(user_input.get(CONF_POI_SYNC, True)),
            CONF_TRACKERS: _people(
                hass, list(user_input.get(CONF_TRACKERS) or []), existing
            ),
        },
    }


class TraceBookConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up TraceBook from the Home Assistant UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):
        if self.hass.data.get(f"{DOMAIN}_source") == "yaml":
            return self.async_abort(reason="yaml_configured")
        errors: dict[str, str] = {}

        if user_input is not None:
            trackers = list(user_input.get(CONF_TRACKERS) or [])
            missing = [
                entity_id
                for entity_id in trackers
                if self.hass.states.get(entity_id) is None
            ]
            if not trackers:
                errors["base"] = "no_trackers"
            elif missing:
                errors["base"] = "unknown_entity"
            else:
                data = _build_data(self.hass, {}, user_input)
                return self.async_create_entry(title="TraceBook", data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema({}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TraceBookOptionsFlow()


class TraceBookOptionsFlow(config_entries.OptionsFlow):
    """Edit the trackers and archive settings of an existing entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        conf = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            trackers = list(user_input.get(CONF_TRACKERS) or [])
            missing = [
                entity_id
                for entity_id in trackers
                if self.hass.states.get(entity_id) is None
            ]
            if not trackers:
                errors["base"] = "no_trackers"
            elif missing:
                errors["base"] = "unknown_entity"
            else:
                data = _build_data(self.hass, conf, user_input)
                return self.async_create_entry(title="", data=data)

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(conf),
            errors=errors,
        )
