# TraceBook

> **Version 0.2.3.**

A Google Timeline-style day view for Home Assistant, built on a local SQLite
archive. TraceBook stores every location report from your device trackers
independently of the recorder retention, so years of history stay available
without an external location service.

## Features

- Day timeline with visits, trips, transport mode, distance and duration.
- Leaflet map with coloured routes, direction arrows, visit pins, legend and a
  day/night tile switch.
- Calendar with a dot for every day that has data.
- Edit visits: rename, choose a saved place, add a note, delete.
- Edit trips: change the transport mode, add a note, merge or rebuild a day.
- Move the first or last part of a route into another trip of the day and let it adopt that trip's mode.
- Adjacent visits at the same place (or both at home) are merged automatically.
- Search places worldwide and see how often you visited them within 75 m.
- Fuzzy text search around a visit (max. 250 m).
- Import GPX, GeoJSON and Google Timeline exports (Android, iOS and Takeout),
  including ZIP bundles.
- Export GPX or GeoJSON per month, year or previous year.
- Contacts from a `.vcf` file show up as known names.
- Local-first: only place-name lookups and address geocoding use the internet.

## Installation

### Marketplace (custom GitHub link)

1. Open **Marketplace** in Home Assistant.
2. Choose **Add via GitHub link**.
3. Enter `https://github.com/RemboIII/TraceBook`.
4. Install **TraceBook** and restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration → TraceBook**.

On older installations this is the HACS **Custom repositories** flow.

The card is bundled with the integration and loaded automatically; you do not
need a separate Lovelace resource.

### Manual

Copy `custom_components/tracebook` to your Home Assistant `config` directory and
restart. The card and Leaflet are served from `/tracebook_static/`.

## Configuration

The integration is configured through the UI:

- **Trackers** — device trackers whose history is archived.
- **Family members** — read-only timelines from the Home Assistant recorder,
  visible to administrators only.
- **Archive** — enable/disable storage, recorder backfill days, contacts file
  and the local OpenStreetMap place index.

The options flow (⋮ → **Configure**) changes the same settings without a
restart.

`configuration.yaml` is still supported for existing installations:

```yaml
tracebook:
  # Optional: restrict access to specific Home Assistant user ids.
  # allowed_user_ids:
  #   - <your-user-id>
  family:
    - id: sam
      name: Sam
      entity_id: device_tracker.sam_phone
  archive:
    enabled: true
    recorder_backfill_days: 10
    contacts_file: /config/HA_timeline/contacts.vcf
    poi_sync: true
    trackers:
      - id: alex
        name: Alex
        entity_id: device_tracker.alex_phone
```

Remove the YAML block when you switch to the UI; otherwise YAML takes
precedence.

## Dashboard card

```yaml
type: custom:tracebook-card
title: Timeline
person_name: Alex
source: local
entity_id: device_tracker.alex_phone
```

Family member from the archive (administrators only):

```yaml
type: custom:tracebook-card
title: Timeline Sam
person_name: Sam
source: local
entity_id: device_tracker.sam_phone
```

Recorder-only family member (read-only):

```yaml
type: custom:tracebook-card
person_name: Robin
source: ha_history
entity_id: device_tracker.robin_phone
```

Optional map settings:

```yaml
tile_url: https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png
tile_attribution: "&copy; OpenStreetMap contributors"
tile_max_zoom: 20
```

The card follows the Home Assistant user language: Dutch (`nl`) or English for
all other languages.

## Importing history

Open the card, click the magnifier (**Places**) and use **History → Import
file**. The import belongs to the tracker of that card.

Supported files:

- **GPX** — track points, route points and timestamped waypoints.
- **GeoJSON** — point features, or lines with `coordTimes`/`times`.
- **Google Timeline**:
  - `Timeline.json` from the Android app (`semanticSegments`, `rawSignals`);
  - `location-history.json` from the iOS app;
  - `Records.json` from Google Takeout;
  - `Semantic Location History/YYYY/YYYY_MONTH.json`.
- **ZIP** — any combination of the above, including a full Takeout archive.

Points are deduplicated by timestamp. Named places are added to the local place
index. Day snapshots in the imported period are dropped, except days you edited
manually. The upload limit is 512 MB; larger files are sent in 8 MB chunks
because Home Assistant caps a single request at 16 MB.

## Exporting

Use **Places → Export**, choose this month, this year or last year, and click
**GPX** or **GeoJSON**. The download streams directly from the archive.

## Data and privacy

Everything is stored in `/config/HA_timeline/archive.db`:

- `points` — every location report (source `live`, `recorder`, `gpx`,
  `geojson`, `google` or `legacy`).
- `places` — saved places.
- `place_index` — local OpenStreetMap, visit and imported places.
- `day_snapshots` — edited days with stable visit ids.
- `meta` — schema version, contacts signature and place-index progress.

Include this file in your Home Assistant backups. Only place-name lookups
(Photon, Nominatim, Overpass) and address geocoding leave your network; the
location history itself never does.

## Requirements

- Home Assistant 2024.6 or newer.
- One or more `device_tracker` entities with latitude/longitude attributes.

## License

MIT
