"""Constants for the GeoPulse integration."""

DOMAIN = "geopulse"

CONF_ALLOWED_USER_IDS = "allowed_user_ids"
CONF_FAMILY = "family"
CONF_GEOCODE = "geocode"
CONF_ARCHIVE = "archive"
CONF_ARCHIVE_ENABLED = "enabled"
CONF_BACKFILL_DAYS = "recorder_backfill_days"
CONF_TRACKERS = "trackers"
CONF_ARCHIVE_DATABASE = "database"
CONF_CONTACTS_FILE = "contacts_file"
CONF_POI_SYNC = "poi_sync"

MODE_COLORS = {
    "walking": "#22c55e",
    "running": "#f97316",
    "cycling": "#3b82f6",
    "driving": "#ef4444",
    "bus": "#eab308",
    "train": "#84cc16",
    "flying": "#06b6d4",
    "boat": "#14b8a6",
    "motorcycle": "#ec4899",
    "stationary": "#94a3b8",
    "unknown": "#94a3b8",
    "mixed": "#94a3b8",
}

JOURNEY_MODES = [
    "walking",
    "running",
    "cycling",
    "driving",
    "bus",
    "train",
    "flying",
    "boat",
    "motorcycle",
]
