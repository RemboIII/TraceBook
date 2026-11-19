"""Contacts from the phone's address book, imported as vCard.

Android and iOS cannot expose the address book to a web page.  The practical
route is to export the contacts as a ``.vcf`` file and place it in the HA
config directory.  This module parses that file, groups contacts by address and
geocodes each address once, so the timeline can suggest "Bram & Janneke" when a
visit is at their home.

Export on Android: Contacts -> Settings -> Export -> share/save the .vcf, then
copy it to ``/config/HA_timeline/contacts.vcf``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import quopri
import re
import time
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .archive import Archive

_LOGGER = logging.getLogger(__name__)

PHOTON_URL = "https://photon.komoot.io/api/"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "GeoPulse/1.7 (Home Assistant)"
NOMINATIM_MIN_INTERVAL = 1.1
PHOTON_TIMEOUT = 4
PHOTON_DOWN_SECONDS = 600
_geocode_lock = asyncio.Lock()
_last_nominatim = 0.0
_photon_down_until = 0.0

COUNTRY_NAMES = {"NL": "Nederland", "BE": "België", "DE": "Duitsland"}


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if lines and raw.startswith((" ", "\t")):
            lines[-1] += raw[1:]
        elif lines and lines[-1].endswith("="):
            # Quoted-printable soft line break used by vCard 2.1.
            lines[-1] = lines[-1][:-1] + raw
        else:
            lines.append(raw)
    return lines


def _unescape(value: str) -> str:
    return (
        value.replace("\\n", " ")
        .replace("\\N", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _decode(value: str, params: str) -> str:
    """Decode vCard 2.1 quoted-printable values, then unescape."""
    if "QUOTED-PRINTABLE" in params.upper():
        try:
            raw = quopri.decodestring(value.encode("utf-8"))
            try:
                value = raw.decode("utf-8")
            except UnicodeDecodeError:
                value = raw.decode("latin-1")
        except Exception:  # noqa: BLE001 - fall back to the raw text
            pass
    return _unescape(value)


def _first_name(values: list[str]) -> str:
    for value in values:
        value = value.strip()
        if not value:
            continue
        # "Bram van Dijk" -> "Bram"; "Janneke" -> "Janneke".
        return value.split()[0]
    return ""


def _vcard_field(line: str) -> tuple[str, str, str]:
    """Return (name, params, value) for a vCard line."""
    if ":" not in line:
        return "", "", ""
    head, value = line.split(":", 1)
    parts = head.split(";")
    return parts[0].upper(), ";".join(parts[1:]), value


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def parse_vcards(text: str, default_country: str = "Nederland") -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in _unfold(text):
        upper = line.upper()
        if upper == "BEGIN:VCARD":
            current = {"fn": [], "n": [], "adr": [], "org": []}
            continue
        if upper == "END:VCARD":
            if current is not None:
                cards.append(current)
            current = None
            continue
        if current is None:
            continue
        name, params, value = _vcard_field(line)
        if name == "FN":
            current["fn"].append(_decode(value, params))
        elif name == "N":
            parts = _decode(value, params).split(";")
            if len(parts) >= 2:
                current["n"].append(parts[1])
            elif parts:
                current["n"].append(parts[0])
        elif name == "ORG":
            current["org"].append(_decode(value, params))
        elif name == "ADR":
            parts = _decode(value, params).split(";")
            # ADR: PO box; extended; street; locality; region; postcode; country
            while len(parts) < 7:
                parts.append("")
            current["adr"].append(
                {
                    "street": parts[2],
                    "city": parts[3],
                    "region": parts[4],
                    "postcode": parts[5],
                    "country": parts[6] or default_country,
                }
            )

    grouped: dict[str, dict[str, Any]] = {}
    for card in cards:
        address = next(
            (
                item
                for item in card["adr"]
                if item["street"] or item["city"]
            ),
            None,
        )
        if address is None:
            continue
        street = address["street"]
        city = address["city"]
        postcode = address["postcode"]
        country = address["country"]
        first = _first_name(card["fn"]) or _first_name(card["n"])
        if not first:
            first = (card["org"][0] if card["org"] else "").strip()
        if not first:
            continue

        # Group by street + city, not by the exact vCard text.  Android fills
        # the same household differently per contact ("37 F Emopad" vs
        # "37f Emopad", country "NL" vs "Nederland" vs empty), which used to
        # split families into separate entries.
        street_key = re.sub(r"[^a-z0-9]", "", street.lower())
        city_key = re.sub(r"[^a-z0-9]", "", city.lower())
        if street_key:
            key_source = f"{street_key}|{city_key}"
        else:
            # A city-only address must not merge every contact in that city.
            key_source = f"city|{city_key}|{_normalise(postcode)}|{_normalise(first)}"
        key = hashlib.sha1(key_source.encode("utf-8")).hexdigest()[:16]

        display_address = ", ".join(
            part for part in (street, f"{postcode} {city}".strip(), country) if part
        )
        group = grouped.get(key)
        if group is None:
            group = grouped[key] = {
                "address_key": key,
                "address": display_address,
                "street": street,
                "city": city,
                "postcode": postcode,
                "country": country,
                "names": [],
            }
        elif len(display_address) > len(group["address"]):
            # Keep the most complete spelling for geocoding/display.
            group.update(
                {
                    "address": display_address,
                    "street": street,
                    "city": city,
                    "postcode": postcode,
                    "country": country,
                }
            )
        if first not in group["names"]:
            group["names"].append(first)

    for group in grouped.values():
        group["display"] = " & ".join(group["names"])
    return list(grouped.values())


async def async_load_contacts(
    hass: HomeAssistant, archive: Archive, path: str
) -> int:
    file = Path(path)
    if not file.exists():
        return 0
    try:
        text = await hass.async_add_executor_job(file.read_text, "utf-8")
    except (OSError, UnicodeDecodeError) as err:
        _LOGGER.warning("Contacten lezen mislukt (%s): %s", path, err)
        return 0
    default_country = COUNTRY_NAMES.get(
        (hass.config.country or "NL").upper(), "Nederland"
    )
    contacts = parse_vcards(text, default_country)
    count = await archive.async_upsert_contacts(contacts)
    await archive.async_prune_contacts(
        [contact["address_key"] for contact in contacts]
    )
    _LOGGER.info("Contacten: %s adressen uit %s", len(contacts), path)
    return count


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 6371000.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


async def _geocode_photon(
    session, contact: dict[str, Any], home: tuple[float, float] | None
) -> tuple[float, float] | None:
    global _photon_down_until
    if time.monotonic() < _photon_down_until:
        return None
    query = ", ".join(
        part
        for part in (
            contact.get("street"),
            f"{contact.get('postcode') or ''} {contact.get('city') or ''}".strip(),
            contact.get("country"),
        )
        if part
    )
    if not query:
        return None
    params: dict[str, Any] = {"q": query, "limit": 5}
    if home is not None:
        params["lat"] = f"{home[0]:.6f}"
        params["lon"] = f"{home[1]:.6f}"
    try:
        async with session.get(
            PHOTON_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=PHOTON_TIMEOUT,
        ) as response:
            if response.status != 200:
                _photon_down_until = time.monotonic() + PHOTON_DOWN_SECONDS
                return None
            payload = await response.json()
    except Exception as err:  # noqa: BLE001 - geocoding is best effort
        _LOGGER.debug("Photon geocoding mislukt: %s", err)
        _photon_down_until = time.monotonic() + PHOTON_DOWN_SECONDS
        return None

    candidates = []
    for feature in payload.get("features") or []:
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        if len(coordinates) < 2:
            continue
        try:
            latitude = float(coordinates[1])
            longitude = float(coordinates[0])
        except (TypeError, ValueError):
            continue
        candidates.append((latitude, longitude))
    if not candidates:
        return None
    if home is not None:
        candidates.sort(key=lambda item: _distance_m(home, item))
        # Without a country in the vCard, stay near home to avoid matching a
        # same-named street abroad. With a country, accept the address even on
        # another continent (contacts can live in Austria, etc.).
        if not contact.get("country") and _distance_m(home, candidates[0]) > 200_000:
            return None
    return candidates[0]


async def _geocode_nominatim(
    session, contact: dict[str, Any]
) -> tuple[float, float] | None:
    global _last_nominatim
    wait = NOMINATIM_MIN_INTERVAL - (time.monotonic() - _last_nominatim)
    if wait > 0:
        await asyncio.sleep(wait)
    params = {
        "format": "jsonv2",
        "street": contact.get("street") or "",
        "city": contact.get("city") or "",
        "postalcode": contact.get("postcode") or "",
        "country": contact.get("country") or "",
        "limit": 1,
        "accept-language": "nl",
    }
    try:
        async with session.get(
            NOMINATIM_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=12,
        ) as response:
            if response.status != 200:
                return None
            payload = await response.json()
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Nominatim geocoding mislukt: %s", err)
        return None
    finally:
        _last_nominatim = time.monotonic()
    if not payload:
        return None
    try:
        return float(payload[0]["lat"]), float(payload[0]["lon"])
    except (KeyError, TypeError, ValueError):
        return None


async def async_geocode_pending(
    hass: HomeAssistant,
    archive: Archive,
    home: tuple[float, float] | None = None,
    limit: int = 500,
) -> int:
    """Geocode contact addresses that do not have coordinates yet."""
    async with _geocode_lock:
        pending = await archive.async_pending_contacts(limit=limit)
        if not pending:
            return 0
        session = async_get_clientsession(hass)
        done = 0
        for contact in pending:
            location = await _geocode_photon(session, contact, home)
            if location is None:
                location = await _geocode_nominatim(session, contact)
            if location is None:
                _LOGGER.debug(
                    "Contactadres niet gevonden: %s", contact.get("address")
                )
                continue
            await archive.async_set_contact_location(
                contact["address_key"], location[0], location[1]
            )
            done += 1
            if done % 10 == 0:
                _LOGGER.info(
                    "Contacten: %s van %s adressen gegeocodeerd",
                    done,
                    len(pending),
                )
        _LOGGER.info("Contacten: %s adressen gegeocodeerd", done)
        return done
