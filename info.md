# TraceBook

> **Version 0.3.0.**

A Google Timeline-style day view for Home Assistant with a local SQLite
archive. Day timeline, map, calendar, editable visits and trips, place search,
contacts, GPX/GeoJSON export and import of GPX, GeoJSON and Google Timeline
exports.

Everything is stored locally; only place-name lookups and address geocoding use
the internet. The bundled Lovelace card is loaded automatically.

Install it via **Marketplace → Add via GitHub link** and configure it through **Settings → Devices & services → Add
integration → TraceBook**.

**Upgrading from 0.2.x:** the integration domain changed to `tracebook`.
Remove the old GeoPulse entry, uninstall it in the Marketplace, add this
repository again, and create the TraceBook entry. The local archive and edited
visits are kept.
