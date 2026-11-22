/* GeoPulse card for Home Assistant
 * A Google Timeline-style day view backed by the local GeoPulse archive.
 */

const CARD_VERSION = "0.2.0";

//: Text search in the visit editor only looks this far from the visit.
const MAX_PLACE_SEARCH_METERS = 250;
//: Places shown in the editor before typing.
const NEARBY_PLACE_RADIUS_METERS = 75;

const MODES = {
  walking: {
    emoji: "🚶",
    label: "Wandelen",
    label_en: "Walking",
    short: "Lopen",
    short_en: "Walk",
    color: "#22c55e",
    icon: "mdi:walk",
  },
  running: {
    emoji: "🏃",
    label: "Hardlopen",
    label_en: "Running",
    short: "Hardlopen",
    short_en: "Run",
    color: "#f97316",
    icon: "mdi:run",
  },
  cycling: {
    emoji: "🚴",
    label: "Met de fiets",
    label_en: "Cycling",
    short: "Fiets",
    short_en: "Bike",
    color: "#3b82f6",
    icon: "mdi:bike",
  },
  driving: {
    emoji: "🚗",
    label: "Met de auto",
    label_en: "Driving",
    short: "Auto",
    short_en: "Car",
    color: "#ef4444",
    icon: "mdi:car",
  },
  bus: {
    emoji: "🚌",
    label: "Met de bus",
    label_en: "Bus",
    short: "Bus",
    short_en: "Bus",
    color: "#eab308",
    icon: "mdi:bus",
  },
  train: {
    emoji: "🚆",
    label: "Met de trein",
    label_en: "Train",
    short: "Trein",
    short_en: "Train",
    color: "#84cc16",
    icon: "mdi:train",
  },
  flying: {
    emoji: "✈️",
    label: "Met het vliegtuig",
    label_en: "Flying",
    short: "Vliegtuig",
    short_en: "Plane",
    color: "#06b6d4",
    icon: "mdi:airplane",
  },
  boat: {
    emoji: "⛵",
    label: "Met de boot",
    label_en: "Boat",
    short: "Boot",
    short_en: "Boat",
    color: "#14b8a6",
    icon: "mdi:ferry",
  },
  motorcycle: {
    emoji: "🏍️",
    label: "Met de motor",
    label_en: "Motorcycle",
    short: "Motor",
    short_en: "Moto",
    color: "#ec4899",
    icon: "mdi:motorbike",
  },
  stationary: {
    emoji: "🛑",
    label: "Stilgestaan",
    label_en: "Stationary",
    short: "Gestopt",
    short_en: "Stopped",
    color: "#94a3b8",
    icon: "mdi:stop-circle-outline",
  },
  unknown: {
    emoji: "🧭",
    label: "Onderweg",
    label_en: "Moving",
    short: "Onderweg",
    short_en: "Moving",
    color: "#94a3b8",
    icon: "mdi:map-marker-path",
  },
  mixed: {
    emoji: "🔀",
    label: "Gemengde reis",
    label_en: "Mixed trip",
    short: "Gemengd",
    short_en: "Mixed",
    color: "#94a3b8",
    icon: "mdi:swap-horizontal",
  },
};

const JOURNEY_MODE_ORDER = [
  "walking",
  "running",
  "cycling",
  "driving",
  "bus",
  "train",
  "flying",
  "boat",
  "motorcycle",
];

const MONTHS_NL = [
  "januari",
  "februari",
  "maart",
  "april",
  "mei",
  "juni",
  "juli",
  "augustus",
  "september",
  "oktober",
  "november",
  "december",
];

const MONTHS_SHORT_NL = [
  "jan",
  "feb",
  "mrt",
  "apr",
  "mei",
  "jun",
  "jul",
  "aug",
  "sep",
  "okt",
  "nov",
  "dec",
];

const WEEKDAYS_NL = [
  "zondag",
  "maandag",
  "dinsdag",
  "woensdag",
  "donderdag",
  "vrijdag",
  "zaterdag",
];

const WEEKDAYS_SHORT_NL = ["zo", "ma", "di", "wo", "do", "vr", "za"];
const WEEKDAYS_MIN_NL = ["ma", "di", "wo", "do", "vr", "za", "zo"];

const MONTHS_EN = [
  "january", "february", "march", "april", "may", "june",
  "july", "august", "september", "october", "november", "december",
];
const MONTHS_SHORT_EN = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];
const WEEKDAYS_EN = [
  "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
];
const WEEKDAYS_SHORT_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const WEEKDAYS_MIN_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

//: Language of the card follows the Home Assistant user language.  Dutch is
//: the source language; every other language falls back to English.
let CARD_LANG = "nl";

function isEnglish() {
  return CARD_LANG === "en";
}
function months() {
  return isEnglish() ? MONTHS_EN : MONTHS_NL;
}
function monthsShort() {
  return isEnglish() ? MONTHS_SHORT_EN : MONTHS_SHORT_NL;
}
function weekdays() {
  return isEnglish() ? WEEKDAYS_EN : WEEKDAYS_NL;
}
function weekdaysShort() {
  return isEnglish() ? WEEKDAYS_SHORT_EN : WEEKDAYS_SHORT_NL;
}
function weekdaysMin() {
  return isEnglish() ? WEEKDAYS_MIN_EN : WEEKDAYS_MIN_NL;
}
function numberLocale() {
  return isEnglish() ? "en-GB" : "nl-NL";
}

const COUNTRY_NAMES = {
  Netherlands: "Nederland",
  Belgium: "België",
  Germany: "Duitsland",
  France: "Frankrijk",
  Luxembourg: "Luxemburg",
  "United Kingdom": "Verenigd Koninkrijk",
  Austria: "Oostenrijk",
  Switzerland: "Zwitserland",
  Spain: "Spanje",
  Italy: "Italië",
  Denmark: "Denemarken",
  Sweden: "Zweden",
  Norway: "Noorwegen",
};

const PROVINCE_NAMES = {
  "North Brabant": "Noord-Brabant",
  "South Holland": "Zuid-Holland",
  "North Holland": "Noord-Holland",
  "North Rhine-Westphalia": "Noordrijn-Westfalen",
};

const CONFIDENCE_LABELS = {
  high: "Zeker",
  medium: "Waarschijnlijk",
  low: "Onzeker",
};

const PIN_SVG =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a7 7 0 0 0-7 7c0 5.1 5.4 11 6.3 12a1 1 0 0 0 1.4 0C13.6 20 19 14.1 19 9a7 7 0 0 0-7-7Zm0 9.6A2.6 2.6 0 1 1 12 6.4a2.6 2.6 0 0 1 0 5.2Z"/></svg>';

const HOUSE_SVG =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.2 2.8 10.5a1 1 0 0 0 .6 1.8H5v7.2a1.5 1.5 0 0 0 1.5 1.5H10v-5.5h4V21h3.5a1.5 1.5 0 0 0 1.5-1.5v-7.2h1.6a1 1 0 0 0 .6-1.8Z"/></svg>';

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function pad2(value) {
  return String(value).padStart(2, "0");
}

function toISO(date) {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(
    date.getDate()
  )}`;
}

function todayISO() {
  return toISO(new Date());
}

function parseISO(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function addDays(iso, delta) {
  const date = parseISO(iso);
  date.setDate(date.getDate() + delta);
  return toISO(date);
}

function dutchPlaceName(value) {
  if (isEnglish()) return String(value ?? "");
  let result = String(value ?? "");
  for (const [source, target] of Object.entries(PROVINCE_NAMES)) {
    result = result.replaceAll(source, target);
  }
  for (const [source, target] of Object.entries(COUNTRY_NAMES)) {
    result = result.replaceAll(source, target);
  }
  return result;
}

function normalizeSearchText(value) {
  let text = String(value ?? "");
  const replacements = {
    ß: "ss",
    æ: "ae",
    œ: "oe",
    ø: "o",
    ł: "l",
    đ: "d",
    ð: "d",
    þ: "th",
    ı: "i",
    ĳ: "ij",
  };
  for (const [source, target] of Object.entries(replacements)) {
    text = text
      .replaceAll(source, target)
      .replaceAll(source.toUpperCase(), target.toUpperCase());
  }
  return text
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^0-9a-z]+/g, " ")
    .trim();
}

function capitalize(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

function fmtDateLong(iso) {
  const date = parseISO(iso);
  return `${capitalize(weekdays()[date.getDay()])} ${date.getDate()} ${
    months()[date.getMonth()]
  } ${date.getFullYear()}`;
}

function fmtDateShort(iso) {
  const date = parseISO(iso);
  const now = new Date();
  const suffix = date.getFullYear() === now.getFullYear() ? "" : ` ${date.getFullYear()}`;
  return `${weekdaysShort()[date.getDay()]} ${date.getDate()} ${
    monthsShort()[date.getMonth()]
  }${suffix}`;
}

function headerLabel(iso) {
  const today = todayISO();
  if (iso === today) return isEnglish() ? "Today" : "Vandaag";
  if (iso === addDays(today, -1)) return isEnglish() ? "Yesterday" : "Gisteren";
  return fmtDateShort(iso);
}

function fmtTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString(numberLocale(), {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtDistance(km, unit = "km") {
  const value = Number(km) || 0;
  if (unit === "mi") {
    if (value < 0.1) return `${Math.round(value * 1609)} m`;
    const miles = value * 1.60934;
    return `${new Intl.NumberFormat(numberLocale(), {
      maximumFractionDigits: miles < 100 ? 1 : 0,
    }).format(miles)} mi`;
  }
  if (value < 1) return `${Math.round(value * 1000)} m`;
  return `${new Intl.NumberFormat(numberLocale(), {
    maximumFractionDigits: value < 100 ? 1 : 0,
  }).format(value)} km`;
}

function fmtMinutes(minutes) {
  const value = Math.max(0, Math.round(Number(minutes) || 0));
  if (value < 60) return `${value} min`;
  const hours = Math.floor(value / 60);
  const rest = value % 60;
  const short = isEnglish() ? "h" : "u";
  return rest ? `${hours} ${short} ${rest} min` : `${hours} ${short}`;
}

function fmtSeconds(seconds) {
  return fmtMinutes((Number(seconds) || 0) / 60);
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function modeInfo(mode) {
  return MODES[mode] || MODES.unknown;
}

function modeLabel(mode) {
  const info = modeInfo(mode);
  return isEnglish() ? info.label_en || info.label : info.label;
}

function modeShort(mode) {
  const info = modeInfo(mode);
  return isEnglish() ? info.short_en || info.short : info.short;
}

function confidenceLabel(key) {
  const nl = CONFIDENCE_LABELS[key];
  if (!nl || !isEnglish()) return nl;
  return { high: "Certain", medium: "Likely", low: "Uncertain" }[key] || nl;
}

/* ------------------------------------------------------------------ */
/* English translation of the Dutch interface strings                 */
/* ------------------------------------------------------------------ */

const I18N_ATTRS = ["title", "aria-label", "placeholder", "alt"];

const EN_TEXT = {
  "Tijdlijn": "Timeline",
  "Jouw bewegingen per dag": "Your movements by day",
  "Vandaag": "Today",
  "Vorige dag": "Previous day",
  "Volgende dag": "Next day",
  "Vernieuwen": "Refresh",
  "Plaatsen zoeken": "Search places",
  "Alles in beeld": "Fit to view",
  "Kaart maximaliseren": "Maximize map",
  "Kaart verkleinen": "Restore map",
  "Wandel- en fietskaart": "Walking and cycling map",
  "Kaartlaag wisselen": "Change map layer",
  "Tijdlijnpaneel groter of kleiner maken": "Resize the timeline panel",
  "Geen locaties op deze dag": "No locations on this day",
  "Geen beweging op deze dag": "No movement on this day",
  "Kies een andere dag of controleer of de tracker locaties doorgeeft.":
    "Choose another day or check that the tracker reports locations.",
  "Gegevens niet beschikbaar": "Data unavailable",
  "Opnieuw proberen": "Try again",
  "Suggestie": "Suggestion",
  "Bevestigd": "Confirmed",
  "Samengevoegd": "Merged",
  "vanaf vorige dag": "since previous day",
  "Ja": "Yes",
  "Bewerken": "Edit",
  "Aanpassen": "Edit",
  "Samenvoegen": "Merge",
  "Splitsen": "Split",
  "Vorige maand": "Previous month",
  "Volgende maand": "Next month",
  "dag met gegevens": "day with data",
  "Plaatsen": "Places",
  "Zoek": "Search",
  "Zoeken…": "Searching…",
  "Geen plekken gevonden.": "No places found.",
  "Zoek een plek om te zien of en hoe vaak je er geweest bent.":
    "Search for a place to see whether and how often you have been there.",
  "Bijv. Apollopad of een winkel…": "E.g. Main Street or a shop…",
  "Bewaar als plek": "Save as place",
  "Al bewaard": "Already saved",
  "Sluiten": "Close",
  "Exporteren": "Export",
  "Deze maand": "This month",
  "Dit jaar": "This year",
  "Vorig jaar": "Last year",
  "Adresboek": "Contacts",
  "Importeer .vcf": "Import .vcf",
  "Historie": "History",
  "Importeer bestand": "Import file",
  "nog niet bezocht": "not visited yet",
  "Bezoek aanpassen": "Edit visit",
  "Plek (POI)": "Place (POI)",
  "Naam (optioneel)": "Name (optional)",
  "Laat leeg om de naam van de gekozen plek te gebruiken.":
    "Leave empty to use the name of the selected place.",
  "Annuleren": "Cancel",
  "Bevestigen": "Confirm",
  "Plekken laden…": "Loading places…",
  "Eigen naam voor dit bezoek": "Custom name for this visit",
  "Reis aanpassen": "Edit trip",
  "Reismethode": "Transport mode",
  "Opmerking (optioneel)": "Note (optional)",
  "Deze opmerking wordt alleen in Home Assistant bewaard.":
    "This note is stored in Home Assistant only.",
  "Opslaan": "Save",
  "Bijv. Boswandeling met Rubbel": "E.g. Forest walk with the dog",
  "Kaart kon niet worden geladen": "Could not load the map",
  "Geen tracker gekoppeld voor deze kaart": "No tracker linked to this card",
  "Geen bezoek gevonden binnen de zoekstraal": "No visit found within the search radius",
  "Plek bewaard": "Place saved",
  "Geen tracker gekoppeld": "No tracker linked",
  "Export gestart — het bestand wordt gedownload":
    "Export started — the file is being downloaded",
  "Kaartlaag is via tile_url ingesteld": "The map layer is set through tile_url",
  "Bezoek bevestigd": "Visit confirmed",
  "Bezoek bijgewerkt en bevestigd": "Visit updated and confirmed",
  "Bezoek verwijderd": "Visit removed",
  "Reis bijgewerkt": "Trip updated",
  "Reizen samengevoegd": "Trips merged",
  "Dag opnieuw opgebouwd": "Day rebuilt",
  "Dagkaart": "Day map",
  "Nachtkaart": "Night map",
  "Importeren…": "Importing…",
  "Lezen mislukt": "Could not read the file",
  "Dit is geen .vcf-bestand": "This is not a .vcf file",
  "Importeren mislukt": "Import failed",
  "Mislukt": "Failed",
  "Contacten importeren mislukt": "Importing contacts failed",
  "Bewaren mislukt": "Saving failed",
  "Bevestigen mislukt": "Confirming failed",
  "Opslaan mislukt": "Saving failed",
  "Verwijderen mislukt": "Removing failed",
  "Samenvoegen mislukt": "Merging failed",
  "Herberekenen mislukt": "Rebuilding failed",
  "Exporteren mislukt": "Exporting failed",
  "Zoeken mislukt. Probeer het opnieuw.": "Search failed. Please try again.",
  "Zoeken duurde te lang. Probeer het opnieuw.":
    "The search took too long. Please try again.",
  "Kon de gegevens van deze dag niet ophalen.":
    "Could not load the data for this day.",
  "Dit bezoek verwijderen? Het verdwijnt uit de tijdlijn. Je kunt de dag later opnieuw opbouwen.":
    "Remove this visit? It disappears from the timeline. You can rebuild the day later.",
  "Deze dag opnieuw opbouwen? Handmatige aanpassingen aan de hele dag gaan verloren.":
    "Rebuild this day? Manual changes to the whole day will be lost.",
  "Bezig…": "Working…",
  "Niet gevonden? Gebruik het veld Naam (optioneel) om dit bezoek zelf een naam te geven.":
    "Not found? Use the Name (optional) field to give this visit a custom name.",
  "Route splitsen": "Split route",
  "Splitstijd:": "Split time:",
  "Eerste deel → vorige reis": "First part → previous trip",
  "Laatste deel → volgende reis": "Last part → next trip",
  "Tussenliggende bezoeken worden verwijderd. Doorgaan?":
    "Visits in between will be removed. Continue?",
  "Deel verplaatst": "Part moved",
  "Verplaatsen mislukt": "Moving failed",
  "Kies een ander splitpunt.": "Choose another split point.",
  "Verplaatsen…": "Moving…",
  "Het gekozen deel gaat naar de aangrenzende reis en krijgt de methode van die reis. Tussenliggende bezoeken worden verwijderd.":
    "The selected part is moved to the adjacent trip and adopts its mode. Visits in between are removed.",
  "Deze reis bestaat uit": "This trip consists of",
  "ritten.": "parts.",
};

const EN_PATTERNS = [
  [/^(\d+) bezoeken$/, "$1 visits"],
  [/^(\d+) bezoek$/, "$1 visit"],
  [/^(\d+) plekken$/, "$1 places"],
  [/^(\d+) plek$/, "$1 place"],
  [/^Laatst: (.*)$/, "Last: $1"],
  [/^Geen bezoek gevonden binnen (\d+) m$/, "No visit found within $1 m"],
  [/^(.+) onderweg$/, "$1 moving"],
  [/^Bewegingen van (.+)$/, "Movements of $1"],
  [/^(\d+) adressen uit het adresboek geïmporteerd$/,
    "$1 addresses imported from the contacts file"],
  [/^(\d+) adres uit het adresboek geïmporteerd$/,
    "$1 address imported from the contacts file"],
  [/^(\d+) locatiepunten geïmporteerd$/, "$1 location points imported"],
  [/^(\d+) locatiepunten geïmporteerd en (\d+) plekken opgeslagen$/,
    "$1 location points imported and $2 places saved"],
  [/^(\d+) locatiepunten geïmporteerd en (\d+) plek opgeslagen$/,
    "$1 location points imported and $2 place saved"],
  [/^(\d+) locatiepunt geïmporteerd$/, "$1 location point imported"],
  [/^(\d+) punten$/, "$1 points"],
  [/^Bezig… \((\d+) MB\)$/, "Working… ($1 MB)"],
  [/^Bezig… (\d+)% \((\d+) MB\)$/, "Working… $1% ($2 MB)"],
  [/^Bezig… (\d+)%$/, "Working… $1%"],
];

function translateText(value) {
  if (!isEnglish() || value == null) return value;
  const text = String(value);
  const trimmed = text.trim();
  if (!trimmed) return value;
  let out = EN_TEXT[trimmed];
  if (out === undefined) {
    for (const [pattern, replacement] of EN_PATTERNS) {
      if (pattern.test(trimmed)) {
        out = trimmed.replace(pattern, replacement);
        break;
      }
    }
  }
  if (out === undefined) return value;
  return text.replace(trimmed, out);
}

function localizeAttributes(element) {
  if (!element?.getAttribute) return;
  for (const attr of I18N_ATTRS) {
    const current = element.getAttribute(attr);
    if (!current) continue;
    const next = translateText(current);
    if (next !== current) element.setAttribute(attr, next);
  }
}

function localizeTree(root) {
  if (!root || !isEnglish()) return;
  if (root.nodeType === Node.TEXT_NODE) {
    root.nodeValue = translateText(root.nodeValue);
    return;
  }
  if (
    root.nodeType !== Node.ELEMENT_NODE &&
    root.nodeType !== Node.DOCUMENT_FRAGMENT_NODE
  ) {
    return;
  }
  localizeAttributes(root);
  const doc = root.ownerDocument || document;
  const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentElement?.closest?.("style, script")) continue;
    const next = translateText(node.nodeValue);
    if (next !== node.nodeValue) node.nodeValue = next;
  }
  for (const element of root.querySelectorAll?.("[title],[aria-label],[placeholder],[alt]") || []) {
    localizeAttributes(element);
  }
}

function isTextInput(element) {
  if (!element) return false;
  const tag = element.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    element.isContentEditable
  );
}

/* ------------------------------------------------------------------ */
/* Card                                                                */
/* ------------------------------------------------------------------ */

class GeoPulseCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });

    this._initialized = false;
    this._hass = null;
    this._config = {};
    this._date = todayISO();
    this._data = null;
    this._error = null;
    this._loading = false;
    this._loadToken = 0;
    this._fitMap = true;
    this._selectedKey = null;

    this._calendarOpen = false;
    this._calYear = 0;
    this._calMonth = 0;
    this._monthDays = null;
    this._monthToken = 0;

    this._places = null;
    this._placesPromise = null;
    this._placesSearch = {
      open: false,
      query: "",
      results: [],
      loading: false,
      error: null,
    };

    this._edit = null;

    this._map = null;
    this._mapInitPromise = null;
    this._leafletPromise = null;
    this._routeLayer = null;
    this._visitLayer = null;
    this._routeVisuals = {};
    this._visitVisuals = {};
    this._mapMaximized = false;
    this._fittedDate = null;

    this._journeyEdit = null;

    this._resizeObserver = null;
    this._docClick = null;
    this._keydown = null;
    this._resizeWin = null;
    this._visibilityHandler = null;
    this._refreshMapTimer = null;
    this._mapResizeTimer = null;
    this._resizer = null;
    this._main = null;
    this._splitDrag = null;
    this._resizing = false;
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    const language = String(
      hass?.locale?.language || hass?.language || "nl"
    )
      .split("-")[0]
      .toLowerCase();
    CARD_LANG = language === "nl" ? "nl" : "en";
    if (first) this._init();
  }

  connectedCallback() {
    if (!this._initialized && this._hass) this._init();
    this._attachDocumentListeners();
    if (this._app) window.setTimeout(() => this._applyStoredSplit(), 60);
    if (this._map) {
      window.setTimeout(() => this._map?.invalidateSize({ pan: false }), 120);
    }
  }

  disconnectedCallback() {
    this._detachDocumentListeners();
    if (this._i18nObserver) {
      this._i18nObserver.disconnect();
      this._i18nObserver = null;
    }
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }
  }

  /* ---------------------------------------------------------------- */
  /* Initialisation                                                    */
  /* ---------------------------------------------------------------- */

  _init() {
    if (this._initialized || !this._hass) return;
    this._initialized = true;

    this._renderShell();
    this._startLocalizer();
    this._attachShadowListeners();
    this._updateHeader();
    window.setTimeout(() => this._applyStoredSplit(), 60);
    this._loadLeaflet()
      .then(() => this._initMap())
      .catch((err) => {
        console.error("GeoPulse: Leaflet laden mislukt", err);
        this._toast("Kaart kon niet worden geladen", "error");
      });
    this._loadDay();
  }

  _startLocalizer() {
    if (this._i18nObserver || !this.shadowRoot) return;
    localizeTree(this.shadowRoot);
    if (!isEnglish()) return;
    this._i18nObserver = new MutationObserver((mutations) => {
      if (!isEnglish()) return;
      for (const mutation of mutations) {
        if (mutation.type === "attributes") {
          localizeTree(mutation.target);
          continue;
        }
        for (const node of mutation.addedNodes) localizeTree(node);
      }
    });
    this._i18nObserver.observe(this.shadowRoot, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: I18N_ATTRS,
    });
  }

  _renderShell() {
    const style = document.createElement("style");
    style.textContent = this._css();

    const app = document.createElement("div");
    app.className = "dt-app";
    app.innerHTML = `
      <header class="dt-topbar">
        <div class="dt-brand">
          <div class="dt-brand-icon"><ha-icon icon="mdi:map-clock-outline"></ha-icon></div>
          <div class="dt-brand-text">
            <div class="dt-title">${esc(this._config.title || "Tijdlijn")}</div>
            <div class="dt-brand-sub">${esc(
              this._config.subtitle ||
                (this._config.person_name
                  ? `Bewegingen van ${this._config.person_name}`
                  : "Jouw bewegingen per dag")
            )}</div>
          </div>
        </div>

        <div class="dt-datenav">
          <button class="dt-iconbtn" data-nav="prev" title="Vorige dag" aria-label="Vorige dag">
            <ha-icon icon="mdi:chevron-left"></ha-icon>
          </button>
          <button class="dt-datebtn" data-action="calendar" aria-haspopup="dialog" aria-expanded="false">
            <ha-icon icon="mdi:calendar-month-outline"></ha-icon>
            <span class="dt-datelabel">Vandaag</span>
            <ha-icon icon="mdi:chevron-down" class="dt-chev"></ha-icon>
          </button>
          <button class="dt-iconbtn" data-nav="next" title="Volgende dag" aria-label="Volgende dag">
            <ha-icon icon="mdi:chevron-right"></ha-icon>
          </button>
          <button class="dt-todaybtn" data-action="today">Vandaag</button>
        </div>

        <div class="dt-spacer"></div>

        <button class="dt-iconbtn dt-placesbtn" data-action="places" title="Plaatsen zoeken" aria-label="Plaatsen zoeken">
          <ha-icon icon="mdi:map-search-outline"></ha-icon>
        </button>
        <button class="dt-iconbtn dt-refresh" data-action="refresh" title="Vernieuwen" aria-label="Vernieuwen">
          <ha-icon icon="mdi:refresh"></ha-icon>
        </button>
      </header>

      <div class="dt-main">
        <section class="dt-mapwrap">
          <div class="dt-map" id="dt-map"></div>

          <div class="dt-map-badge">
            <ha-icon icon="mdi:map-marker-path"></ha-icon>
            <span class="dt-map-daylabel">Vandaag</span>
          </div>

          <button class="dt-mapbtn" data-action="fit" title="Alles in beeld" aria-label="Alles in beeld">
            <ha-icon icon="mdi:fit-to-page-outline"></ha-icon>
          </button>
          <button class="dt-mapbtn dt-map-max" data-action="map-max" title="Kaart maximaliseren" aria-label="Kaart maximaliseren">
            <ha-icon icon="mdi:arrow-expand"></ha-icon>
          </button>
          <button class="dt-mapbtn dt-map-style" data-action="map-style" title="Wandel- en fietskaart" aria-label="Kaartlaag wisselen">
            <ha-icon icon="mdi:layers-outline"></ha-icon>
          </button>

          <div class="dt-legend" hidden></div>

          <div class="dt-map-empty" hidden>
            <ha-icon icon="mdi:map-marker-off-outline"></ha-icon>
            <div>Geen locaties op deze dag</div>
          </div>

          <div class="dt-map-spinner dt-spinner" hidden><span></span></div>
        </section>

        <aside class="dt-side">
          <div class="dt-resizer" role="separator" aria-orientation="horizontal"
               aria-label="Tijdlijnpaneel groter of kleiner maken" tabindex="0">
            <span></span>
          </div>
          <div class="dt-sidehead">
            <div class="dt-daytitle"></div>
            <div class="dt-summary"></div>
          </div>
          <div class="dt-listwrap">
            <div class="dt-loadingbar" hidden></div>
            <div class="dt-list"></div>
          </div>
        </aside>
      </div>

      <div class="dt-calpop" hidden></div>
      <div class="dt-placespop" hidden></div>
      <div class="dt-modal" hidden></div>
      <div class="dt-toasts" role="status" aria-live="polite"></div>
    `;

    this.shadowRoot.replaceChildren(style, app);

    this._app = app;
    this._mapEl = app.querySelector("#dt-map");
    this._mapWrap = app.querySelector(".dt-mapwrap");
    this._dateBtn = app.querySelector(".dt-datebtn");
    this._dateLabel = app.querySelector(".dt-datelabel");
    this._mapDayLabel = app.querySelector(".dt-map-daylabel");
    this._nextBtn = app.querySelector('[data-nav="next"]');
    this._todayBtn = app.querySelector(".dt-todaybtn");
    this._dayTitle = app.querySelector(".dt-daytitle");
    this._summary = app.querySelector(".dt-summary");
    this._list = app.querySelector(".dt-list");
    this._listWrap = app.querySelector(".dt-listwrap");
    this._loadingBar = app.querySelector(".dt-loadingbar");
    this._mapSpinner = app.querySelector(".dt-map-spinner");
    this._mapEmpty = app.querySelector(".dt-map-empty");
    this._mapMaxBtn = app.querySelector(".dt-map-max");
    this._mapStyleBtn = app.querySelector(".dt-map-style");
    this._legend = app.querySelector(".dt-legend");
    this._calendarPop = app.querySelector(".dt-calpop");
    this._placesPop = app.querySelector(".dt-placespop");
    this._modal = app.querySelector(".dt-modal");
    this._toasts = app.querySelector(".dt-toasts");
    this._calPop = app.querySelector(".dt-calpop");
    this._main = app.querySelector(".dt-main");
    this._resizer = app.querySelector(".dt-resizer");
    this._setupSplit();
  }

  /* ---------------------------------------------------------------- */
  /* Resizable timeline panel (mobile)                                 */
  /* ---------------------------------------------------------------- */

  _isMobileLayout() {
    return window.matchMedia("(max-width: 820px)").matches;
  }

  _splitLimits() {
    const mainH = this._main?.getBoundingClientRect().height || 0;
    const minMap = 160;
    const minSide = 190;
    return {
      mainH,
      minMap,
      maxMap: Math.max(minMap, mainH - minSide),
    };
  }

  _applySplitHeight(height, persist) {
    const { mainH, minMap, maxMap } = this._splitLimits();
    if (!mainH || !this._app) return;
    const clamped = Math.min(Math.max(height, minMap), maxMap);
    this._app.style.setProperty("--dt-map-h", `${Math.round(clamped)}px`);
    if (persist) {
      try {
        localStorage.setItem(
          "geopulse:split",
          String(clamped / mainH)
        );
      } catch {
        /* private mode: alleen deze sessie */
      }
    }
  }

  _applyStoredSplit() {
    if (!this._app || !this._main) return;
    if (!this._isMobileLayout()) {
      this._app.style.removeProperty("--dt-map-h");
      return;
    }
    const { mainH, minMap, maxMap } = this._splitLimits();
    if (!mainH) return;

    let ratio = null;
    try {
      const stored = Number(localStorage.getItem("geopulse:split"));
      if (Number.isFinite(stored) && stored > 0) ratio = stored;
    } catch {
      /* geen opslag beschikbaar */
    }
    if (ratio == null) {
      // Same 40vh map as before, expressed as a share of the content area.
      ratio = (window.innerHeight * 0.4) / mainH;
    }
    const height = Math.min(Math.max(ratio * mainH, minMap), maxMap);
    this._applySplitHeight(height, false);
  }

  _finishSplitDrag() {
    if (!this._splitDrag) return;
    const height = this._mapWrap?.getBoundingClientRect().height;
    this._splitDrag = null;
    this._resizer?.classList.remove("dt-dragging");
    this._app?.classList.remove("dt-resizing");
    this._resizing = false;
    if (height) this._applySplitHeight(height, true);
    this._map?.invalidateSize({ pan: false });
    if (
      !this._userMovedMap &&
      this._data &&
      this._fittedDate === this._data.date
    ) {
      this._fitToData();
    }
  }

  _setupSplit() {
    const resizer = this._resizer;
    if (!resizer) return;

    resizer.addEventListener("pointerdown", (event) => {
      if (!this._isMobileLayout()) return;
      event.preventDefault();
      const mapHeight = this._mapWrap?.getBoundingClientRect().height || 0;
      this._splitDrag = {
        pointerId: event.pointerId,
        startY: event.clientY,
        startHeight: mapHeight,
      };
      this._resizing = true;
      try {
        resizer.setPointerCapture(event.pointerId);
      } catch {
        /* synthetische events hebben geen geldige pointer-id */
      }
      resizer.classList.add("dt-dragging");
      this._app?.classList.add("dt-resizing");
    });

    // Volg de vinger ook buiten de greep, zodat de drag nooit blijft hangen.
    const move = (event) => {
      if (!this._splitDrag || event.pointerId !== this._splitDrag.pointerId) {
        return;
      }
      if (event.pointerType === "mouse" && event.buttons === 0) {
        this._finishSplitDrag();
        return;
      }
      event.preventDefault();
      // Follow the finger: dragging down grows the map (and moves the pill
      // down), dragging up shrinks it.
      const delta = event.clientY - this._splitDrag.startY;
      this._applySplitHeight(this._splitDrag.startHeight + delta, false);
    };
    window.addEventListener("pointermove", move, { passive: false });

    const end = (event) => {
      if (!this._splitDrag || event.pointerId !== this._splitDrag.pointerId) {
        return;
      }
      try {
        if (resizer.hasPointerCapture(event.pointerId)) {
          resizer.releasePointerCapture(event.pointerId);
        }
      } catch {
        /* pointer is al losgelaten */
      }
      this._finishSplitDrag();
    };
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
    resizer.addEventListener("lostpointercapture", () => {
      this._finishSplitDrag();
    });

    resizer.addEventListener("keydown", (event) => {
      if (!this._isMobileLayout()) return;
      if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
      event.preventDefault();
      const current =
        this._mapWrap?.getBoundingClientRect().height ||
        this._splitLimits().minMap;
      this._applySplitHeight(
        current + (event.key === "ArrowUp" ? -24 : 24),
        true
      );
    });
  }

  _attachShadowListeners() {
    this._onShadowClick = (event) => this._handleClick(event);
    this.shadowRoot.addEventListener("click", this._onShadowClick);

    this._onShadowInput = (event) => {
      if (event.target.matches(".dt-combosearch input")) {
        this._edit.query = event.target.value;
        this._renderComboList();
        window.clearTimeout(this._comboSearchTimer);
        const query = this._edit.query.trim();
        if (query.length >= 2) {
          this._comboSearchTimer = window.setTimeout(
            () => this._searchComboOSM(query),
            350
          );
        }
      } else if (event.target.matches(".dt-splitrange")) {
        if (this._journeyEdit) {
          const index = Number(event.target.value);
          this._journeyEdit.splitIndex = index;
          const times = this._journeyEdit.route?.times || [];
          const label = this._modal?.querySelector(".dt-splittime");
          if (label) label.textContent = fmtTime(times[index]);
        }
      } else if (event.target.matches(".dt-placesinput")) {
        this._placesSearch.query = event.target.value;
        window.clearTimeout(this._placesSearch.timer);
        const query = this._placesSearch.query.trim();
        if (query.length >= 3) {
          this._placesSearch.timer = window.setTimeout(
            () => this._runPlacesSearch(),
            700
          );
        }
      }
    };
    this.shadowRoot.addEventListener("input", this._onShadowInput);

    this._onShadowChange = (event) => {
      if (event.target.matches(".dt-contactfile")) {
        const file = event.target.files?.[0];
        if (file) this._importContactsFile(file);
      } else if (event.target.matches(".dt-historyfile")) {
        const file = event.target.files?.[0];
        if (file) this._importHistoryFile(file);
      }
    };
    this.shadowRoot.addEventListener("change", this._onShadowChange);
  }

  async _importContactsFile(file) {
    const status = this._placesPop?.querySelector(".dt-contactstatus");
    const input = this._placesPop?.querySelector(".dt-contactfile");
    if (status) status.textContent = "Importeren…";
    try {
      const text = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("Lezen mislukt"));
        reader.readAsText(file);
      });
      if (!text.toUpperCase().includes("BEGIN:VCARD")) {
        throw new Error("Dit is geen .vcf-bestand");
      }
      const response = await this._hass.fetchWithAuth(
        "/api/geopulse/contacts",
        {
          method: "POST",
          headers: { "Content-Type": "text/vcard; charset=utf-8" },
          body: text,
        }
      );
      if (!response.ok) {
        throw new Error((await response.text()) || "Importeren mislukt");
      }
      const data = await response.json();
      const count = Number(data.addresses || 0);
      if (status) {
        status.textContent = `${count} adres${count === 1 ? "" : "sen"}`;
      }
      this._toast(
        `${count} adres${count === 1 ? "" : "sen"} uit het adresboek geïmporteerd`
      );
    } catch (err) {
      console.error("GeoPulse: contacten importeren mislukt", err);
      if (status) status.textContent = "Mislukt";
      this._toast(err?.message || "Contacten importeren mislukt", "error");
    } finally {
      if (input) input.value = "";
    }
  }

  async _importHistoryFile(file) {
    const status = this._placesPop?.querySelector(".dt-importstatus");
    const input = this._placesPop?.querySelector(".dt-historyfile");
    const entity = this._localEntity();
    if (!entity) {
      this._toast("Geen tracker gekoppeld voor deze kaart", "error");
      return;
    }
    const sizeMb = file.size / (1024 * 1024);
    if (status) {
      status.textContent = sizeMb >= 1
        ? `Bezig… (${Math.round(sizeMb)} MB)`
        : "Bezig…";
    }
    try {
      // HA caps a single request at 16 MB, so larger exports are uploaded in
      // pieces. The server appends them and imports the last chunk.
      const chunkSize = 8 * 1024 * 1024;
      const chunks = Math.max(1, Math.ceil(file.size / chunkSize));
      const randomId = () => {
        try {
          const value = crypto.randomUUID?.();
          if (value) return value.replaceAll("-", "");
        } catch {
          /* not a secure context */
        }
        let out = "";
        while (out.length < 32) {
          out += Math.floor(Math.random() * 16).toString(16);
        }
        return out.slice(0, 32);
      };
      const uploadId = chunks > 1 ? randomId() : "";
      let data = null;
      for (let index = 0; index < chunks; index += 1) {
        if (status && chunks > 1) {
          status.textContent = `Bezig… ${Math.round(
            (index / chunks) * 100
          )}% (${Math.round(sizeMb)} MB)`;
        }
        const blob = chunks === 1
          ? file
          : file.slice(index * chunkSize, (index + 1) * chunkSize);
        const response = await this._hass.fetchWithAuth(
          `/api/geopulse/import/${encodeURIComponent(entity)}` +
            `?name=${encodeURIComponent(file.name)}&size=${file.size}` +
            (chunks > 1
              ? `&upload_id=${uploadId}&chunk=${index}&chunks=${chunks}`
              : ""),
          {
            method: "POST",
            headers: {
              "Content-Type": file.type || "application/octet-stream",
            },
            body: blob,
          }
        );
        let body = null;
        try {
          body = await response.json();
        } catch {
          body = null;
        }
        if (!response.ok) {
          throw new Error(
            body?.error || `Importeren mislukt (${response.status})`
          );
        }
        if (index + 1 === chunks) data = body;
      }
      const count = Number(data?.imported || 0);
      if (status) {
        status.textContent = `${count.toLocaleString(numberLocale())} punten`;
      }
      this._toast(
        `${count.toLocaleString(numberLocale())} locatiepunten geïmporteerd` +
          (data?.places ? ` en ${data.places} plekken opgeslagen` : "")
      );
      this._places = null;
      this._placesPromise = null;
      await this._loadDay();
    } catch (err) {
      console.error("GeoPulse: historie importeren mislukt", err);
      if (status) status.textContent = "Mislukt";
      this._toast(err?.message || "Importeren mislukt", "error");
    } finally {
      if (input) input.value = "";
    }
  }

  _attachDocumentListeners() {
    if (!this._docClick) {
      this._docClick = (event) => {
        const path = event.composedPath();
        const hasClass = (name) =>
          path.some(
            (el) => el instanceof HTMLElement && el.classList?.contains(name)
          );
        if (this._calendarOpen) {
          if (!hasClass("dt-calpop") && !hasClass("dt-datebtn")) {
            this._closeCalendar();
          }
        }
        if (this._placesSearch?.open) {
          if (!hasClass("dt-placespop") && !hasClass("dt-placesbtn")) {
            this._closePlacesSearch();
          }
        }
      };
      document.addEventListener("click", this._docClick, true);
    }

    if (!this._keydown) {
      this._keydown = (event) => this._handleKeydown(event);
      document.addEventListener("keydown", this._keydown);
    }

    if (!this._resizeWin) {
      this._resizeWin = () => {
        window.clearTimeout(this._resizeWinTimer);
        this._resizeWinTimer = window.setTimeout(
          () => this._applyStoredSplit(),
          120
        );
      };
      window.addEventListener("resize", this._resizeWin, { passive: true });
    }

    if (!this._visibilityHandler) {
      this._visibilityHandler = () => {
        if (document.visibilityState === "hidden") {
          this._finishSplitDrag();
          return;
        }
        this._refreshMap();
      };
      document.addEventListener("visibilitychange", this._visibilityHandler);
      window.addEventListener("focus", this._visibilityHandler);
      window.addEventListener("pageshow", this._visibilityHandler);
    }
  }

  _detachDocumentListeners() {
    if (this._docClick) {
      document.removeEventListener("click", this._docClick, true);
      this._docClick = null;
    }
    if (this._keydown) {
      document.removeEventListener("keydown", this._keydown);
      this._keydown = null;
    }
    if (this._resizeWin) {
      window.removeEventListener("resize", this._resizeWin);
      window.clearTimeout(this._resizeWinTimer);
      this._resizeWin = null;
    }
    if (this._visibilityHandler) {
      document.removeEventListener(
        "visibilitychange",
        this._visibilityHandler
      );
      window.removeEventListener("focus", this._visibilityHandler);
      window.removeEventListener("pageshow", this._visibilityHandler);
      this._visibilityHandler = null;
    }
    window.clearTimeout(this._refreshMapTimer);
    window.clearTimeout(this._mapResizeTimer);
  }

  _handleKeydown(event) {
    const target = event.composedPath?.()[0];
    if (
      event.key === "Enter" &&
      target?.classList?.contains("dt-placesinput")
    ) {
      event.preventDefault();
      this._runPlacesSearch();
      return;
    }

    if (event.key === "Escape") {
      if (this._placesSearch?.open) {
        this._closePlacesSearch();
        event.preventDefault();
        return;
      }
      if (this._modal && !this._modal.hidden) {
        this._closeModal();
        event.preventDefault();
        return;
      }
      if (this._calendarOpen) {
        this._closeCalendar();
        event.preventDefault();
        return;
      }
      if (this._mapMaximized) {
        this._setMapMaximized(false);
        event.preventDefault();
        return;
      }
      if (this._edit?.comboOpen) {
        this._edit.comboOpen = false;
        this._renderComboState();
        event.preventDefault();
      }
      return;
    }

    if (this._modal && !this._modal.hidden) return;
    if (this._calendarOpen) return;
    if (isTextInput(event.composedPath()[0])) return;

    if (event.key === "ArrowLeft") {
      event.preventDefault();
      this._shiftDay(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      this._shiftDay(1);
    }
  }

  /* ---------------------------------------------------------------- */
  /* Day loading                                                       */
  /* ---------------------------------------------------------------- */

  _isFamilySource() {
    return this._config.source === "ha_history";
  }

  _isLocalSource() {
    return this._config.source !== "ha_history";
  }

  _localEntity() {
    return (
      this._config.entity_id ||
      this._config.route_entity ||
      this._config.tracker_entity ||
      null
    );
  }

  async _loadDay() {
    if (!this._hass) return;
    const token = ++this._loadToken;
    this._loading = true;
    this._error = null;
    this._updateLoadingState();

    try {
      const request = this._isFamilySource()
        ? {
            type: "geopulse/ha_day",
            date: this._date,
            entity_id: this._config.entity_id,
          }
        : {
            type: "geopulse/local_day",
            date: this._date,
            entity_id: this._localEntity(),
          };
      const data = await this._hass.callWS(request);
      if (token !== this._loadToken) return;
      this._data = data;
      this._renderDay();
      this._renderMap();
    } catch (err) {
      if (token !== this._loadToken) return;
      console.error("GeoPulse: dag laden mislukt", err);
      this._error =
        err?.message || "Kon de gegevens van deze dag niet ophalen.";
      this._data = null;
      this._renderDay();
      this._renderMap();
    } finally {
      if (token === this._loadToken) {
        this._loading = false;
        this._updateLoadingState();
      }
    }
  }

  _updateLoadingState() {
    if (this._loadingBar) this._loadingBar.hidden = !this._loading;
    if (this._mapSpinner) this._mapSpinner.hidden = !this._loading;
    if (this._list) this._list.classList.toggle("dt-stale", this._loading);
    if (this._app) this._app.classList.toggle("dt-loading", this._loading);
  }

  _shiftDay(delta) {
    const next = addDays(this._date, delta);
    if (next > todayISO()) return;
    this._setDate(next);
  }

  _setDate(iso) {
    if (iso > todayISO()) return;
    if (iso === this._date && this._data) {
      this._closeCalendar();
      return;
    }
    this._date = iso;
    this._selectedKey = null;
    this._fitMap = true;
    this._closeCalendar();
    this._updateHeader();
    this._loadDay();
  }

  _setMapMaximized(value) {
    if (this._mapMaximized === value) return;

    // Keep the exact centre and zoom while the map container changes size.
    // Leaflet's default invalidateSize() pans the map, which can push the
    // day's route off-screen when the map grows to the full viewport.
    const center = this._map?.getCenter();
    const zoom = this._map?.getZoom();

    this._mapMaximized = value;
    this._app?.classList.toggle("dt-map-max", value);
    if (this._mapMaxBtn) {
      this._mapMaxBtn.innerHTML = `<ha-icon icon="${
        value ? "mdi:arrow-collapse" : "mdi:arrow-expand"
      }"></ha-icon>`;
      this._mapMaxBtn.title = value
        ? "Kaart verkleinen"
        : "Kaart maximaliseren";
      this._mapMaxBtn.setAttribute(
        "aria-label",
        value ? "Kaart verkleinen" : "Kaart maximaliseren"
      );
    }
    window.setTimeout(() => {
      if (!this._map) return;
      this._map.invalidateSize({ pan: false });
      if (center && zoom !== undefined) {
        this._map.setView(center, zoom, { animate: false });
      }
    }, 120);
  }

  _updateHeader() {
    const iso = this._date;
    const label = headerLabel(iso);
    if (this._dateLabel) this._dateLabel.textContent = label;
    if (this._mapDayLabel) this._mapDayLabel.textContent = label;
    if (this._dayTitle) this._dayTitle.textContent = fmtDateLong(iso);

    const isToday = iso === todayISO();
    if (this._nextBtn) this._nextBtn.disabled = isToday;
    if (this._todayBtn) {
      this._todayBtn.hidden = isToday;
      this._todayBtn.disabled = isToday;
    }
  }

  /* ---------------------------------------------------------------- */
  /* Calendar                                                          */
  /* ---------------------------------------------------------------- */

  _toggleCalendar() {
    if (this._calendarOpen) {
      this._closeCalendar();
    } else {
      this._openCalendar();
    }
  }

  _openCalendar() {
    const date = parseISO(this._date);
    this._calYear = date.getFullYear();
    this._calMonth = date.getMonth();
    this._calendarOpen = true;
    this._calendarPop.hidden = false;
    this._dateBtn.setAttribute("aria-expanded", "true");
    this._positionCalendar();
    this._renderCalendar();
    this._loadMonth(this._calYear, this._calMonth);
  }

  _closeCalendar() {
    if (!this._calendarOpen) return;
    this._calendarOpen = false;
    this._calendarPop.hidden = true;
    this._dateBtn.setAttribute("aria-expanded", "false");
  }

  _positionCalendar() {
    if (!this._dateBtn || !this._calendarPop) return;
    const rect = this._dateBtn.getBoundingClientRect();
    const width = Math.min(340, window.innerWidth - 24);
    this._calendarPop.style.width = `${width}px`;
    const left = Math.min(
      Math.max(12, rect.left + rect.width / 2 - width / 2),
      window.innerWidth - width - 12
    );
    const top = Math.min(rect.bottom + 8, window.innerHeight - 120);
    this._calendarPop.style.left = `${left}px`;
    this._calendarPop.style.top = `${top}px`;
  }

  async _loadMonth(year, month) {
    const token = ++this._monthToken;
    this._monthDays = null;
    this._renderCalendar();
    try {
      const request = this._isFamilySource()
        ? {
            type: "geopulse/ha_month",
            year,
            month: month + 1,
            entity_id: this._config.entity_id,
          }
        : {
            type: "geopulse/local_month",
            year,
            month: month + 1,
            entity_id: this._localEntity(),
          };
      const result = await this._hass.callWS(request);
      if (token !== this._monthToken) return;
      this._monthDays = result.days || {};
      this._renderCalendar();
    } catch (err) {
      console.warn("GeoPulse: maandgegevens laden mislukt", err);
    }
  }

  /* ---------------------------------------------------------------- */
  /* Plaatsen zoeken (POI)                                             */
  /* ---------------------------------------------------------------- */

  _togglePlacesSearch() {
    const state = this._placesSearch;
    state.open = !state.open;
    if (!state.open) {
      this._placesPop.hidden = true;
      return;
    }
    this._renderPlacesSearch();
    this._placesPop.hidden = false;
    window.setTimeout(() => {
      this._placesPop.querySelector(".dt-placesinput")?.focus();
    }, 30);
  }

  _closePlacesSearch() {
    if (!this._placesSearch?.open) return;
    this._placesSearch.open = false;
    this._placesPop.hidden = true;
  }

  _renderPlacesSearch() {
    if (!this._placesPop) return;
    const state = this._placesSearch;
    const results = state.results || [];
    const active = this.shadowRoot?.activeElement;
    const hadFocus = Boolean(
      active && active.classList?.contains("dt-placesinput")
    );
    const selection = hadFocus
      ? [active.selectionStart, active.selectionEnd]
      : null;

    const body = state.loading
      ? `<div class="dt-placesloading"><span class="dt-btnspinner"></span>Zoeken…</div>`
      : state.error
        ? `<div class="dt-placesempty">${esc(state.error)}</div>`
        : results.length
          ? results
              .map((item, index) => {
                const distance =
                  item.visit_count > 0
                    ? `${item.visit_count} bezoek${item.visit_count === 1 ? "" : "en"}`
                    : "nog niet bezocht";
                const lastDay = item.last
                  ? String(item.last).slice(0, 10)
                  : null;
                const period = lastDay
                  ? `Laatst: ${fmtDateShort(lastDay)}${
                      fmtTime(item.last) ? " " + fmtTime(item.last) : ""
                    }`
                  : "Geen bezoek gevonden binnen " + Math.round(item.radius) + " m";
                return `
                  <div class="dt-placeresult">
                    <button class="dt-placeresult-main" data-action="place-open" data-index="${index}">
                      <span class="dt-placeresult-name">${esc(item.name)}</span>
                      <span class="dt-placeresult-sub">${esc(item.address || "")}</span>
                      <span class="dt-placeresult-meta">
                        <span class="dt-placecount">${esc(distance)}</span>
                        <span>${esc(period)}</span>
                      </span>
                    </button>
                    <button class="dt-iconbtn dt-placesave" data-action="place-save" data-index="${index}"
                      title="${item.saved ? "Al bewaard" : "Bewaar als plek"}" aria-label="Bewaar als plek"
                      ${item.saved ? "disabled" : ""}>
                      <ha-icon icon="${item.saved ? "mdi:bookmark-check" : "mdi:bookmark-plus-outline"}"></ha-icon>
                    </button>
                  </div>`;
              })
              .join("")
          : state.query
            ? `<div class="dt-placesempty">Geen plekken gevonden.</div>`
            : `<div class="dt-placesempty">Zoek een plek om te zien of en hoe vaak je er geweest bent.</div>`;

    this._placesPop.innerHTML = `
      <div class="dt-placeshead">
        <div class="dt-placestitle">
          <ha-icon icon="mdi:map-search-outline"></ha-icon>
          <span>Plaatsen</span>
        </div>
        <button class="dt-iconbtn" data-action="places-close" aria-label="Sluiten">
          <ha-icon icon="mdi:close"></ha-icon>
        </button>
      </div>
      <div class="dt-placesrow">
        <input class="dt-input dt-placesinput" type="search" autocomplete="off"
          placeholder="Bijv. Apollopad of een winkel…" value="${esc(state.query || "")}">
        <button class="dt-btn dt-primary" data-action="places-run" ${
          state.loading ? "disabled" : ""
        }>
          <ha-icon icon="mdi:magnify"></ha-icon>Zoek
        </button>
      </div>
      <div class="dt-placeshint">Bezoeken worden geteld binnen ${Math.round(
        results[0]?.radius || 75
      )} m van de plek, over de hele opgeslagen historie.</div>
      <div class="dt-placeslist">${body}</div>
      <div class="dt-placesexport">
        <span class="dt-exportlabel"><ha-icon icon="mdi:download-outline"></ha-icon>Exporteren</span>
        <select class="dt-input dt-exportrange">
          <option value="month">Deze maand</option>
          <option value="year" selected>Dit jaar</option>
          <option value="last">Vorig jaar</option>
        </select>
        <button class="dt-btn" data-action="export" data-format="gpx">GPX</button>
        <button class="dt-btn" data-action="export" data-format="geojson">GeoJSON</button>
      </div>
      <div class="dt-placescontacts">
        <span class="dt-exportlabel"><ha-icon icon="mdi:account-box-outline"></ha-icon>Adresboek</span>
        <input class="dt-contactfile" type="file"
          accept=".vcf,text/vcard,text/x-vcard" hidden>
        <button class="dt-btn" data-action="contacts-import">Importeer .vcf</button>
        <span class="dt-contactstatus"></span>
      </div>
      ${
        !this._isFamilySource() && this._isLocalSource() && this._localEntity()
          ? `<div class="dt-placesimport">
        <span class="dt-exportlabel"><ha-icon icon="mdi:database-import-outline"></ha-icon>Historie</span>
        <input class="dt-historyfile" type="file"
          accept=".gpx,.geojson,.json,.zip,application/gpx+xml,application/geo+json,application/json,application/zip" hidden>
        <button class="dt-btn" data-action="history-import">Importeer bestand</button>
        <span class="dt-importstatus"></span>
      </div>`
          : ""
      }
    `;

    if (hadFocus) {
      const input = this._placesPop.querySelector(".dt-placesinput");
      if (input) {
        input.focus();
        if (selection) {
          try {
            input.setSelectionRange(selection[0], selection[1]);
          } catch {
            /* input type may not support selection */
          }
        }
      }
    }
  }

  async _runPlacesSearch() {
    const input = this._placesPop.querySelector(".dt-placesinput");
    const query = (input?.value || this._placesSearch.query || "").trim();
    if (!query) return;
    if (!this._localEntity()) {
      this._placesSearch.error =
        "Geen tracker gekoppeld. Stel entity_id of route_entity in.";
      this._renderPlacesSearch();
      return;
    }
    this._placesSearch.query = query;
    this._placesSearch.loading = true;
    this._placesSearch.error = null;
    this._renderPlacesSearch();

    try {
      const result = await Promise.race([
        this._hass.callWS({
          type: "geopulse/places_search",
          query,
          entity_id: this._localEntity(),
          radius: 75,
        }),
        new Promise((_, reject) =>
          window.setTimeout(
            () => reject(new Error("Zoeken duurde te lang. Probeer het opnieuw.")),
            15000
          )
        ),
      ]);
      this._placesSearch.results = result.results || [];
      this._placesSearch.loading = false;
      this._renderPlacesSearch();
    } catch (err) {
      console.error("GeoPulse: plaatsen zoeken mislukt", err);
      this._placesSearch.loading = false;
      this._placesSearch.error =
        err?.message || "Zoeken mislukt. Probeer het opnieuw.";
      this._renderPlacesSearch();
    }
  }

  _openPlaceResult(index) {
    const item = (this._placesSearch.results || [])[index];
    if (!item) return;
    this._closePlacesSearch();
    if (item.last) {
      this._setDate(String(item.last).slice(0, 10));
    } else {
      this._toast("Geen bezoek gevonden binnen de zoekstraal", "error");
    }
  }

  async _savePlaceResult(index) {    const item = (this._placesSearch.results || [])[index];
    if (!item) return;
    try {
      await this._hass.callWS({
        type: "geopulse/local_save_place",
        name: item.name,
        lat: Number(item.lat),
        lon: Number(item.lon),
        radius: 75,
        address: item.address || null,
        osm_type: item.osm_type || null,
        osm_id: item.osm_id != null ? String(item.osm_id) : null,
        place_id: item.id || null,
      });
      item.saved = true;
      this._places = null;
      this._toast("Plek bewaard");
      this._renderPlacesSearch();
    } catch (err) {
      console.error("GeoPulse: plek bewaren mislukt", err);
      this._toast(err?.message || "Bewaren mislukt", "error");
    }
  }

  async _exportArchive(format) {
    if (!this._localEntity()) {
      this._toast("Geen tracker gekoppeld", "error");
      return;
    }
    const select = this._placesPop.querySelector(".dt-exportrange");
    const range = select?.value || "year";
    const now = new Date();
    let start;
    let end;
    if (range === "month") {
      start = `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-01`;
      end = todayISO();
    } else if (range === "last") {
      start = `${now.getFullYear() - 1}-01-01`;
      end = `${now.getFullYear() - 1}-12-31`;
    } else {
      start = `${now.getFullYear()}-01-01`;
      end = todayISO();
    }

    try {
      const entity = encodeURIComponent(this._localEntity());
      const url = `/api/geopulse/export/${entity}/${format}?start=${encodeURIComponent(
        start
      )}&end=${encodeURIComponent(end)}`;
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.rel = "noopener";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      this._toast("Export gestart — het bestand wordt gedownload");
    } catch (err) {
      console.error("GeoPulse: exporteren mislukt", err);
      this._toast(err?.message || "Exporteren mislukt", "error");
    }
  }

  _renderCalendar() {    const year = this._calYear;
    const month = this._calMonth;
    const first = new Date(year, month, 1);
    const offset = (first.getDay() + 6) % 7;
    const dayCount = new Date(year, month + 1, 0).getDate();
    const today = todayISO();

    const cells = [];
    for (let i = 0; i < offset; i += 1) {
      cells.push('<div class="dt-cal-day dt-cal-empty"></div>');
    }
    for (let day = 1; day <= dayCount; day += 1) {
      const iso = `${year}-${pad2(month + 1)}-${pad2(day)}`;
      const classes = ["dt-cal-day"];
      if (iso === this._date) classes.push("dt-cal-selected");
      if (iso === today) classes.push("dt-cal-today");
      if (this._monthDays && this._monthDays[iso]) classes.push("dt-cal-hasdata");
      const future = iso > today;
      const dot =
        this._monthDays && this._monthDays[iso]
          ? '<span class="dt-cal-dot"></span>'
          : "";
      cells.push(
        `<button class="${classes.join(" ")}" data-cal-day="${iso}" ${
          future ? "disabled" : ""
        }><span>${day}</span>${dot}</button>`
      );
    }

    this._calendarPop.innerHTML = `
      <div class="dt-cal-head">
        <button class="dt-iconbtn" data-action="cal-prev" aria-label="Vorige maand">
          <ha-icon icon="mdi:chevron-left"></ha-icon>
        </button>
        <div class="dt-cal-title">${capitalize(months()[month])} ${year}</div>
        <button class="dt-iconbtn" data-action="cal-next" aria-label="Volgende maand">
          <ha-icon icon="mdi:chevron-right"></ha-icon>
        </button>
      </div>
      <div class="dt-cal-weekdays">
        ${weekdaysMin().map((day) => `<div>${day}</div>`).join("")}
      </div>
      <div class="dt-cal-grid">${cells.join("")}</div>
      <div class="dt-cal-foot">
        <span class="dt-cal-hint"><i class="dt-cal-dot"></i> dag met gegevens</span>
        <button class="dt-cal-todaybtn" data-action="cal-today">Vandaag</button>
      </div>
    `;
  }

  _shiftCalendarMonth(delta) {
    const date = new Date(this._calYear, this._calMonth + delta, 1);
    this._calYear = date.getFullYear();
    this._calMonth = date.getMonth();
    this._monthDays = null;
    this._renderCalendar();
    this._loadMonth(this._calYear, this._calMonth);
  }

  /* ---------------------------------------------------------------- */
  /* Rendering: sidebar                                                */
  /* ---------------------------------------------------------------- */

  _renderDay() {
    this._updateHeader();
    if (!this._data) {
      if (this._error) {
        this._summary.innerHTML = "";
        this._list.innerHTML = `
          <div class="dt-errorcard">
            <ha-icon icon="mdi:cloud-alert-outline"></ha-icon>
            <div class="dt-error-title">Gegevens niet beschikbaar</div>
            <div class="dt-error-text">${esc(this._error)}</div>
            <button class="dt-btn" data-action="retry">Opnieuw proberen</button>
          </div>`;
      } else if (!this._loading) {
        this._summary.innerHTML = "";
        this._list.innerHTML = this._emptyHTML();
      } else {
        this._summary.innerHTML = "";
        this._list.innerHTML = this._skeletonHTML();
      }
      this._updateLoadingState();
      return;
    }

    const data = this._data;
    this._summary.innerHTML = this._summaryHTML(data.summary);

    if (!data.entries.length) {
      this._list.innerHTML = this._emptyHTML();
    } else {
      this._list.innerHTML = data.entries
        .map((entry, index, all) =>
          entry.type === "visit"
            ? this._visitHTML(entry, index, all)
            : this._journeyHTML(entry, index, all)
        )
        .join("");
    }

    if (this._selectedKey) {
      const selected = this._list.querySelector(
        `.dt-entry[data-key="${CSS.escape(this._selectedKey)}"]`
      );
      selected?.classList.add("dt-selected");
    }

    this._updateLoadingState();
  }

  _summaryHTML(summary) {
    if (!summary) return "";
    const chips = [];

    const chip = (icon, text, color, subtle = false) => `
      <span class="dt-chip ${subtle ? "dt-chip-subtle" : ""}"${
        color ? ` style="--chip-color:${color}"` : ""
      }>
        <ha-icon icon="${icon}"></ha-icon><span>${esc(text)}</span>
      </span>`;

    if (summary.distance > 0) {
      chips.push(
        chip(
          "mdi:map-marker-distance",
          fmtDistance(summary.distance, summary.unit),
          "",
          false
        )
      );
    }
    if (summary.places > 0) {
      chips.push(
        chip(
          "mdi:map-marker-multiple",
          `${summary.places} ${summary.places === 1 ? "plek" : "plekken"}`
        )
      );
    }
    if (summary.moving_minutes > 0) {
      chips.push(
        chip(
          "mdi:timer-outline",
          `${fmtMinutes(summary.moving_minutes)} onderweg`
        )
      );
    }
    for (const mode of (summary.modes || []).slice(0, 4)) {
      const info = modeInfo(mode.mode);
      chips.push(
        `<span class="dt-chip dt-chip-mode" style="--chip-color:${info.color}">
          <i class="dt-mode-dot"></i><span>${esc(modeShort(mode.mode))}</span>
          <b>${esc(fmtDistance(mode.distance, summary.unit))}</b>
        </span>`
      );
    }

    return chips.join("");
  }

  _visitHTML(entry, index, all) {
    const suggested = entry.status === "suggested";
    const confirmed = entry.status === "confirmed";
    const classes = [
      "dt-entry",
      "dt-entry-visit",
      suggested ? "dt-suggested" : "",
      confirmed ? "dt-confirmed" : "",
      index === all.length - 1 ? "dt-last" : "",
    ]
      .filter(Boolean)
      .join(" ");

    const confidence = confidenceLabel(entry.confidence) || "";
    const badges = [];
    if (suggested) {
      badges.push('<span class="dt-badge dt-badge-suggested">Suggestie</span>');
      if (confidence) {
        badges.push(`<span class="dt-badge">${esc(confidence)}</span>`);
      }
    } else if (confirmed) {
      badges.push(
        '<span class="dt-badge dt-badge-confirmed"><ha-icon icon="mdi:check-circle"></ha-icon>Bevestigd</span>'
      );
    }
    if (entry.merged) {
      badges.push(
        '<span class="dt-badge dt-badge-merged"><ha-icon icon="mdi:link-variant"></ha-icon>Samengevoegd</span>'
      );
    }

    const continued = entry.continued
      ? '<span class="dt-badge dt-badge-continued">vanaf vorige dag</span>'
      : "";

    const timeRange = `${fmtTime(entry.start)} – ${fmtTime(entry.end)}`;
    const meta = [
      timeRange,
      fmtMinutes(entry.duration_minutes),
      entry.subtitle,
    ]
      .filter(Boolean)
      .join(" · ");

    const actions = [];
    if (entry.editable !== false) {
      if (suggested) {
        actions.push(`
          <button class="dt-btn dt-primary" data-action="confirm-visit">
            <ha-icon icon="mdi:check"></ha-icon>Ja
          </button>`);
      }
      actions.push(`
        <button class="dt-btn ${suggested ? "" : "dt-btn-quiet"}" data-action="edit-visit">
          <ha-icon icon="mdi:pencil-outline"></ha-icon>Bewerken
        </button>`);
    }

    const dotClass = entry.is_home ? "dt-dot-home" : "";

    return `
      <div class="${classes}" data-key="${esc(entry.key)}" data-kind="visit" data-visit-id="${entry.visit_id}">
        <div class="dt-rail">
          <div class="dt-dot dt-dot-visit ${suggested ? "dt-dot-suggested" : ""} ${dotClass}">${
            entry.is_home ? HOUSE_SVG : PIN_SVG
          }</div>
        </div>
        <div class="dt-card">
          <div class="dt-entry-head">
            <div class="dt-entry-title">${esc(entry.name)}</div>
          </div>
          <div class="dt-entry-meta">${esc(meta)}</div>
          ${
            badges.length || continued
              ? `<div class="dt-badges">${badges.join("")}${continued}</div>`
              : ""
          }
          <div class="dt-actions">${actions.join("")}</div>
        </div>
      </div>`;
  }

  _journeyHTML(entry, index, all) {
    const info = modeInfo(entry.mode);
    const classes = [
      "dt-entry",
      "dt-entry-journey",
      index === all.length - 1 ? "dt-last" : "",
    ]
      .filter(Boolean)
      .join(" ");

    const stats = [
      fmtDistance(entry.distance, entry.distance_unit),
      fmtSeconds(entry.duration_seconds),
    ].join(" · ");

    const badges = [];
    if (entry.continued) {
      badges.push(
        '<span class="dt-badge dt-badge-continued">vanaf vorige dag</span>'
      );
    }
    if (entry.merged) {
      badges.push(
        '<span class="dt-badge dt-badge-merged"><ha-icon icon="mdi:link-variant"></ha-icon>Samengevoegd</span>'
      );
    }

    const actions = [];
    if (entry.editable !== false) {
      actions.push(`
        <button class="dt-btn dt-btn-quiet" data-action="edit-journey">
          <ha-icon icon="mdi:pencil-outline"></ha-icon>Aanpassen
        </button>`);
      const previous = index > 0 ? all[index - 1] : null;
      if (
        previous &&
        previous.type === "journey" &&
        previous.track_id !== entry.track_id
      ) {
        actions.push(`
          <button class="dt-btn dt-btn-quiet" data-action="merge-journey">
            <ha-icon icon="mdi:link-variant"></ha-icon>Samenvoegen
          </button>`);
      }
      if (entry.merged) {
        actions.push(`
          <button class="dt-btn dt-btn-quiet" data-action="unmerge-journey">
            <ha-icon icon="mdi:link-variant-off"></ha-icon>Splitsen
          </button>`);
      }
    }

    const note = entry.note
      ? `<div class="dt-entry-note"><ha-icon icon="mdi:note-text-outline"></ha-icon><span>${esc(
          entry.note
        )}</span></div>`
      : "";

    const trackIds = (entry.track_ids || [entry.track_id]).join(",");
    const modeBreakdown =
      entry.modes && entry.modes.length > 1
        ? `<div class="dt-entry-modes">${entry.modes
            .filter((mode) => mode.distance > 0)
            .map((mode) => {
              const chipInfo = modeInfo(mode.mode);
              return `<span class="dt-modechip"><i style="background:${
                chipInfo.color
              }"></i>${esc(modeLabel(mode.mode))} ${esc(
                fmtDistance(mode.distance, entry.distance_unit)
              )}</span>`;
            })
            .join("")}</div>`
        : "";

    return `
      <div class="${classes}" data-key="${esc(entry.key)}" data-kind="journey"
        data-track-id="${entry.track_id}" data-track-ids="${esc(trackIds)}">
        <div class="dt-rail">
          <div class="dt-dot dt-dot-mode" style="--mode-color:${info.color}">${info.emoji}</div>
        </div>
        <div class="dt-card dt-card-journey">
          <div class="dt-entry-head">
            <div class="dt-entry-title">${esc(modeLabel(entry.mode))}</div>
            ${badges.join("")}
          </div>
          <div class="dt-entry-meta">${esc(stats)}</div>
          ${modeBreakdown}
          <div class="dt-entry-times">${esc(fmtTime(entry.start))} – ${esc(
      fmtTime(entry.end)
    )}</div>
          ${note}
          ${
            actions.length
              ? `<div class="dt-actions dt-journey-actions">${actions.join("")}</div>`
              : ""
          }
        </div>
      </div>`;
  }

  _emptyHTML() {
    return `
      <div class="dt-empty">
        <div class="dt-empty-icon"><ha-icon icon="mdi:map-marker-off-outline"></ha-icon></div>
        <div class="dt-empty-title">Geen beweging op deze dag</div>
        <div class="dt-empty-text">Kies een andere dag of controleer of de tracker locaties doorgeeft.</div>
      </div>`;
  }

  _skeletonHTML() {
    return `
      <div class="dt-skeleton">
        ${Array.from({ length: 4 })
          .map(
            () => `
          <div class="dt-skel-row">
            <div class="dt-skel-dot"></div>
            <div class="dt-skel-lines">
              <div class="dt-skel-line w70"></div>
              <div class="dt-skel-line w45"></div>
            </div>
          </div>`
          )
          .join("")}
      </div>`;
  }

  /* ---------------------------------------------------------------- */
  /* Rendering: map                                                    */
  /* ---------------------------------------------------------------- */

  _loadLeaflet() {
    if (this._L) {
      this._ensureLeafletCss();
      return Promise.resolve(this._L);
    }
    if (window.__geopulseLeaflet) {
      this._L = window.__geopulseLeaflet;
      this._ensureLeafletCss();
      return Promise.resolve(this._L);
    }
    if (window.__geopulseLeafletPromise) {
      return window.__geopulseLeafletPromise.then((L) => {
        this._L = L;
        this._ensureLeafletCss();
        return L;
      });
    }
    if (this._leafletPromise) return this._leafletPromise;

    this._leafletPromise = new Promise((resolve, reject) => {
      this._ensureLeafletCss();
      // Home Assistant's own map card bundles another Leaflet. Keep ours in a
      // private global and restore window.L, so the two never mix versions
      // (mixed versions broke clipping and the drag handler).
      const previous = window.L;
      const script = document.createElement("script");
      script.src = "/geopulse_static/leaflet.js";
      script.async = true;
      script.onload = () => {
        const ours = window.L;
        window.__geopulseLeaflet = ours;
        if (previous) {
          window.L = previous;
        } else {
          try {
            delete window.L;
          } catch {
            window.L = undefined;
          }
        }
        resolve(ours);
      };
      script.onerror = () => {
        if (previous) window.L = previous;
        reject(new Error("Leaflet kon niet worden geladen"));
      };
      document.head.appendChild(script);
    });
    window.__geopulseLeafletPromise = this._leafletPromise;
    return this._leafletPromise;
  }

  _ensureLeafletCss() {
    if (this.shadowRoot.querySelector("link[data-leaflet-css]")) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/geopulse_static/leaflet.css";
    link.dataset.leafletCss = "true";
    this.shadowRoot.prepend(link);
  }

  async _initMap() {
    if (this._map) return this._map;
    if (this._mapInitPromise) return this._mapInitPromise;
    if (!this._mapEl) return null;

    this._mapInitPromise = (async () => {
      const L = await this._loadLeaflet();
      if (this._map) return this._map;

      // The app can mount the card while the view is still hidden.  Leaflet
      // then sizes the map to 0x0 and never paints tiles.  Wait until the
      // container has a real size (or the browser becomes visible again).
      await this._waitForMapSize();

      const home = this._homeCoordinates();
      this._map = L.map(this._mapEl, {
        zoomControl: true,
        attributionControl: true,
        // SVG keeps lines crisp during (fractional) pinch zoom and avoids
        // canvas clipping artefacts on Android WebViews.
        preferCanvas: false,
        zoomSnap: 0.25,
        minZoom: 3,
        worldCopyJump: true,
        // Leaflet's drag handler pans with one finger and the mouse. Its
        // touchZoom handler is disabled below because it left a phantom
        // second touch on Android and turned pans into zooms.
        dragging: true,
        touchZoom: false,
        scrollWheelZoom: true,
      }).setView(home || [52.1, 5.3], home ? 13 : 8);

      this._applyTileLayer(L);

      this._routeLayer = L.layerGroup().addTo(this._map);
      this._visitLayer = L.layerGroup().addTo(this._map);

      this._userMovedMap = false;
      const markMoved = () => {
        this._userMovedMap = true;
      };
      this._mapEl.addEventListener("pointerdown", markMoved, {
        passive: true,
      });
      // Android WebViews do not always emit a usable pointerdown before the
      // touch handlers, so also mark touch and wheel interaction.
      this._mapEl.addEventListener("touchstart", markMoved, {
        passive: true,
      });
      this._mapEl.addEventListener("wheel", markMoved, { passive: true });
      this._map.on("dragstart", markMoved);
      this._setupMapGestures(L);

      if (this._resizeObserver) this._resizeObserver.disconnect();
      this._resizeObserver = new ResizeObserver(() => {
        if (!this._map) return;
        // During a splitter drag the map must follow the finger immediately.
        if (this._resizing) {
          this._map.invalidateSize({ pan: false });
          return;
        }
        // Debounce changes caused by the mobile URL bar or page scroll;
        // resizing the map mid-pan makes Leaflet jump or zoom.
        window.clearTimeout(this._mapResizeTimer);
        this._mapResizeTimer = window.setTimeout(() => {
          if (!this._map) return;
          this._map.invalidateSize({ pan: false });
          if (
            !this._userMovedMap &&
            this._data &&
            this._fittedDate === this._data.date
          ) {
            this._fitToData();
          }
        }, 140);
      });
      this._resizeObserver.observe(this._mapEl);

      window.setTimeout(() => this._map?.invalidateSize({ pan: false }), 80);
      window.setTimeout(() => this._map?.invalidateSize({ pan: false }), 450);
      this._renderMap();
      return this._map;
    })();
    this._mapInitPromise = this._mapInitPromise.catch((err) => {
      console.error("GeoPulse: kaart initialiseren mislukt", err);
      this._mapInitPromise = null;
      this._leafletPromise = null;
      return null;
    });

    return this._mapInitPromise;
  }

  _waitForMapSize(timeout = 5000) {
    return new Promise((resolve) => {
      const started = Date.now();
      const check = () => {
        if (!this._mapEl) {
          resolve();
          return;
        }
        if (this._mapEl.clientWidth >= 2 && this._mapEl.clientHeight >= 2) {
          resolve();
          return;
        }
        if (Date.now() - started >= timeout) {
          resolve();
          return;
        }
        window.requestAnimationFrame(check);
      };
      check();
    });
  }

  _refreshMap() {
    window.clearTimeout(this._refreshMapTimer);
    this._refreshMapTimer = window.setTimeout(() => {
      if (!this._map) {
        this._initMap().then((map) => {
          if (!map) return;
          map.invalidateSize({ pan: false });
          if (this._data) this._renderMap();
        });
        return;
      }
      this._map.invalidateSize({ pan: false });
      if (this._data) this._renderMap();
    }, 250);
  }

  _mapStyle() {
    if (this._config.tile_url) return "custom";
    try {
      const saved = localStorage.getItem("geopulse:layer");
      if (saved === "night") return "night";
    } catch {
      /* private mode */
    }
    return "day";
  }

  _applyTileLayer(L) {
    if (!this._map) return;
    if (this._tileLayer) {
      this._map.removeLayer(this._tileLayer);
      this._tileLayer = null;
    }

    const custom = Boolean(this._config.tile_url);
    const style = this._mapStyle();
    const day = {
      url: "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
      subdomains: "abc",
      maxZoom: 20,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-bijdragers, Tiles: HOT',
      fallback:
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
      fallbackAttribution:
        'Tiles &copy; <a href="https://www.esri.com/">Esri</a> &mdash; Esri, HERE, Garmin',
      fallbackNativeZoom: null,
    };

    const config = custom
      ? {
          url: this._config.tile_url,
          subdomains: "abc",
          maxZoom: Number(this._config.tile_max_zoom) || 19,
          attribution: this._config.tile_attribution || "",
          fallback: day.fallback,
          fallbackAttribution: day.fallbackAttribution,
          fallbackNativeZoom: null,
        }
      : day;

    if (this._mapEl) {
      this._mapEl.classList.toggle("dt-night", style === "night");
    }

    const options = {
      maxZoom: config.maxZoom,
      attribution: config.attribution,
      keepBuffer: 4,
    };
    if (config.subdomains) options.subdomains = config.subdomains;
    const layer = L.tileLayer(config.url, options).addTo(this._map);
    this._tileLayer = layer;
    this._tileFallback = false;

    if (!custom) {
      let errors = 0;
      let replaced = false;
      layer.on("tileerror", () => {
        errors += 1;
        if (replaced || errors < 4) return;
        replaced = true;
        this._tileFallback = true;
        this._map.removeLayer(layer);
        const fallbackOptions = {
          maxZoom: config.maxZoom,
          attribution: config.fallbackAttribution,
        };
        if (config.fallbackNativeZoom) {
          fallbackOptions.maxNativeZoom = config.fallbackNativeZoom;
        }
        this._tileLayer = L.tileLayer(
          config.fallback, fallbackOptions
        ).addTo(this._map);
      });
    }
    this._updateMapStyleButton();
  }

  _updateMapStyleButton() {
    const button = this._mapStyleBtn;
    if (!button) return;
    const night = this._mapStyle() === "night";
    button.innerHTML = `<ha-icon icon="${
      night ? "mdi:weather-sunny" : "mdi:weather-night"
    }"></ha-icon>`;
    const label = night ? "Dagkaart" : "Nachtkaart";
    button.title = label;
    button.setAttribute("aria-label", label);
  }

  _toggleMapStyle() {
    if (this._config.tile_url) {
      this._toast("Kaartlaag is via tile_url ingesteld", "error");
      return;
    }
    const next = this._mapStyle() === "night" ? "day" : "night";
    try {
      localStorage.setItem("geopulse:layer", next);
    } catch {
      /* private mode */
    }
    if (this._mapEl) {
      this._mapEl.classList.toggle("dt-night", next === "night");
    }
    this._updateMapStyleButton();
    this._toast(next === "night" ? "Nachtkaart" : "Dagkaart");
  }

  _setupMapGestures(L) {
    if (!this._mapEl || this._gestureEl === this._mapEl) return;
    this._gestureEl = this._mapEl;
    this._pinchBound = true;
    const el = this._mapEl;
    let pinch = null;

    const distance = (first, second) =>
      Math.hypot(
        first.clientX - second.clientX,
        first.clientY - second.clientY
      );

    const midpoint = (first, second) => {
      const rect = el.getBoundingClientRect();
      return L.point(
        (first.clientX + second.clientX) / 2 - rect.left,
        (first.clientY + second.clientY) / 2 - rect.top
      );
    };

    // One-finger panning is Leaflet's own (well-tested) drag handler.
    // Only pinch needs a custom handler because touchZoom is disabled: its
    // phantom second touch caused one-finger pans to zoom on Android.
    const start = (event) => {
      if (!event.touches || event.touches.length !== 2) {
        pinch = null;
        return;
      }
      event.preventDefault();
      this._userMovedMap = true;
      pinch = {
        distance: Math.max(1, distance(event.touches[0], event.touches[1])),
        zoom: this._map.getZoom(),
      };
      if (this._map.dragging.enabled()) this._map.dragging.disable();
    };

    const move = (event) => {
      if (!pinch || !event.touches || event.touches.length !== 2) return;
      event.preventDefault();
      const spread = distance(event.touches[0], event.touches[1]);
      if (!spread) return;
      const zoom = pinch.zoom + Math.log2(spread / pinch.distance);
      this._map.setZoomAround(
        this._map.containerPointToLatLng(
          midpoint(event.touches[0], event.touches[1])
        ),
        zoom,
        { animate: false }
      );
    };

    const end = (event) => {
      if (event.touches && event.touches.length >= 2) return;
      const wasPinching = Boolean(pinch);
      pinch = null;
      if (!this._map) return;
      if (!this._map.dragging.enabled()) this._map.dragging.enable();
      if (!wasPinching) return;
      const zoom = this._map.getZoom();
      if (Math.abs(zoom - Math.round(zoom)) > 0.01) {
        this._map.setZoom(Math.round(zoom), { animate: true });
      }
    };

    el.addEventListener("touchstart", start, { passive: false });
    el.addEventListener("touchmove", move, { passive: false });
    el.addEventListener("touchend", end);
    el.addEventListener("touchcancel", end);
    el.addEventListener("gesturestart", (event) => event.preventDefault());

    // Fallback for WebViews where Leaflet's drag handler does not receive the
    // gesture. It only pans when Leaflet's own handler did not move the map,
    // so a working Leaflet drag is never applied twice.
    let fallback = null;
    const activePointers = new Set();
    el.addEventListener("pointerdown", (event) => {
      activePointers.add(event.pointerId);
      if (activePointers.size > 1) {
        fallback = null;
        return;
      }
      if (event.pointerType === "mouse" && event.button !== 0) return;
      fallback = {
        x: event.clientX,
        y: event.clientY,
        lastX: event.clientX,
        lastY: event.clientY,
        center: this._map.getCenter(),
        moved: false,
      };
    });
    el.addEventListener("pointermove", (event) => {
      if (!fallback || activePointers.size > 1) return;
      const dxTotal = event.clientX - fallback.x;
      const dyTotal = event.clientY - fallback.y;
      if (!fallback.moved && Math.hypot(dxTotal, dyTotal) < 8) return;
      const center = this._map.getCenter();
      const leafletMoved =
        Math.abs(center.lat - fallback.center.lat) > 1e-9 ||
        Math.abs(center.lng - fallback.center.lng) > 1e-9;
      if (leafletMoved) {
        fallback.lastX = event.clientX;
        fallback.lastY = event.clientY;
        fallback.moved = true;
        return;
      }
      const dx = event.clientX - fallback.lastX;
      const dy = event.clientY - fallback.lastY;
      if (!dx && !dy) return;
      fallback.moved = true;
      this._userMovedMap = true;
      this._map.panBy([-dx, -dy], { animate: false });
      fallback.lastX = event.clientX;
      fallback.lastY = event.clientY;
    });
    const endFallback = (event) => {
      if (event && event.pointerId !== undefined) {
        activePointers.delete(event.pointerId);
      }
      fallback = null;
    };
    el.addEventListener("pointerup", endFallback);
    el.addEventListener("pointercancel", endFallback);
    el.addEventListener("pointerleave", endFallback);
  }

  _homeCoordinates() {
    const home = this._hass?.states?.["zone.home"];
    if (!home) return null;
    const lat = Number(home.attributes?.latitude);
    const lng = Number(home.attributes?.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    return [lat, lng];
  }

  async _renderMap() {
    let L = this._L;
    if (!L) {
      await this._initMap();
      L = this._L;
      if (!L) return;
    }
    if (!this._map) {
      await this._initMap();
      if (!this._map) return;
    }

    this._routeLayer.clearLayers();
    this._visitLayer.clearLayers();
    this._routeVisuals = {};
    this._visitVisuals = {};

    const data = this._data;
    if (!data) {
      this._mapEmpty.hidden = this._loading || Boolean(this._error);
      this._legend.hidden = true;
      if (this._fitMap) {
        this._fitMap = false;
        const home = this._homeCoordinates();
        if (home) this._map.setView(home, 13, { animate: false });
      }
      return;
    }

    this._mapEmpty.hidden = data.entries.length > 0;

    const entriesByTrack = {};
    const entriesByKey = {};
    const entriesByVisit = {};
    for (const entry of data.entries) {
      if (entry.type === "journey") {
        entriesByKey[entry.key] = entry;
        for (const trackId of entry.track_ids || [entry.track_id]) {
          entriesByTrack[trackId] = entry;
        }
        for (const routeKey of entry.route_keys || []) {
          entriesByKey[routeKey] = entry;
        }
      } else {
        entriesByVisit[entry.visit_id] = entry;
      }
    }

    // Faint raw-GPS trail for slow movement between visits.
    for (const trail of data.background || []) {
      if (!Array.isArray(trail) || trail.length < 2) continue;
      L.polyline(trail, {
        color: "#94a3b8",
        weight: 3,
        opacity: 0.45,
        lineCap: "round",
        lineJoin: "round",
        interactive: false,
        smoothFactor: 1,
      }).addTo(this._routeLayer);
    }

    for (const route of data.routes || []) {
      const routeKey = route.key || String(route.track_id);
      const entry =
        entriesByKey[route.entry_key] || entriesByTrack[route.track_id];
      const select = () => {
        if (entry) this._selectEntry(entry.key, true);
      };
      // One journey can contain several modes (e.g. walking to the car and
      // then driving). Draw every segment in its own colour.
      const pieces =
        route.segments && route.segments.length
          ? route.segments
          : [
              {
                mode: route.mode,
                color: route.color,
                coordinates: route.coordinates,
              },
            ];
      const visuals = {
        entryKey: route.entry_key || (entry && entry.key),
        casings: [],
        lines: [],
      };

      for (const piece of pieces) {
        const coords = piece.coordinates;
        if (!coords || coords.length < 2) continue;
        const info = modeInfo(piece.mode || route.mode);
        const color = piece.color || info.color;

        const casing = L.polyline(coords, {
          color: "#ffffff",
          weight: 10,
          opacity: 0.9,
          lineCap: "round",
          lineJoin: "round",
          interactive: false,
          smoothFactor: 1,
        }).addTo(this._routeLayer);

        const line = L.polyline(coords, {
          color,
          weight: 6,
          opacity: 0.92,
          lineCap: "round",
          lineJoin: "round",
          smoothFactor: 1,
        }).addTo(this._routeLayer);

        line.on("click", select);
        casing.on("click", select);
        visuals.casings.push(casing);
        visuals.lines.push(line);

        this._addDirectionArrows(coords, color);

        const middle = coords[Math.floor(coords.length / 2)];
        if (middle) {
          const icon = L.divIcon({
            className: "dt-mode-marker",
            html: `<div class="dt-mode-marker-inner" style="--mode-color:${color}">${info.emoji}</div>`,
            iconSize: [30, 30],
            iconAnchor: [15, 15],
          });
          L.marker(middle, {
            icon,
            interactive: false,
            keyboard: false,
            zIndexOffset: -200,
          }).addTo(this._routeLayer);
        }
      }

      if (visuals.lines.length) {
        this._routeVisuals[routeKey] = visuals;
      }
    }

    const coordinateCounts = new Map();
    for (const entry of data.entries) {
      if (entry.type !== "visit") continue;
      if (entry.latitude == null || entry.longitude == null) continue;

      // Visits at (almost) the same spot would otherwise hide each other.
      const coordKey = `${entry.latitude.toFixed(4)},${entry.longitude.toFixed(4)}`;
      const seen = coordinateCounts.get(coordKey) || 0;
      coordinateCounts.set(coordKey, seen + 1);
      const angle = seen * 2.399963;
      const radius =
        entry.is_home || seen === 0 ? 0 : 0.00007 * seen;
      const latitude = entry.latitude + Math.cos(angle) * radius;
      const longitude = entry.longitude + Math.sin(angle) * radius;

      const status = entry.status === "confirmed" ? "confirmed" : "suggested";
      const icon = L.divIcon({
        className: "dt-visit-marker",
        html: `<div class="dt-pin ${
          entry.is_home ? "dt-pin-home" : `dt-pin-${status}`
        }">${entry.is_home ? HOUSE_SVG : PIN_SVG}</div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -16],
      });

      const marker = L.marker([latitude, longitude], {
        icon,
        zIndexOffset: 500,
        title: entry.name,
      }).addTo(this._visitLayer);

      marker.bindPopup(this._popupHTML(entry), {
        closeButton: false,
        offset: [0, -2],
        className: "dt-popup",
      });

      marker.on("click", () => this._selectEntry(entry.key, true));
      this._visitVisuals[entry.visit_id] = marker;
    }

    this._updateLegend();
    this._updateSelectionStyles();

    // A new day's data must always be framed, even when the map was created
    // before the first day arrived (in that case _fitMap was already cleared
    // while showing the empty state at the home location).
    if (this._fitMap || this._fittedDate !== data.date) {
      this._fitMap = false;
      this._fittedDate = data.date;
      this._fitToData();
    }
  }

  _addDirectionArrows(coords, color) {
    const L = this._L;
    if (!L || !coords || coords.length < 2) return;
    // Keep the map readable: one to three arrows per route part, away from
    // the mode marker in the middle.
    const count = Math.min(3, Math.max(1, Math.floor(coords.length / 14)));
    const fractions =
      count === 1
        ? [0.68]
        : count === 2
          ? [0.3, 0.7]
          : [0.2, 0.42, 0.72];

    for (const fraction of fractions) {
      const index = Math.min(
        coords.length - 2,
        Math.max(0, Math.round((coords.length - 1) * fraction))
      );
      const start = coords[index];
      const end = coords[index + 1];
      if (!start || !end) continue;
      if (start[0] === end[0] && start[1] === end[1]) continue;
      const angle = this._bearing(start, end);
      const icon = L.divIcon({
        className: "dt-arrow-marker",
        html: `<div class="dt-arrow" style="transform:rotate(${angle}deg)"><svg viewBox="0 0 12 14" aria-hidden="true"><path d="M6 1 L11 12 L6 9.2 L1 12 Z" fill="rgba(255,255,255,0.97)" stroke="rgba(15,23,42,0.35)" stroke-width="0.7"/></svg></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7],
      });
      L.marker(start, {
        icon,
        interactive: false,
        keyboard: false,
        zIndexOffset: -150,
      }).addTo(this._routeLayer);
    }
  }

  _bearing(start, end) {
    const lat1 = (start[0] * Math.PI) / 180;
    const lat2 = (end[0] * Math.PI) / 180;
    const deltaLng = ((end[1] - start[1]) * Math.PI) / 180;
    const y = Math.sin(deltaLng) * Math.cos(lat2);
    const x =
      Math.cos(lat1) * Math.sin(lat2) -
      Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLng);
    return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  }

  _popupHTML(entry) {
    const meta = `${fmtTime(entry.start)} – ${fmtTime(entry.end)}`;
    return `
      <div class="dt-pop">
        <div class="dt-pop-title">${esc(entry.name)}</div>
        <div class="dt-pop-sub">${esc(meta)}${
      entry.subtitle ? ` · ${esc(entry.subtitle)}` : ""
    }</div>
      </div>`;
  }

  _updateLegend() {
    const modes = [];
    for (const entry of this._data?.entries || []) {
      if (entry.type !== "journey") continue;
      const entryModes =
        entry.modes && entry.modes.length
          ? entry.modes.map((mode) => mode.mode)
          : [entry.mode];
      for (const mode of entryModes) {
        if (!modes.includes(mode)) modes.push(mode);
      }
    }
    if (!modes.length) {
      this._legend.hidden = true;
      return;
    }
    this._legend.hidden = false;
    this._legend.innerHTML = modes
      .map((mode) => {
        const info = modeInfo(mode);
        return `<span class="dt-legend-item"><i style="background:${info.color}"></i>${esc(
          modeShort(mode)
        )}</span>`;
      })
      .join("");
  }

  _fitToData() {
    if (!this._map || !this._L) return;
    const L = this._L;
    // Refresh Leaflet's cached container size first; it can be stale while
    // the card is still settling into Home Assistant's layout.
    this._map.invalidateSize({ pan: false });
    this._userMovedMap = false;
    const bounds = this._data?.bounds;
    if (bounds && bounds.length === 2) {
      const latLngBounds = L.latLngBounds(
        [bounds[0][0], bounds[0][1]],
        [bounds[1][0], bounds[1][1]]
      );
      if (latLngBounds.isValid()) {
        try {
          this._map.fitBounds(latLngBounds, {
            padding: [42, 42],
            maxZoom: 16,
            animate: false,
          });
          return;
        } catch (err) {
          console.warn("GeoPulse: fitBounds mislukt", err);
        }
      }
    }
    const home = this._homeCoordinates();
    if (home) this._map.setView(home, 13, { animate: false });
  }

  _selectEntry(key, scroll) {
    this._selectedKey = key;
    this._updateSelectionClasses();
    this._updateSelectionStyles();

    const entry = this._data?.entries.find((item) => item.key === key);
    if (!entry || !this._map) return;

    // The user chose a specific visit or journey: keep that view when the
    // card is resized (maximize, rotation) instead of re-framing the day.
    this._userMovedMap = true;

    if (entry.type === "visit") {
      if (entry.latitude != null && entry.longitude != null) {
        const marker = this._visitVisuals[entry.visit_id];
        this._map.flyTo(
          [entry.latitude, entry.longitude],
          Math.max(this._map.getZoom(), 16),
          { duration: 0.45 }
        );
        marker?.openPopup();
      }
    } else {
      const routeKeys = new Set();
      for (const key of entry.route_keys || []) routeKeys.add(String(key));
      if (entry.key) routeKeys.add(String(entry.key));
      if (entry.track_id) routeKeys.add(String(entry.track_id));
      for (const trackId of entry.track_ids || []) {
        routeKeys.add(String(trackId));
        routeKeys.add(`journey-${trackId}`);
      }
      const visuals = [...routeKeys]
        .map((routeKey) => this._routeVisuals[routeKey])
        .filter(Boolean);
      if (visuals.length) {
        const bounds = this._L.latLngBounds([]);
        for (const visual of visuals) {
          for (const line of visual.lines || []) bounds.extend(line.getBounds());
        }
        if (bounds.isValid()) {
          this._map.flyToBounds(bounds, {
            padding: [52, 52],
            maxZoom: 17,
            duration: 0.45,
          });
        }
      }
    }

    if (scroll) {
      const el = this._list?.querySelector(
        `.dt-entry[data-key="${CSS.escape(key)}"]`
      );
      el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  _updateSelectionClasses() {
    if (!this._list) return;
    for (const el of this._list.querySelectorAll(".dt-entry")) {
      el.classList.toggle(
        "dt-selected",
        el.dataset.key === this._selectedKey
      );
    }
  }

  _updateSelectionStyles() {
    if (!this._L) return;
    const entry = this._data?.entries.find(
      (item) => item.key === this._selectedKey
    );
    const selectedKeys = new Set();
    if (entry && entry.type === "journey") {
      selectedKeys.add(entry.key);
      for (const routeKey of entry.route_keys || []) selectedKeys.add(routeKey);
      for (const trackId of entry.track_ids || [entry.track_id]) {
        selectedKeys.add(`journey-${trackId}`);
      }
    }

    for (const [routeKey, visual] of Object.entries(this._routeVisuals)) {
      const selected =
        selectedKeys.has(routeKey) || visual.entryKey === this._selectedKey;
      for (const line of visual.lines || []) {
        line.setStyle({
          weight: selected ? 9 : 6,
          opacity: selected ? 1 : 0.92,
        });
      }
      for (const casing of visual.casings || []) {
        casing.setStyle({ weight: selected ? 13 : 10 });
      }
    }
  }

  /* ---------------------------------------------------------------- */
  /* Visit actions                                                     */
  /* ---------------------------------------------------------------- */

  async _confirmVisit(button, visitId) {
    if (!this._hass) return;
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="dt-btnspinner"></span>Bezig…';
    try {
      await this._hass.callWS({
        type: "geopulse/local_update_visit",
        date: this._date,
        entity_id: this._localEntity(),
        visit_id: String(visitId),
        status: "confirmed",
      });
      this._toast("Bezoek bevestigd");
      await this._loadDay();
    } catch (err) {
      console.error("GeoPulse: bevestigen mislukt", err);
      this._toast(err?.message || "Bevestigen mislukt", "error");
      button.disabled = false;
      button.innerHTML = original;
    }
  }

  _findVisit(visitId) {
    return this._data?.entries.find(
      (entry) =>
        entry.type === "visit" &&
        String(entry.visit_id) === String(visitId)
    );
  }

  async _openEdit(visitId) {
    const visit = this._findVisit(visitId);
    if (!visit) return;

    this._edit = {
      token: Symbol("edit"),
      visit,
      selected: visit.place_id
        ? {
            id: String(visit.place_id),
            name: visit.place_name || visit.name,
            latitude: visit.latitude,
            longitude: visit.longitude,
            visits: 0,
            current: true,
          }
        : null,
      name: visit.editable_name || "",
      query: "",
      options: [],
      placesLoading: true,
      osmLoading: false,
      comboOpen: false,
      saving: false,
    };

    this._modal.hidden = false;
    this._renderEditDialog();
    this._modal.querySelector(".dt-input")?.focus();

    await this._ensurePlaces();

    if (!this._edit || this._edit.visit.visit_id !== visit.visit_id) return;

    const nearby = await this._fetchNearbyPlaces(visit);
    if (!this._edit || this._edit.visit.visit_id !== visit.visit_id) return;

    const options = this._mergeNearbyOptions(
      this._buildPlaceOptions(visit),
      nearby
    );
    this._edit.options = options;
    this._edit.placesLoading = false;

    if (!this._edit.selected) {
      const byName = options.find(
        (place) =>
          place.name &&
          visit.name &&
          String(place.name).toLowerCase() ===
            String(visit.name).toLowerCase()
      );
      this._edit.selected =
        byName ||
        options.find(
          (place) => place.id === String(visit.place_id)
        ) ||
        null;
      if (!this._edit.selected && visit.suggested_places?.length) {
        const suggested = visit.suggested_places[0];
        this._edit.selected =
          options.find(
            (place) => place.id === String(suggested.id)
          ) || null;
      }
    }

    this._renderComboState();
    this._renderComboList();
    this._loadNearbyContacts(this._edit);
  }

  async _fetchNearbyPlaces(visit) {
    if (!this._hass || !this._isLocalSource()) return [];
    const latitude = Number(visit.latitude);
    const longitude = Number(visit.longitude);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return [];
    try {
      const result = await this._hass.callWS({
        type: "geopulse/places_near",
        entity_id: this._localEntity(),
        lat: latitude,
        lon: longitude,
        radius: NEARBY_PLACE_RADIUS_METERS,
        limit: 80,
      });
      return result.results || [];
    } catch (err) {
      console.warn("GeoPulse: plekken in de buurt laden mislukt", err);
      return [];
    }
  }

  _mergeNearbyOptions(options, nearby) {
    const visit = this._edit?.visit;
    const lat = Number(visit?.latitude);
    const lng = Number(visit?.longitude);
    const hasPoint = Number.isFinite(lat) && Number.isFinite(lng);
    const byId = new Map(options.map((place) => [String(place.id), place]));

    for (const place of nearby || []) {
      const id = String(place.id);
      if (byId.has(id)) continue;
      byId.set(id, {
        id,
        name: place.name,
        address: place.address || "",
        latitude: place.lat,
        longitude: place.lon,
        source: place.source,
        nearby: true,
        visits: 0,
        distance: Number.isFinite(Number(place.distance))
          ? Number(place.distance)
          : hasPoint &&
              Number.isFinite(Number(place.lat)) &&
              Number.isFinite(Number(place.lon))
            ? this._distanceMeters(
                lat,
                lng,
                Number(place.lat),
                Number(place.lon)
              )
            : null,
      });
    }

    const merged = [...byId.values()];
    merged.sort((a, b) => {
      if (a.id === this._edit?.selected?.id) return -1;
      if (b.id === this._edit?.selected?.id) return 1;
      if (a.distance != null && b.distance != null) {
        return a.distance - b.distance;
      }
      if (a.distance != null) return -1;
      if (b.distance != null) return 1;
      return (b.visits || 0) - (a.visits || 0);
    });
    return merged;
  }

  async _loadNearbyContacts(edit) {
    if (!edit || !this._hass) return;
    const visit = edit.visit;
    const latitude = Number(visit.latitude);
    const longitude = Number(visit.longitude);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return;
    try {
      const result = await this._hass.callWS({
        type: "geopulse/contacts_near",
        lat: latitude,
        lon: longitude,
        radius: 150,
      });
      if (this._edit !== edit) return;
      const existing = new Set(
        (edit.options || []).map((option) => String(option.id))
      );
      let added = false;
      for (const contact of result.contacts || []) {
        const id = `contact:${contact.id}`;
        if (existing.has(id)) continue;
        existing.add(id);
        edit.options.unshift({
          id,
          name: contact.name,
          address: contact.address,
          latitude: contact.lat,
          longitude: contact.lon,
          contact: true,
          visits: 0,
          distance: contact.distance,
        });
        added = true;
      }
      if (added) this._renderComboList();
    } catch (err) {
      console.warn("GeoPulse: contacten laden mislukt", err);
    }
  }

  _buildPlaceOptions(visit) {
    const byId = new Map();
    const idOf = (value) => (value == null ? null : String(value));

    if (visit.place_id) {
      byId.set(idOf(visit.place_id), {
        id: idOf(visit.place_id),
        name: visit.place_name || visit.name,
        latitude: visit.latitude,
        longitude: visit.longitude,
        visits: 0,
        current: true,
      });
    }

    for (const suggested of visit.suggested_places || []) {
      if (suggested.id == null) continue;
      const id = idOf(suggested.id);
      if (!byId.has(id)) {
        byId.set(id, {
          id,
          name: dutchPlaceName(suggested.name) || `Plek ${id}`,
          latitude: suggested.lat,
          longitude: suggested.lng,
          visits: 0,
        });
      }
    }

    for (const place of this._places || []) {
      const id = idOf(place.id);
      if (!id) continue;
      if (!byId.has(id)) {
        byId.set(id, { ...place, id, name: dutchPlaceName(place.name) });
      } else {
        byId.get(id).visits = place.visits || 0;
      }
    }

    const options = [...byId.values()];
    const lat = Number(visit.latitude);
    const lng = Number(visit.longitude);
    const hasPoint = Number.isFinite(lat) && Number.isFinite(lng);

    for (const place of options) {
      if (
        hasPoint &&
        Number.isFinite(Number(place.latitude)) &&
        Number.isFinite(Number(place.longitude))
      ) {
        place.distance = this._distanceMeters(
          lat,
          lng,
          Number(place.latitude),
          Number(place.longitude)
        );
      } else {
        place.distance = null;
      }
    }

    options.sort((a, b) => {
      if (a.id === this._edit?.selected?.id) return -1;
      if (b.id === this._edit?.selected?.id) return 1;
      if (a.distance != null && b.distance != null) {
        return a.distance - b.distance;
      }
      if (a.distance != null) return -1;
      if (b.distance != null) return 1;
      return (b.visits || 0) - (a.visits || 0);
    });

    return options;
  }

  _distanceMeters(lat1, lng1, lat2, lng2) {
    const rad = Math.PI / 180;
    const dLat = (lat2 - lat1) * rad;
    const dLng = (lng2 - lng1) * rad;
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(lat1 * rad) *
        Math.cos(lat2 * rad) *
        Math.sin(dLng / 2) ** 2;
    return 6_371_000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  async _searchComboOSM(query) {
    const edit = this._edit;
    if (!edit || !this._hass) return;
    const visit = edit.visit;
    const token = edit.token;
    edit.options = (edit.options || []).filter((option) => !option.searchResult);
    edit.osmLoading = true;
    this._renderComboList();
    try {
      const result = await Promise.race([
        this._hass.callWS({
          type: "geopulse/places_lookup",
          query,
          lat: Number(visit.latitude),
          lon: Number(visit.longitude),
          limit: 8,
        }),
        new Promise((resolve) =>
          window.setTimeout(() => resolve({ results: [] }), 10000)
        ),
      ]);
      if (this._edit !== edit || edit.token !== token) return;
      if ((edit.query || "").trim() !== query) {
        edit.osmLoading = false;
        return;
      }
      const existing = new Set(
        (edit.options || []).map((option) => String(option.id))
      );
      const lat = Number(visit.latitude);
      const lng = Number(visit.longitude);
      for (const item of result.results || []) {
        const id = String(item.id || `osm:${item.name}`);
        if (existing.has(id)) continue;
        existing.add(id);
        edit.options.push({
          id,
          name: item.name,
          latitude: item.lat,
          longitude: item.lon,
          address: item.address || "",
          osm: item.source === "osm",
          source: item.source,
          saved: false,
          searchResult: true,
          visits: 0,
          distance:
            Number.isFinite(lat) &&
            Number.isFinite(lng) &&
            Number.isFinite(Number(item.lat))
              ? this._distanceMeters(
                  lat,
                  lng,
                  Number(item.lat),
                  Number(item.lon)
                )
              : null,
        });
      }
      edit.osmLoading = false;
      this._renderComboList();
    } catch (err) {
      console.warn("GeoPulse: OSM-zoeken in dropdown mislukt", err);
      edit.osmLoading = false;
      this._renderComboList();
    }
  }

  async _ensureSelectedPlaceSaved() {
    const place = this._edit?.selected;
    if (!place || place.contact) return null;
    const isOsm = Boolean(
      place.osm ||
        place.source === "osm" ||
        (place.id && String(place.id).startsWith("osm:"))
    );
    if (!isOsm || place.saved) return place.id;
    let osmType = place.osm_type || null;
    let osmId = place.osm_id != null ? String(place.osm_id) : null;
    if ((!osmType || !osmId) && place.id) {
      const parts = String(place.id).split(":");
      if (parts.length >= 3 && parts[0] === "osm") {
        osmType = osmType || parts[1];
        osmId = osmId || parts[2];
      }
    }
    const result = await this._hass.callWS({
      type: "geopulse/local_save_place",
      name: place.name,
      lat: Number(place.latitude),
      lon: Number(place.longitude),
      radius: 75,
      address: place.address || null,
      osm_type: osmType,
      osm_id: osmId,
      place_id: place.id || null,
    });
    place.saved = true;
    if (result?.place?.id) place.id = String(result.place.id);
    this._places = null;
    return place.id;
  }

  async _ensurePlaces() {
    if (this._places) return this._places;
    if (this._placesPromise) return this._placesPromise;
    if (!this._hass) return [];

    this._placesPromise = this._hass
      .callWS({ type: "geopulse/local_places" })
      .then((result) => {
        const places = result.places || [];
        this._places = places.map((place) => ({
          id: String(place.id),
          name: place.name,
          latitude: place.lat,
          longitude: place.lon,
          visits: 0,
        }));
        return this._places;
      })
      .catch((err) => {
        console.error("GeoPulse: plekken laden mislukt", err);
        this._places = [];
        return [];
      })
      .finally(() => {
        this._placesPromise = null;
      });

    return this._placesPromise;
  }

  _renderEditDialog() {
    const edit = this._edit;
    if (!edit) return;
    const visit = edit.visit;
    const timeRange = `${fmtTime(visit.start)} – ${fmtTime(visit.end)}`;
    const meta = [timeRange, fmtMinutes(visit.duration_minutes)]
      .filter(Boolean)
      .join(" · ");

    this._modal.innerHTML = `
      <div class="dt-modal-backdrop" data-action="close-modal"></div>
      <div class="dt-dialog" role="dialog" aria-modal="true" aria-labelledby="dt-dlg-title">
        <div class="dt-dlg-head">
          <div>
            <h2 id="dt-dlg-title">Bezoek aanpassen</h2>
            <div class="dt-dlg-sub">${esc(meta)}</div>
          </div>
          <button class="dt-iconbtn" data-action="close-modal" aria-label="Sluiten">
            <ha-icon icon="mdi:close"></ha-icon>
          </button>
        </div>

        <div class="dt-dlg-body">
          <label class="dt-label">Plek (POI)</label>
          <div class="dt-combo">
            <button class="dt-combobtn" data-action="toggle-combo" ${
              edit.placesLoading ? "disabled" : ""
            }>
              <span class="dt-combotext">${
                edit.placesLoading ? "Plekken laden…" : "Kies een plek"
              }</span>
              <ha-icon icon="mdi:chevron-down"></ha-icon>
            </button>
            <div class="dt-compopop" hidden>
              <div class="dt-combosearch">
                <ha-icon icon="mdi:magnify"></ha-icon>
                <input type="search" placeholder="Zoek op naam…" autocomplete="off">
              </div>
              <div class="dt-combolist"></div>
            </div>
          </div>

          <label class="dt-label" for="dt-custom-name">Naam (optioneel)</label>
          <input id="dt-custom-name" class="dt-input" type="text" maxlength="120"
            value="${esc(edit.name)}" placeholder="Eigen naam voor dit bezoek">
          <div class="dt-hint">Laat leeg om de naam van de gekozen plek te gebruiken.</div>
        </div>

        <div class="dt-dlg-actions">
          <button class="dt-btn dt-danger-ghost" data-action="decline-visit">${
            this._isLocalSource() ? "Verwijderen" : "Afwijzen"
          }</button>
          <div class="dt-spacer"></div>
          <button class="dt-btn" data-action="close-modal">Annuleren</button>
          <button class="dt-btn dt-primary" data-action="save-visit">
            <ha-icon icon="mdi:check"></ha-icon>Bevestigen
          </button>
        </div>
      </div>`;

    this._renderComboState();
    this._renderComboList();
  }

  _renderComboState() {
    if (!this._edit || !this._modal) return;
    const edit = this._edit;
    const button = this._modal.querySelector(".dt-combobtn");
    const pop = this._modal.querySelector(".dt-compopop");
    const text = this._modal.querySelector(".dt-combotext");
    if (!button || !pop || !text) return;

    if (edit.placesLoading) {
      text.textContent = "Plekken laden…";
      button.disabled = true;
    } else {
      text.textContent = edit.selected
        ? edit.selected.name
        : "Kies een plek";
      button.disabled = false;
    }
    pop.hidden = !edit.comboOpen;
    button.setAttribute("aria-expanded", edit.comboOpen ? "true" : "false");
  }

  _renderComboList() {
    if (!this._edit || !this._modal) return;
    const edit = this._edit;
    const list = this._modal.querySelector(".dt-combolist");
    if (!list) return;

    if (edit.placesLoading) {
      list.innerHTML = '<div class="dt-comboloading"><span class="dt-btnspinner"></span>Plekken laden…</div>';
      return;
    }

    const query = normalizeSearchText(edit.query || "");
    const all = edit.options || [];
    const withinSearchRadius = (place) =>
      place.distance == null ||
      place.distance <= MAX_PLACE_SEARCH_METERS;

    const matches = (place) => {
      const words = query.split(/\s+/).filter(Boolean);
      if (!words.length) return false;
      const haystack = normalizeSearchText(
        `${place.name} ${place.address || ""}`
      );
      return words.every((word) => haystack.includes(word));
    };

    let options;
    if (query) {
      // Live/index results are already matched by the backend; nearby
      // contacts and POIs still have to match the typed text themselves.
      const searched = all.filter(
        (place) => place.searchResult && withinSearchRadius(place)
      );
      const localMatches = all.filter(
        (place) =>
          (place.contact || place.nearby) &&
          matches(place) &&
          withinSearchRadius(place)
      );
      const saved = all.filter(
        (place) =>
          !place.searchResult &&
          !place.contact &&
          !place.nearby &&
          matches(place) &&
          withinSearchRadius(place)
      );
      options = [...searched, ...localMatches, ...saved];
    } else {
      // Before typing, show everything found near the visit: POIs from the
      // local index, contacts and any search result still in the list.
      options = all.filter(
        (place) => place.searchResult || place.contact || place.nearby
      );
    }

    const seen = new Set();
    options = options
      .filter((place) => {
        const id = String(place.id);
        if (seen.has(id)) return false;
        seen.add(id);
        return true;
      })
      .sort(
        (a, b) =>
          (a.distance == null ? 1e12 : a.distance) -
          (b.distance == null ? 1e12 : b.distance)
      )
      .slice(0, 120);

    if (!options.length) {
      const text = edit.osmLoading
        ? "Zoeken…"
        : query
          ? `Geen plekken gevonden binnen ${MAX_PLACE_SEARCH_METERS} m`
          : `Geen bekende plekken binnen ${NEARBY_PLACE_RADIUS_METERS} m`;
      const hint = query
        ? '<div class="dt-combohint">Niet gevonden? Gebruik het veld Naam (optioneel) om dit bezoek zelf een naam te geven.</div>'
        : "";
      list.innerHTML = `<div class="dt-comboempty">${esc(text)}</div>${hint}`;
      return;
    }

    const loading = edit.osmLoading
      ? '<div class="dt-comboloading"><span class="dt-btnspinner"></span>Zoeken…</div>'
      : "";

    list.innerHTML =
      loading +
      options
        .map((place) => {
          const selected =
            edit.selected &&
            String(edit.selected.id) === String(place.id);
          const meta = [];
          if (place.contact) meta.push("contact");
          else if (place.nearby) meta.push("POI");
          if (place.distance != null) {
            meta.push(fmtDistance(place.distance / 1000, "km"));
          } else if (place.visits) {
            meta.push(`${place.visits} bezoek${place.visits === 1 ? "" : "en"}`);
          }
          if (place.current) meta.push("huidig");
          return `
            <button class="dt-place-option ${selected ? "dt-place-selected" : ""}"
              data-place-id="${place.id}">
              <span class="dt-place-name">${esc(dutchPlaceName(place.name))}</span>
              <span class="dt-place-meta">${
                selected
                  ? '<ha-icon icon="mdi:check"></ha-icon>'
                  : esc(meta.join(" · "))
              }</span>
            </button>`;
        })
        .join("");
  }

  _setSelectedPlace(placeId) {
    if (!this._edit) return;
    const place = (this._edit.options || []).find(
      (option) => String(option.id) === String(placeId)
    );
    if (!place) return;
    this._edit.selected = place;
    if (place.name) {
      this._edit.name = place.name;
      const input = this._modal.querySelector("#dt-custom-name");
      if (input) input.value = place.name;
    }
    this._edit.comboOpen = false;
    this._edit.query = "";
    this._renderComboState();
    this._renderComboList();
  }

  async _saveVisit() {
    if (!this._edit || this._edit.saving) return;
    const edit = this._edit;
    const visit = edit.visit;

    const nameInput = this._modal.querySelector(".dt-input");
    const name = nameInput ? nameInput.value.trim() : edit.name || "";

    const updates = { status: "confirmed" };
    const isContact = Boolean(edit.selected?.contact);
    const lookupOnly =
      isContact ||
      Boolean(
        edit.selected?.source &&
          !edit.selected.osm &&
          edit.selected.source !== "saved"
      );
    let selectedId = edit.selected ? String(edit.selected.id) : null;
    if (this._isLocalSource() && edit.selected && !lookupOnly) {
      try {
        selectedId = await this._ensureSelectedPlaceSaved();
      } catch (err) {
        console.warn("GeoPulse: plek bewaren mislukt", err);
      }
    }
    if (
      !lookupOnly &&
      edit.selected &&
      selectedId &&
      selectedId !== String(visit.place_id ?? "")
    ) {
      updates.place_id = this._isLocalSource()
        ? selectedId
        : Number(edit.selected.id);
    }
    if (isContact && edit.selected) {
      updates.name = edit.selected.name;
    }
    if (name !== (visit.editable_name || "")) {
      updates.name = name;
    }

    const saveButton = this._modal.querySelector('[data-action="save-visit"]');
    const original = saveButton?.innerHTML;
    edit.saving = true;
    if (saveButton) {
      saveButton.disabled = true;
      saveButton.innerHTML = '<span class="dt-btnspinner"></span>Opslaan…';
    }

    try {
      await this._hass.callWS({
        type: "geopulse/local_update_visit",
        date: this._date,
        entity_id: this._localEntity(),
        visit_id: String(visit.visit_id),
        ...updates,
      });
      this._closeModal();
      this._toast("Bezoek bijgewerkt en bevestigd");
      await this._loadDay();
    } catch (err) {
      console.error("GeoPulse: bezoek opslaan mislukt", err);
      this._toast(err?.message || "Opslaan mislukt", "error");
      edit.saving = false;
      if (saveButton) {
        saveButton.disabled = false;
        saveButton.innerHTML = original;
      }
    }
  }

  async _declineVisit() {
    if (!this._edit || this._edit.saving) return;
    if (
      !window.confirm(
        translateText(
          "Dit bezoek verwijderen? Het verdwijnt uit de tijdlijn. Je kunt de dag later opnieuw opbouwen."
        )
      )
    ) {
      return;
    }
    const edit = this._edit;
    const button = this._modal.querySelector('[data-action="decline-visit"]');
    const original = button?.innerHTML;
    edit.saving = true;
    if (button) {
      button.disabled = true;
      button.innerHTML = '<span class="dt-btnspinner"></span>Afwijzen…';
    }

    try {
      await this._hass.callWS({
        type: "geopulse/local_delete_visit",
        date: this._date,
        entity_id: this._localEntity(),
        visit_id: String(edit.visit.visit_id),
      });
      this._closeModal();
      this._toast("Bezoek verwijderd");
      await this._loadDay();
    } catch (err) {
      console.error("GeoPulse: bezoek verwijderen mislukt", err);
      this._toast(err?.message || "Verwijderen mislukt", "error");
      edit.saving = false;
      if (button) {
        button.disabled = false;
        button.innerHTML = original;
      }
    }
  }

  _findJourney(trackId, key) {
    const entries = this._data?.entries || [];
    if (key) {
      const exact = entries.find(
        (entry) => entry.type === "journey" && entry.key === key
      );
      if (exact) return exact;
    }
    const id = String(trackId ?? "");
    return entries.find(
      (entry) =>
        entry.type === "journey" &&
        (String(entry.track_id) === id ||
          (entry.track_ids || []).map(String).includes(id))
    );
  }

  _routesForEntry(entry) {
    const ids = new Set(
      [entry.key, entry.track_id, ...(entry.track_ids || [])].map(String)
    );
    return (this._data?.routes || []).filter((route) =>
      ids.has(String(route.track_id))
    );
  }

  _nextJourney(entry) {
    const entries = this._data?.entries || [];
    const index = entries.findIndex((item) => item.key === entry.key);
    if (index < 0) return null;
    return (
      entries
        .slice(index + 1)
        .find((item) => item.type === "journey") || null
    );
  }

  _previousJourney(entry) {
    const entries = this._data?.entries || [];
    const index = entries.findIndex((item) => item.key === entry.key);
    if (index < 0) return null;
    return (
      [...entries.slice(0, index)]
        .reverse()
        .find((item) => item.type === "journey") || null
    );
  }

  _visitsBetween(first, second) {
    const entries = this._data?.entries || [];
    const a = entries.findIndex((item) => item.key === first.key);
    const b = entries.findIndex((item) => item.key === second.key);
    if (a < 0 || b < 0) return [];
    const low = Math.min(a, b);
    const high = Math.max(a, b);
    return entries
      .slice(low + 1, high)
      .filter((item) => item.type === "visit");
  }

  _openJourneyEdit(trackId, key) {
    const entry = this._findJourney(trackId, key);
    if (!entry) return;
    const routes = this._routesForEntry(entry);
    const route = routes.length === 1 ? routes[0] : null;
    const times = route?.times || [];

    this._journeyEdit = {
      entry,
      route,
      splitIndex: times.length >= 4 ? Math.round((times.length - 1) / 2) : 0,
      mode: entry.mode === "mixed" ? "" : entry.mode,
      note: entry.note || "",
      saving: false,
    };
    this._modal.hidden = false;
    this._renderJourneyDialog();
  }

  _renderJourneyDialog() {
    const edit = this._journeyEdit;
    if (!edit) return;
    const entry = edit.entry;
    const info = modeInfo(entry.mode);
    const meta = [
      `${fmtTime(entry.start)} – ${fmtTime(entry.end)}`,
      fmtDistance(entry.distance, entry.distance_unit),
      fmtSeconds(entry.duration_seconds),
    ]
      .filter(Boolean)
      .join(" · ");

    const options = JOURNEY_MODE_ORDER.map(
      (mode) =>
        `<option value="${mode}" ${
          edit.mode === mode ? "selected" : ""
        }>${esc(modeLabel(mode))}</option>`
    ).join("");

    this._modal.innerHTML = `
      <div class="dt-modal-backdrop" data-action="close-modal"></div>
      <div class="dt-dialog" role="dialog" aria-modal="true" aria-labelledby="dt-journey-title">
        <div class="dt-dlg-head">
          <div>
            <h2 id="dt-journey-title">Reis aanpassen</h2>
            <div class="dt-dlg-sub">${esc(meta)}</div>
          </div>
          <button class="dt-iconbtn" data-action="close-modal" aria-label="Sluiten">
            <ha-icon icon="mdi:close"></ha-icon>
          </button>
        </div>

        <div class="dt-dlg-body">
          <label class="dt-label" for="dt-journey-mode">Reismethode</label>
          <select id="dt-journey-mode" class="dt-input dt-select">
            ${options}
          </select>
          <div class="dt-hint">
            Kies hoe je deze reis hebt afgelegd. De samenvatting bovenaan
            gebruikt daarna dezelfde methode.
          </div>

          <label class="dt-label" for="dt-journey-note">Opmerking (optioneel)</label>
          <textarea id="dt-journey-note" class="dt-input dt-textarea" maxlength="280"
            placeholder="Bijv. Boswandeling met Rubbel">${esc(edit.note)}</textarea>
          <div class="dt-hint">Deze opmerking wordt alleen in Home Assistant bewaard.</div>

          ${
            entry.merged
              ? `<div class="dt-merged-hint"><ha-icon icon="mdi:link-variant"></ha-icon>
                  Deze reis bestaat uit ${entry.track_ids.length} ritten.
                </div>`
              : ""
          }

          ${(() => {
            const times = edit.route?.times || [];
            if (times.length < 4) return "";
            const next = this._nextJourney(entry);
            const previous = this._previousJourney(entry);
            if (!next && !previous) return "";
            const current = times[edit.splitIndex] || times[0];
            const between = next
              ? this._visitsBetween(entry, next)
              : previous
                ? this._visitsBetween(previous, entry)
                : [];
            return `
              <div class="dt-split">
                <label class="dt-label" for="dt-split-range">Route splitsen</label>
                <input id="dt-split-range" class="dt-splitrange" type="range"
                  min="2" max="${times.length - 2}" step="1"
                  value="${edit.splitIndex}">
                <div class="dt-splitmeta">Splitstijd:
                  <b class="dt-splittime">${esc(fmtTime(current))}</b>
                </div>
                <div class="dt-splitactions">
                  ${
                    previous
                      ? `<button class="dt-btn" data-action="move-head">
                          <ha-icon icon="mdi:arrow-collapse-left"></ha-icon>Eerste deel → vorige reis
                        </button>`
                      : ""
                  }
                  ${
                    next
                      ? `<button class="dt-btn" data-action="move-tail">
                          <ha-icon icon="mdi:arrow-collapse-right"></ha-icon>Laatste deel → volgende reis
                        </button>`
                      : ""
                  }
                </div>
                <div class="dt-hint">
                  Het gekozen deel gaat naar de aangrenzende reis en krijgt de
                  methode van die reis. Tussenliggende bezoeken worden verwijderd.
                  ${between.length ? `(${between.length} bezoek${between.length === 1 ? "" : "en"})` : ""}
                </div>
              </div>`;
          })()}
        </div>

        <div class="dt-dlg-actions">
          ${
            entry.merged
              ? `<button class="dt-btn dt-danger-ghost" data-action="unmerge-journey">Splitsen</button>`
              : ""
          }
          <div class="dt-spacer"></div>
          <button class="dt-btn" data-action="close-modal">Annuleren</button>
          <button class="dt-btn dt-primary" data-action="save-journey">
            <ha-icon icon="mdi:check"></ha-icon>Opslaan
          </button>
        </div>
      </div>`;
  }

  async _saveJourney() {
    if (!this._journeyEdit || this._journeyEdit.saving) return;
    const edit = this._journeyEdit;
    const modeSelect = this._modal.querySelector("#dt-journey-mode");
    const noteInput = this._modal.querySelector("#dt-journey-note");
    const mode = modeSelect ? modeSelect.value : edit.mode;
    const note = noteInput ? noteInput.value.trim() : edit.note;

    const button = this._modal.querySelector('[data-action="save-journey"]');
    const original = button?.innerHTML;
    edit.saving = true;
    if (button) {
      button.disabled = true;
      button.innerHTML = '<span class="dt-btnspinner"></span>Opslaan…';
    }

    try {
      await this._hass.callWS({
        type: "geopulse/local_update_journey",
        date: this._date,
        entity_id: this._localEntity(),
        track_key: String(edit.entry.key),
        mode,
        note,
      });
      this._closeModal();
      this._toast("Reis bijgewerkt");
      await this._loadDay();
    } catch (err) {
      console.error("GeoPulse: reis opslaan mislukt", err);
      this._toast(err?.message || "Opslaan mislukt", "error");
      edit.saving = false;
      if (button) {
        button.disabled = false;
        button.innerHTML = original;
      }
    }
  }

  async _moveJourneyPart(direction) {
    const edit = this._journeyEdit;
    if (!edit || edit.saving || !edit.route) return;
    const times = edit.route.times || [];
    const splitTs = times[edit.splitIndex];
    if (!splitTs) {
      this._toast("Kies een ander splitpunt.", "error");
      return;
    }
    const target =
      direction === "tail_to_next"
        ? this._nextJourney(edit.entry)
        : this._previousJourney(edit.entry);
    if (!target) return;
    const between = this._visitsBetween(
      direction === "tail_to_next" ? edit.entry : target,
      direction === "tail_to_next" ? target : edit.entry
    );
    if (
      between.length &&
      !window.confirm(
        translateText(
          "Tussenliggende bezoeken worden verwijderd. Doorgaan?"
        )
      )
    ) {
      return;
    }

    const button = this._modal.querySelector(
      direction === "tail_to_next"
        ? '[data-action="move-tail"]'
        : '[data-action="move-head"]'
    );
    const original = button?.innerHTML;
    edit.saving = true;
    if (button) {
      button.disabled = true;
      button.innerHTML = '<span class="dt-btnspinner"></span>Verplaatsen…';
    }
    try {
      await this._hass.callWS({
        type: "geopulse/local_move_journey_part",
        date: this._date,
        entity_id: this._localEntity(),
        track_key: String(edit.entry.key),
        split_ts: splitTs,
        direction,
      });
      this._closeModal();
      this._toast("Deel verplaatst");
      await this._loadDay();
    } catch (err) {
      console.error("GeoPulse: routedeel verplaatsen mislukt", err);
      this._toast(err?.message || "Verplaatsen mislukt", "error");
      edit.saving = false;
      if (button) {
        button.disabled = false;
        button.innerHTML = original;
      }
    }
  }

  async _mergeJourney(entry) {
    if (!entry || !this._data) return;
    const index = this._data.entries.findIndex((item) => item.key === entry.key);
    const previous = index > 0 ? this._data.entries[index - 1] : null;
    if (!previous || previous.type !== "journey") return;

    const trackIds = [
      ...(previous.track_ids || [previous.track_id]),
      ...(entry.track_ids || [entry.track_id]),
    ];
    try {
      await this._hass.callWS({
        type: "geopulse/local_merge_journeys",
        date: this._date,
        entity_id: this._localEntity(),
        keys: [String(previous.key), String(entry.key)],
      });
      this._toast("Reizen samengevoegd");
      await this._loadDay();
    } catch (err) {
      console.error("GeoPulse: samenvoegen mislukt", err);
      this._toast(err?.message || "Samenvoegen mislukt", "error");
    }
  }

  async _unmergeJourney(entry) {
    if (!entry) return;
    if (
      !window.confirm(
        translateText(
          "Deze dag opnieuw opbouwen? Handmatige aanpassingen aan de hele dag gaan verloren."
        )
      )
    ) {
      return;
    }
    try {
      await this._hass.callWS({
        type: "geopulse/local_reset_day",
        date: this._date,
        entity_id: this._localEntity(),
      });
      this._closeModal();
      this._toast("Dag opnieuw opgebouwd");
      await this._loadDay();
    } catch (err) {
      console.error("GeoPulse: dag herberekenen mislukt", err);
      this._toast(err?.message || "Herberekenen mislukt", "error");
    }
  }

  _closeModal() {
    this._edit = null;
    this._journeyEdit = null;
    if (this._modal) {
      this._modal.hidden = true;
      this._modal.innerHTML = "";
    }
  }

  /* ---------------------------------------------------------------- */
  /* Events                                                            */
  /* ---------------------------------------------------------------- */

  _handleClick(event) {
    const path = event.composedPath();

    // Close the POI dropdown when clicking outside it.
    if (this._edit?.comboOpen) {
      const inCombo = path.some(
        (el) => el instanceof HTMLElement && el.classList?.contains("dt-combo")
      );
      if (!inCombo) {
        this._edit.comboOpen = false;
        this._renderComboState();
      }
    }

    const nav = event.target.closest?.("[data-nav]");
    if (nav) {
      this._shiftDay(nav.dataset.nav === "prev" ? -1 : 1);
      return;
    }

    const calDay = event.target.closest?.("[data-cal-day]");
    if (calDay) {
      this._setDate(calDay.dataset.calDay);
      return;
    }

    const placeOption = event.target.closest?.("[data-place-id]");
    if (placeOption) {
      this._setSelectedPlace(placeOption.dataset.placeId);
      return;
    }

    const actionEl = event.target.closest?.("[data-action]");
    if (actionEl) {
      const action = actionEl.dataset.action;
      const entry = actionEl.closest(".dt-entry");

      switch (action) {
        case "calendar":
          this._toggleCalendar();
          return;
        case "places":
          this._togglePlacesSearch();
          return;
        case "places-close":
          this._closePlacesSearch();
          return;
        case "places-run":
          this._runPlacesSearch();
          return;
        case "place-open":
          this._openPlaceResult(Number(actionEl.dataset.index));
          return;
        case "place-save":
          this._savePlaceResult(Number(actionEl.dataset.index));
          return;
        case "export":
          this._exportArchive(actionEl.dataset.format || "gpx");
          return;
        case "contacts-import":
          this._placesPop?.querySelector(".dt-contactfile")?.click();
          return;
        case "history-import":
          this._placesPop?.querySelector(".dt-historyfile")?.click();
          return;
        case "today":
          this._setDate(todayISO());
          return;
        case "cal-today":
          this._setDate(todayISO());
          return;
        case "cal-prev":
          this._shiftCalendarMonth(-1);
          return;
        case "cal-next":
          this._shiftCalendarMonth(1);
          return;
        case "refresh":
          this._fitMap = false;
          this._loadDay();
          return;
        case "map-max":
          this._setMapMaximized(!this._mapMaximized);
          return;
        case "map-style":
          this._toggleMapStyle();
          return;
        case "fit":
          this._fitMap = true;
          this._fitToData();
          return;
        case "retry":
          this._loadDay();
          return;
        case "edit-journey":
          if (entry)
            this._openJourneyEdit(entry.dataset.trackId, entry.dataset.key);
          return;
        case "merge-journey":
          if (entry)
            this._mergeJourney(
              this._findJourney(entry.dataset.trackId, entry.dataset.key)
            );
          return;
        case "unmerge-journey":
          if (entry)
            this._unmergeJourney(
              this._findJourney(entry.dataset.trackId, entry.dataset.key)
            );
          return;
        case "save-journey":
          this._saveJourney();
          return;
        case "move-tail":
          this._moveJourneyPart("tail_to_next");
          return;
        case "move-head":
          this._moveJourneyPart("head_to_previous");
          return;
        case "confirm-visit":
          if (entry) this._confirmVisit(actionEl, entry.dataset.visitId);
          return;
        case "edit-visit":
          if (entry) this._openEdit(entry.dataset.visitId);
          return;
        case "close-modal":
          this._closeModal();
          return;
        case "toggle-combo":
          if (this._edit) {
            this._edit.comboOpen = !this._edit.comboOpen;
            this._renderComboState();
            if (this._edit.comboOpen) {
              window.setTimeout(() => {
                this._modal
                  ?.querySelector(".dt-combosearch input")
                  ?.focus();
              }, 30);
            }
          }
          return;
        case "save-visit":
          this._saveVisit();
          return;
        case "decline-visit":
          this._declineVisit();
          return;
        default:
          break;
      }
    }

    // Clicking an entry focuses it on the map, unless a button was clicked.
    const entryEl = event.target.closest?.(".dt-entry");
    if (entryEl && !event.target.closest?.("button")) {
      if (entryEl.dataset.key) this._selectEntry(entryEl.dataset.key, false);
    }
  }

  _toast(message, type = "success") {
    if (!this._toasts) return;
    const toast = document.createElement("div");
    toast.className = `dt-toast dt-toast-${type}`;
    toast.innerHTML = `<ha-icon icon="${
      type === "error" ? "mdi:alert-circle-outline" : "mdi:check-circle-outline"
    }"></ha-icon><span>${esc(translateText(message))}</span>`;
    this._toasts.appendChild(toast);
    window.setTimeout(() => {
      toast.classList.add("dt-toast-out");
      window.setTimeout(() => toast.remove(), 250);
    }, 3200);
  }

  /* ---------------------------------------------------------------- */
  /* CSS                                                               */
  /* ---------------------------------------------------------------- */

  _css() {
    return `
      :host {
        --dt-bg: var(--primary-background-color, #f4f6f8);
        --dt-card: var(--card-background-color, #ffffff);
        --dt-text: var(--primary-text-color, #1f2937);
        --dt-sub: var(--secondary-text-color, #6b7280);
        --dt-divider: var(--divider-color, rgba(0, 0, 0, 0.12));
        --dt-primary: var(--primary-color, #039be5);
        --dt-primary-soft: color-mix(in srgb, var(--dt-primary) 12%, transparent);
        --dt-radius: var(--ha-card-border-radius, 14px);
        --dt-shadow: 0 2px 10px rgba(15, 23, 42, 0.08);
        --dt-suggested: #f59e0b;
        --dt-confirmed: #16a34a;
        display: block;
        /* A timeline card is a full-page view: bind it to the viewport so the
           map and the scrollable list never stretch with their content. */
        height: calc(100vh - var(--header-height, 56px));
        min-height: min(540px, calc(100vh - var(--header-height, 56px)));
        color: var(--dt-text);
        font-family: var(--paper-font-body1_-_font-family, Roboto, system-ui, -apple-system, "Segoe UI", sans-serif);
      }

      * { box-sizing: border-box; }
      [hidden] { display: none !important; }

      ha-icon { --mdc-icon-size: 22px; display: inline-flex; }

      .dt-app {
        position: relative;
        display: flex;
        flex-direction: column;
        height: 100%;
        min-height: 0;
        overflow: hidden;
        background: var(--dt-bg);
      }

      /* ---------------- top bar ---------------- */
      .dt-topbar {
        position: relative;
        z-index: 500;
        display: flex;
        align-items: center;
        gap: 14px;
        min-height: 64px;
        padding: 10px 16px;
        background: var(--dt-card);
        border-bottom: 1px solid var(--dt-divider);
      }

      .dt-brand { display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1 1 0; }

      .dt-brand-icon {
        width: 38px; height: 38px; flex: 0 0 38px;
        display: flex; align-items: center; justify-content: center;
        border-radius: 12px;
        color: #fff;
        background: linear-gradient(135deg, #0ea5e9, #2563eb);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.28);
      }
      .dt-brand-icon ha-icon { --mdc-icon-size: 21px; }
      .dt-brand-text { min-width: 0; }
      .dt-title { font-size: 19px; font-weight: 700; letter-spacing: -0.2px; line-height: 1.15; }
      .dt-brand-sub { font-size: 11.5px; color: var(--dt-sub); margin-top: 2px; white-space: nowrap; }

      .dt-datenav {
        display: flex; align-items: center; gap: 4px;
        flex: 0 0 auto;
      }

      .dt-iconbtn {
        width: 38px; height: 38px; flex: 0 0 38px;
        display: inline-flex; align-items: center; justify-content: center;
        border: 0; border-radius: 50%;
        background: transparent; color: var(--dt-text);
        cursor: pointer; padding: 0;
        transition: background 0.15s ease, opacity 0.15s ease;
      }
      .dt-iconbtn:hover { background: color-mix(in srgb, var(--dt-text) 8%, transparent); }
      .dt-iconbtn:disabled { opacity: 0.28; cursor: default; }
      .dt-iconbtn:disabled:hover { background: transparent; }

      .dt-datebtn {
        display: inline-flex; align-items: center; gap: 8px;
        height: 40px; padding: 0 14px;
        border: 1px solid var(--dt-divider); border-radius: 20px;
        background: var(--dt-card); color: var(--dt-text);
        font: inherit; font-size: 14px; font-weight: 600;
        cursor: pointer; white-space: nowrap;
        transition: border-color 0.15s ease, background 0.15s ease;
      }
      .dt-datebtn:hover { border-color: var(--dt-primary); background: var(--dt-primary-soft); }
      .dt-datebtn ha-icon { --mdc-icon-size: 19px; color: var(--dt-primary); }
      .dt-datebtn .dt-chev { --mdc-icon-size: 17px; color: var(--dt-sub); }

      .dt-todaybtn {
        height: 40px; padding: 0 14px; margin-left: 4px;
        border: 0; border-radius: 20px;
        background: var(--dt-primary-soft); color: var(--dt-primary);
        font: inherit; font-size: 13px; font-weight: 600;
        cursor: pointer;
      }
      .dt-todaybtn:disabled { opacity: 0.4; cursor: default; }

      .dt-spacer { flex: 1; }
      .dt-refresh { color: var(--dt-sub); }

      /* ---------------- layout ---------------- */
      .dt-main {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 430px;
        flex: 1;
        min-height: 0;
      }

      .dt-mapwrap {
        position: relative;
        min-height: 0;
        overflow: hidden;
        overscroll-behavior: contain;
        background: #dfe8ef;
      }

      .dt-map {
        position: absolute; inset: 0; z-index: 0;
        background: #dfe8ef;
        -webkit-user-select: none;
        user-select: none;
      }
      /* Leaflet zet op .leaflet-touch-drag touch-action: pinch-zoom; dat
         moet de kaart niet overnemen, anders zoomt de pagina/app mee. */
      .dt-map.leaflet-container { touch-action: none !important; }

      /* Nachtmodus: dezelfde rustige OSM-tegels, maar donker gefilterd.
         Routes en markers zitten in andere Leaflet-panes en houden hun kleur. */
      .dt-map.dt-night { background: #0b1220; }
      .dt-map.dt-night .leaflet-tile-pane {
        filter: invert(1) hue-rotate(180deg) brightness(0.9)
          contrast(1.05) saturate(0.75);
      }
      .dt-map.dt-night .leaflet-control-attribution {
        background: rgba(15, 23, 42, 0.75);
        color: #cbd5e1;
      }

      /* ---------------- map overlays ---------------- */
      .dt-map-badge {
        position: absolute; z-index: 400;
        top: 12px; left: 54px;
        display: flex; align-items: center; gap: 7px;
        padding: 7px 12px;
        border-radius: 999px;
        background: color-mix(in srgb, var(--dt-card) 94%, transparent);
        box-shadow: var(--dt-shadow);
        color: var(--dt-text);
        font-size: 13px; font-weight: 600;
        backdrop-filter: blur(8px);
        pointer-events: none;
      }
      .dt-map-badge ha-icon { --mdc-icon-size: 18px; color: var(--dt-primary); }

      .dt-mapbtn {
        position: absolute; z-index: 400;
        top: 12px; right: 12px;
        width: 42px; height: 42px;
        display: flex; align-items: center; justify-content: center;
        border: 0; border-radius: 12px;
        background: color-mix(in srgb, var(--dt-card) 94%, transparent);
        color: var(--dt-text);
        box-shadow: var(--dt-shadow);
        cursor: pointer;
        backdrop-filter: blur(8px);
      }
      .dt-mapbtn:hover { color: var(--dt-primary); }

      .dt-mapbtn.dt-map-max { top: 62px; }
      .dt-mapbtn.dt-map-style { top: 112px; }

      .dt-app.dt-map-max .dt-topbar,
      .dt-app.dt-map-max .dt-side {
        display: none;
      }
      .dt-app.dt-map-max .dt-main {
        display: block;
      }
      .dt-app.dt-map-max .dt-mapwrap {
        position: fixed;
        inset: 0;
        z-index: 1500;
        border-radius: 0;
        background: #dfe8ef;
      }

      .dt-legend {
        position: absolute; z-index: 400;
        left: 12px; bottom: 26px;
        display: flex; flex-wrap: wrap; gap: 6px;
        max-width: 65%;
        padding: 7px 9px;
        border-radius: 12px;
        background: color-mix(in srgb, var(--dt-card) 93%, transparent);
        box-shadow: var(--dt-shadow);
        backdrop-filter: blur(8px);
        font-size: 11.5px; color: var(--dt-text);
      }
      .dt-legend-item { display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }
      .dt-legend-item i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

      .dt-map-empty {
        position: absolute; z-index: 350;
        top: 50%; left: 50%; transform: translate(-50%, -50%);
        display: flex; flex-direction: column; align-items: center; gap: 8px;
        padding: 20px 24px;
        border-radius: 16px;
        background: color-mix(in srgb, var(--dt-card) 94%, transparent);
        box-shadow: var(--dt-shadow);
        color: var(--dt-sub); font-size: 14px;
        backdrop-filter: blur(8px);
        text-align: center;
      }
      .dt-map-empty ha-icon { --mdc-icon-size: 34px; color: var(--dt-sub); }

      .dt-map-spinner {
        position: absolute; z-index: 450;
        top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        width: 48px; height: 48px;
        display: flex; align-items: center; justify-content: center;
        border-radius: 50%;
        background: color-mix(in srgb, var(--dt-card) 94%, transparent);
        box-shadow: var(--dt-shadow);
        backdrop-filter: blur(8px);
      }
      .dt-map-spinner span {
        width: 21px; height: 21px;
        border: 2.5px solid var(--dt-primary);
        border-top-color: transparent;
        border-radius: 50%;
        animation: dt-spin 0.75s linear infinite;
      }

      /* ---------------- sidebar ---------------- */
      .dt-side {
        display: flex; flex-direction: column;
        min-height: 0; min-width: 0;
        background: var(--dt-bg);
        border-left: 1px solid var(--dt-divider);
      }

      /* Alleen op smalle schermen: sleep de grens tussen kaart en lijst. */
      .dt-resizer { display: none; }

      .dt-app.dt-resizing .dt-map,
      .dt-app.dt-resizing .dt-side { user-select: none; }
      .dt-app.dt-resizing .dt-map { pointer-events: none; }

      .dt-sidehead {
        padding: 18px 18px 10px;
        background: var(--dt-bg);
        border-bottom: 1px solid transparent;
      }

      .dt-daytitle {
        font-size: 15px; font-weight: 700;
        letter-spacing: -0.1px;
        margin-bottom: 10px;
      }

      .dt-summary {
        display: flex; flex-wrap: wrap; align-items: center; gap: 7px;
        overflow: visible;
        padding-bottom: 2px;
      }
      .dt-summary::-webkit-scrollbar { display: none; }

      .dt-chip {
        display: inline-flex; align-items: center; gap: 5px;
        flex: 0 0 auto;
        height: 30px; padding: 0 10px;
        border-radius: 999px;
        background: var(--dt-card);
        border: 1px solid var(--dt-divider);
        color: var(--dt-text);
        font-size: 12px; font-weight: 500;
        white-space: nowrap;
      }
      .dt-chip ha-icon { --mdc-icon-size: 15px; color: var(--dt-sub); }
      .dt-chip b { font-weight: 700; margin-left: 1px; }
      .dt-chip-mode { gap: 6px; }
      .dt-chip-mode b { color: var(--dt-sub); font-weight: 600; }
      .dt-mode-dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: var(--chip-color, var(--dt-primary));
        display: inline-block;
      }

      .dt-listwrap { position: relative; flex: 1; min-height: 0; overflow: hidden; }

      .dt-loadingbar {
        position: absolute; z-index: 5;
        top: 0; left: 0; right: 0;
        height: 2px; overflow: hidden; background: var(--dt-primary-soft);
      }
      .dt-loadingbar::after {
        content: ""; position: absolute; inset: 0;
        background: var(--dt-primary);
        animation: dt-loading 1.1s ease-in-out infinite;
        transform-origin: left;
      }
      @keyframes dt-loading {
        0% { transform: translateX(-100%) scaleX(0.35); }
        60% { transform: translateX(60%) scaleX(0.55); }
        100% { transform: translateX(100%) scaleX(0.35); }
      }

      .dt-list {
        height: 100%;
        overflow-y: auto;
        padding: 2px 14px 28px;
        transition: opacity 0.18s ease;
      }
      .dt-list.dt-stale { opacity: 0.55; }

      /* ---------------- timeline entries ---------------- */
      .dt-entry {
        position: relative;
        display: flex;
        gap: 10px;
        padding-bottom: 8px;
        cursor: pointer;
      }

      .dt-rail {
        position: relative;
        flex: 0 0 38px;
        display: flex;
        justify-content: center;
        padding-top: 10px;
      }
      .dt-entry:not(.dt-last) .dt-rail::after {
        content: "";
        position: absolute;
        top: 50px;
        bottom: -8px;
        width: 2px;
        border-radius: 2px;
        background: var(--dt-divider);
        opacity: 0.7;
      }

      .dt-dot {
        position: relative; z-index: 1;
        width: 34px; height: 34px;
        display: flex; align-items: center; justify-content: center;
        border-radius: 50%;
        background: var(--dt-card);
        border: 1px solid var(--dt-divider);
        font-size: 15px;
        line-height: 1;
      }
      .dt-dot-visit {
        background: var(--dt-confirmed);
        border-color: #fff;
        color: #fff;
        box-shadow: 0 2px 6px rgba(22, 163, 74, 0.3);
      }
      .dt-dot-visit svg { width: 17px; height: 17px; fill: currentColor; }
      .dt-dot-suggested {
        background: var(--dt-suggested);
        box-shadow: 0 2px 6px rgba(245, 158, 11, 0.32);
      }
      .dt-dot-home {
        background: var(--dt-primary);
        border-color: #fff;
        box-shadow: 0 2px 6px color-mix(in srgb, var(--dt-primary) 35%, transparent);
      }
      .dt-dot-mode {
        background: color-mix(in srgb, var(--mode-color) 14%, var(--dt-card));
        border-color: color-mix(in srgb, var(--mode-color) 30%, transparent);
        box-shadow: none;
      }

      .dt-card {
        flex: 1;
        min-width: 0;
        padding: 11px 13px 12px;
        border-radius: 14px;
        background: var(--dt-card);
        border: 1px solid var(--dt-divider);
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
      }
      .dt-entry:hover .dt-card {
        border-color: color-mix(in srgb, var(--dt-primary) 34%, var(--dt-divider));
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
      }
      .dt-entry.dt-selected .dt-card {
        border-color: var(--dt-primary);
        box-shadow: 0 0 0 1px var(--dt-primary), 0 5px 16px rgba(15, 23, 42, 0.1);
        background: color-mix(in srgb, var(--dt-primary) 4%, var(--dt-card));
      }
      .dt-card-journey { padding-top: 10px; padding-bottom: 11px; }

      .dt-entry-head {
        display: flex; align-items: center; gap: 8px;
        justify-content: space-between;
      }
      .dt-entry-title {
        font-size: 14.5px; font-weight: 650;
        line-height: 1.3;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
      .dt-entry-journey .dt-entry-title { font-weight: 600; }
      .dt-entry-meta {
        margin-top: 3px;
        color: var(--dt-sub);
        font-size: 12.5px;
        line-height: 1.35;
      }
      .dt-entry-times {
        margin-top: 2px;
        color: var(--dt-sub);
        font-size: 12px;
        font-variant-numeric: tabular-nums;
      }
      .dt-entry-modes {
        display: flex; flex-wrap: wrap; gap: 5px;
        margin-top: 6px;
      }
      .dt-modechip {
        display: inline-flex; align-items: center; gap: 5px;
        padding: 2px 7px;
        border-radius: 999px;
        background: var(--dt-card);
        border: 1px solid var(--dt-divider);
        color: var(--dt-sub);
        font-size: 11.5px;
        white-space: nowrap;
      }
      .dt-modechip i {
        width: 7px; height: 7px; border-radius: 50%;
        display: inline-block;
        background: var(--dt-primary);
      }
      .dt-entry-note {
        display: flex;
        align-items: flex-start;
        gap: 6px;
        margin-top: 7px;
        padding: 7px 9px;
        border-radius: 9px;
        background: color-mix(in srgb, var(--dt-primary) 7%, transparent);
        color: var(--dt-text);
        font-size: 12px;
        line-height: 1.4;
      }
      .dt-entry-note ha-icon {
        --mdc-icon-size: 15px;
        color: var(--dt-primary);
        flex: 0 0 15px;
        margin-top: 1px;
      }
      .dt-journey-actions {
        margin-top: 7px;
        flex-wrap: wrap;
        gap: 4px;
      }
      .dt-journey-actions .dt-btn {
        height: 29px;
        padding: 0 8px;
        font-size: 11.5px;
      }

      .dt-badges { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px; }
      .dt-badge {
        display: inline-flex; align-items: center; gap: 4px;
        height: 22px; padding: 0 8px;
        border-radius: 999px;
        font-size: 11px; font-weight: 600;
        background: color-mix(in srgb, var(--dt-text) 7%, transparent);
        color: var(--dt-sub);
      }
      .dt-badge ha-icon { --mdc-icon-size: 14px; }
      .dt-badge-suggested {
        background: color-mix(in srgb, var(--dt-suggested) 16%, transparent);
        color: #b45309;
      }
      .dt-badge-confirmed {
        background: color-mix(in srgb, var(--dt-confirmed) 13%, transparent);
        color: #15803d;
      }
      .dt-badge-continued {
        background: transparent;
        border: 1px dashed var(--dt-divider);
      }
      .dt-badge-merged {
        background: var(--dt-primary-soft);
        color: var(--dt-primary);
      }

      .dt-actions {
        display: flex; align-items: center; gap: 7px;
        margin-top: 10px;
      }

      .dt-btn {
        display: inline-flex; align-items: center; justify-content: center; gap: 6px;
        height: 33px; padding: 0 13px;
        border: 1px solid var(--dt-divider);
        border-radius: 17px;
        background: var(--dt-card);
        color: var(--dt-text);
        font: inherit; font-size: 12.5px; font-weight: 600;
        cursor: pointer;
        white-space: nowrap;
        transition: background 0.15s ease, border-color 0.15s ease, transform 0.1s ease;
      }
      .dt-btn:hover { border-color: var(--dt-primary); background: var(--dt-primary-soft); }
      .dt-btn:active { transform: scale(0.98); }
      .dt-btn:disabled { opacity: 0.6; cursor: default; }
      .dt-btn ha-icon { --mdc-icon-size: 17px; }
      .dt-primary {
        border-color: var(--dt-primary);
        background: var(--dt-primary);
        color: #fff;
        box-shadow: 0 2px 6px color-mix(in srgb, var(--dt-primary) 32%, transparent);
      }
      .dt-primary:hover { background: var(--dt-primary); filter: brightness(1.06); }
      .dt-btn-quiet { border-color: transparent; background: transparent; color: var(--dt-sub); }
      .dt-btn-quiet:hover { background: color-mix(in srgb, var(--dt-text) 7%, transparent); border-color: transparent; }
      .dt-danger-ghost { border-color: transparent; background: transparent; color: #dc2626; }
      .dt-danger-ghost:hover { background: color-mix(in srgb, #dc2626 10%, transparent); border-color: transparent; }

      .dt-btnspinner {
        width: 13px; height: 13px;
        border: 2px solid currentColor;
        border-top-color: transparent;
        border-radius: 50%;
        display: inline-block;
        animation: dt-spin 0.7s linear infinite;
      }
      @keyframes dt-spin { to { transform: rotate(360deg); } }

      /* ---------------- empty / skeleton / error ---------------- */
      .dt-empty {
        display: flex; flex-direction: column; align-items: center;
        text-align: center;
        padding: 52px 26px 30px;
        color: var(--dt-sub);
      }
      .dt-empty-icon {
        width: 58px; height: 58px;
        display: flex; align-items: center; justify-content: center;
        border-radius: 18px;
        background: color-mix(in srgb, var(--dt-text) 6%, transparent);
        margin-bottom: 14px;
      }
      .dt-empty-icon ha-icon { --mdc-icon-size: 30px; color: var(--dt-sub); }
      .dt-empty-title { font-size: 15px; font-weight: 650; color: var(--dt-text); }
      .dt-empty-text { font-size: 12.5px; line-height: 1.45; margin-top: 5px; max-width: 270px; }

      .dt-skeleton { padding-top: 8px; }
      .dt-skel-row { display: flex; gap: 12px; padding: 12px 0; }
      .dt-skel-dot {
        width: 34px; height: 34px; flex: 0 0 34px; border-radius: 50%;
        background: color-mix(in srgb, var(--dt-text) 7%, transparent);
        animation: dt-pulse 1.2s ease-in-out infinite;
      }
      .dt-skel-lines { flex: 1; padding-top: 4px; }
      .dt-skel-line {
        height: 12px; border-radius: 6px;
        background: color-mix(in srgb, var(--dt-text) 7%, transparent);
        margin-bottom: 8px;
        animation: dt-pulse 1.2s ease-in-out infinite;
      }
      .dt-skel-line.w70 { width: 70%; }
      .dt-skel-line.w45 { width: 45%; }
      @keyframes dt-pulse { 0%, 100% { opacity: 0.55; } 50% { opacity: 1; } }

      .dt-errorcard {
        display: flex; flex-direction: column; align-items: center;
        text-align: center; gap: 7px;
        padding: 40px 20px;
        color: var(--dt-sub);
      }
      .dt-errorcard ha-icon { --mdc-icon-size: 38px; color: #dc2626; }
      .dt-error-title { font-size: 15px; font-weight: 650; color: var(--dt-text); }
      .dt-error-text { font-size: 12.5px; line-height: 1.5; max-width: 300px; margin-bottom: 8px; }

      /* ---------------- calendar popover ---------------- */
      .dt-calpop {
        position: fixed;
        z-index: 1200;
        padding: 10px;
        border-radius: 18px;
        background: var(--dt-card);
        border: 1px solid var(--dt-divider);
        box-shadow: 0 18px 50px rgba(15, 23, 42, 0.22);
        color: var(--dt-text);
      }
      .dt-calpop[hidden] { display: none; }

      /* ---------------- places / POI search ---------------- */
      .dt-placespop {
        position: fixed;
        z-index: 1300;
        top: 72px;
        right: 16px;
        width: min(440px, calc(100vw - 24px));
        max-height: min(70vh, 640px);
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 12px;
        border-radius: 18px;
        background: var(--dt-card);
        border: 1px solid var(--dt-divider);
        box-shadow: 0 18px 50px rgba(15, 23, 42, 0.22);
        color: var(--dt-text);
      }
      .dt-placespop[hidden] { display: none; }
      .dt-placeshead {
        display: flex; align-items: center; justify-content: space-between;
      }
      .dt-placestitle {
        display: flex; align-items: center; gap: 8px;
        font-weight: 700; font-size: 15px;
      }
      .dt-placesrow { display: flex; gap: 8px; }
      .dt-placesrow .dt-input { flex: 1 1 auto; min-width: 0; }
      .dt-placesrow .dt-btn { flex: 0 0 auto; }
      .dt-placeshint {
        font-size: 11.5px; color: var(--dt-sub); line-height: 1.4;
      }
      .dt-placeslist {
        display: flex; flex-direction: column; gap: 6px;
        overflow-y: auto; min-height: 40px;
      }
      .dt-placesloading,
      .dt-placesempty {
        display: flex; align-items: center; gap: 8px;
        padding: 14px 8px; color: var(--dt-sub); font-size: 13px;
      }
      .dt-placeresult {
        display: flex; align-items: stretch; gap: 4px;
        border: 1px solid var(--dt-divider);
        border-radius: 12px;
        background: color-mix(in srgb, var(--dt-primary) 4%, transparent);
      }
      .dt-placeresult-main {
        flex: 1 1 auto; min-width: 0;
        display: flex; flex-direction: column; gap: 2px;
        padding: 9px 10px;
        border: 0; background: transparent; color: inherit;
        text-align: left; cursor: pointer;
        font: inherit;
      }
      .dt-placeresult-main:hover {
        background: color-mix(in srgb, var(--dt-primary) 8%, transparent);
      }
      .dt-placeresult-name {
        font-weight: 650; font-size: 13.5px;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .dt-placeresult-sub {
        font-size: 11.5px; color: var(--dt-sub);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .dt-placeresult-meta {
        display: flex; flex-wrap: wrap; gap: 8px;
        margin-top: 3px; font-size: 11.5px; color: var(--dt-sub);
      }
      .dt-placecount {
        font-weight: 700;
        color: var(--dt-confirmed);
      }
      .dt-placesave {
        width: 38px; flex: 0 0 38px;
        border-radius: 0 12px 12px 0;
      }
      .dt-placesave[disabled] { opacity: 0.45; cursor: default; }
      .dt-placesbtn { flex: 0 0 auto; }

      .dt-placesexport {
        display: flex; align-items: center; gap: 6px;
        padding-top: 8px;
        border-top: 1px solid var(--dt-divider);
      }
      .dt-exportlabel {
        display: inline-flex; align-items: center; gap: 4px;
        font-size: 11.5px; font-weight: 600; color: var(--dt-sub);
        white-space: nowrap;
      }
      .dt-exportlabel ha-icon { --mdc-icon-size: 16px; }
      .dt-placesexport .dt-exportrange {
        flex: 1 1 auto; min-width: 0; padding: 6px 8px; font-size: 12px;
      }
      .dt-placesexport .dt-btn {
        padding: 6px 9px; font-size: 11.5px; flex: 0 0 auto;
      }
      .dt-placescontacts {
        display: flex; align-items: center; gap: 6px;
        padding-top: 8px;
        border-top: 1px solid var(--dt-divider);
      }
      .dt-placescontacts .dt-btn {
        padding: 6px 9px; font-size: 11.5px; flex: 0 0 auto;
      }
      .dt-contactstatus {
        font-size: 11.5px; color: var(--dt-sub);
        margin-left: auto; white-space: nowrap;
      }
      .dt-placesimport {
        display: flex; align-items: center; gap: 6px;
        padding-top: 8px;
        border-top: 1px solid var(--dt-divider);
      }
      .dt-placesimport .dt-btn {
        padding: 6px 9px; font-size: 11.5px; flex: 0 0 auto;
      }
      .dt-importstatus {
        font-size: 11.5px; color: var(--dt-sub);
        margin-left: auto; white-space: nowrap;
        overflow: hidden; text-overflow: ellipsis;
      }

      .dt-cal-head {
        display: flex; align-items: center; justify-content: space-between;
        padding: 2px 2px 8px;
      }
      .dt-cal-title { font-size: 14.5px; font-weight: 700; }
      .dt-cal-head .dt-iconbtn { width: 32px; height: 32px; flex-basis: 32px; }
      .dt-cal-head ha-icon { --mdc-icon-size: 20px; }

      .dt-cal-weekdays {
        display: grid; grid-template-columns: repeat(7, 1fr);
        padding: 2px 0 4px;
        color: var(--dt-sub);
        font-size: 10.5px; font-weight: 600;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 0.3px;
      }

      .dt-cal-grid {
        display: grid; grid-template-columns: repeat(7, 1fr);
        gap: 2px;
      }
      .dt-cal-day {
        position: relative;
        height: 38px;
        border: 0; border-radius: 10px;
        background: transparent; color: var(--dt-text);
        font: inherit; font-size: 12.5px;
        cursor: pointer;
        display: flex; align-items: center; justify-content: center;
      }
      .dt-cal-day:hover:not(:disabled) { background: color-mix(in srgb, var(--dt-text) 7%, transparent); }
      .dt-cal-day:disabled { color: var(--dt-sub); opacity: 0.35; cursor: default; }
      .dt-cal-empty { visibility: hidden; }
      .dt-cal-today { font-weight: 800; color: var(--dt-primary); }
      .dt-cal-selected {
        background: var(--dt-primary) !important;
        color: #fff !important;
        font-weight: 700;
        box-shadow: 0 2px 6px color-mix(in srgb, var(--dt-primary) 35%, transparent);
      }
      .dt-cal-selected .dt-cal-dot { background: #fff; }
      .dt-cal-dot {
        position: absolute; bottom: 5px; left: 50%;
        transform: translateX(-50%);
        width: 4px; height: 4px; border-radius: 50%;
        background: var(--dt-primary);
      }

      .dt-cal-foot {
        display: flex; align-items: center; justify-content: space-between;
        gap: 10px;
        padding: 9px 2px 1px;
        border-top: 1px solid var(--dt-divider);
        margin-top: 6px;
      }
      .dt-cal-hint {
        display: inline-flex; align-items: center; gap: 6px;
        color: var(--dt-sub); font-size: 10.5px;
      }
      .dt-cal-hint .dt-cal-dot { position: static; transform: none; }
      .dt-cal-todaybtn {
        border: 0; background: transparent; color: var(--dt-primary);
        font: inherit; font-size: 12px; font-weight: 700;
        cursor: pointer; padding: 4px 6px; border-radius: 8px;
      }
      .dt-cal-todaybtn:hover { background: var(--dt-primary-soft); }

      /* ---------------- modal ---------------- */
      .dt-modal {
        position: fixed; inset: 0; z-index: 2000;
        display: flex; align-items: center; justify-content: center;
        padding: 20px;
      }
      .dt-modal[hidden] { display: none; }
      .dt-modal-backdrop {
        position: absolute; inset: 0;
        background: rgba(15, 23, 42, 0.55);
        backdrop-filter: blur(3px);
        animation: dt-fade 0.18s ease-out;
      }
      @keyframes dt-fade { from { opacity: 0; } to { opacity: 1; } }

      .dt-dialog {
        position: relative;
        z-index: 1;
        width: min(520px, 100%);
        max-height: min(86vh, 720px);
        display: flex; flex-direction: column;
        background: var(--dt-card);
        border-radius: 22px;
        box-shadow: 0 24px 70px rgba(15, 23, 42, 0.35);
        overflow: hidden;
        animation: dt-pop-in 0.2s cubic-bezier(0.2, 0.9, 0.3, 1);
      }
      @keyframes dt-pop-in {
        from { opacity: 0; transform: translateY(14px) scale(0.98); }
        to { opacity: 1; transform: translateY(0) scale(1); }
      }

      .dt-dlg-head {
        display: flex; align-items: flex-start; justify-content: space-between;
        gap: 12px;
        padding: 18px 18px 10px;
      }
      .dt-dlg-head h2 {
        margin: 0; font-size: 18px; font-weight: 700;
        letter-spacing: -0.2px;
      }
      .dt-dlg-sub { margin-top: 3px; color: var(--dt-sub); font-size: 12.5px; }

      .dt-dlg-body {
        padding: 6px 18px 18px;
        overflow-y: auto;
      }

      .dt-label {
        display: block;
        margin: 14px 0 6px;
        color: var(--dt-sub);
        font-size: 11.5px; font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.4px;
      }
      .dt-label:first-child { margin-top: 0; }

      .dt-input {
        width: 100%; height: 44px;
        padding: 0 13px;
        border: 1px solid var(--dt-divider); border-radius: 12px;
        background: var(--dt-bg); color: var(--dt-text);
        font: inherit; font-size: 14px;
        outline: none;
      }
      .dt-input:focus { border-color: var(--dt-primary); box-shadow: 0 0 0 3px var(--dt-primary-soft); }
      .dt-hint { margin-top: 5px; color: var(--dt-sub); font-size: 11.5px; line-height: 1.4; }

      .dt-select {
        appearance: none;
        padding-right: 36px;
        background-image: linear-gradient(45deg, transparent 50%, var(--dt-sub) 50%),
          linear-gradient(135deg, var(--dt-sub) 50%, transparent 50%);
        background-position: calc(100% - 18px) 19px, calc(100% - 13px) 19px;
        background-size: 5px 5px, 5px 5px;
        background-repeat: no-repeat;
      }
      .dt-textarea {
        height: auto;
        min-height: 82px;
        padding: 10px 13px;
        line-height: 1.45;
        resize: vertical;
      }
      .dt-merged-hint {
        display: flex;
        align-items: center;
        gap: 7px;
        margin-top: 14px;
        padding: 9px 11px;
        border-radius: 10px;
        background: var(--dt-primary-soft);
        color: var(--dt-primary);
        font-size: 12px;
      }
      .dt-merged-hint ha-icon { --mdc-icon-size: 16px; }

      .dt-combo { position: relative; }

      .dt-combobtn {
        width: 100%; height: 44px;
        display: flex; align-items: center; justify-content: space-between; gap: 10px;
        padding: 0 13px;
        border: 1px solid var(--dt-divider); border-radius: 12px;
        background: var(--dt-bg); color: var(--dt-text);
        font: inherit; font-size: 14px; text-align: left;
        cursor: pointer;
      }
      .dt-combobtn:hover { border-color: var(--dt-primary); }
      .dt-combobtn:disabled { cursor: wait; opacity: 0.7; }
      .dt-combotext { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .dt-combobtn ha-icon { --mdc-icon-size: 20px; color: var(--dt-sub); flex: 0 0 20px; }

      .dt-compopop {
        position: relative; z-index: 20;
        margin-top: 6px;
        border-radius: 14px;
        background: var(--dt-card);
        border: 1px solid var(--dt-divider);
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.16);
        overflow: hidden;
      }
      .dt-compopop[hidden] { display: none; }

      .dt-combosearch {
        display: flex; align-items: center; gap: 8px;
        padding: 10px 12px;
        border-bottom: 1px solid var(--dt-divider);
      }
      .dt-combosearch ha-icon { --mdc-icon-size: 20px; color: var(--dt-sub); }
      .dt-combosearch input {
        flex: 1; min-width: 0;
        border: 0; background: transparent; color: var(--dt-text);
        font: inherit; font-size: 14px; outline: none;
      }

      .dt-combolist { max-height: 260px; overflow-y: auto; padding: 5px; }

      .dt-place-option {
        width: 100%;
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
        padding: 10px 10px;
        border: 0; border-radius: 9px;
        background: transparent; color: var(--dt-text);
        font: inherit; font-size: 13.5px; text-align: left;
        cursor: pointer;
      }
      .dt-place-option:hover { background: color-mix(in srgb, var(--dt-text) 6%, transparent); }
      .dt-place-selected { background: var(--dt-primary-soft); color: var(--dt-primary); font-weight: 600; }
      .dt-place-selected:hover { background: var(--dt-primary-soft); }
      .dt-place-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .dt-place-meta {
        flex: 0 0 auto;
        color: var(--dt-sub); font-size: 11.5px;
        display: inline-flex; align-items: center; gap: 5px;
      }
      .dt-place-selected .dt-place-meta { color: var(--dt-primary); }
      .dt-place-meta ha-icon { --mdc-icon-size: 17px; }
      .dt-combohint {
        padding: 0 14px 12px;
        text-align: center;
        color: var(--dt-sub);
        font-size: 12px;
        line-height: 1.45;
      }
      .dt-comboempty, .dt-comboloading {
        padding: 18px 12px; text-align: center;
        color: var(--dt-sub); font-size: 12.5px;
        display: flex; align-items: center; justify-content: center; gap: 8px;
      }

      .dt-split {
        margin-top: 14px;
        padding-top: 12px;
        border-top: 1px solid var(--dt-divider);
      }
      .dt-splitrange {
        width: 100%;
        margin: 6px 0 2px;
        accent-color: var(--dt-primary);
      }
      .dt-splitmeta {
        font-size: 12px;
        color: var(--dt-sub);
      }
      .dt-splitactions {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 8px;
      }
      .dt-splitactions .dt-btn {
        flex: 1 1 180px;
        font-size: 12px;
        padding: 8px 10px;
      }
      .dt-dlg-actions {
        display: flex; align-items: center; gap: 8px;
        padding: 13px 18px;
        border-top: 1px solid var(--dt-divider);
        background: color-mix(in srgb, var(--dt-bg) 48%, var(--dt-card));
      }

      /* ---------------- toasts ---------------- */
      .dt-toasts {
        position: fixed; z-index: 3000;
        left: 50%; bottom: 22px;
        transform: translateX(-50%);
        display: flex; flex-direction: column; align-items: center; gap: 8px;
        pointer-events: none;
        width: max-content; max-width: calc(100vw - 32px);
      }
      .dt-toast {
        display: flex; align-items: center; gap: 8px;
        padding: 10px 15px;
        border-radius: 999px;
        background: rgba(17, 24, 39, 0.94);
        color: #fff;
        font-size: 13px; font-weight: 500;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.3);
        animation: dt-toast-in 0.22s ease-out;
      }
      .dt-toast ha-icon { --mdc-icon-size: 19px; color: #4ade80; }
      .dt-toast-error ha-icon { color: #f87171; }
      .dt-toast-out { opacity: 0; transform: translateY(6px); transition: all 0.22s ease; }
      @keyframes dt-toast-in {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
      }

      /* ---------------- map internals ---------------- */
      .dt-map .leaflet-control-zoom {
        border: 0 !important;
        border-radius: 12px !important;
        overflow: hidden;
        box-shadow: var(--dt-shadow) !important;
      }
      .dt-map .leaflet-control-zoom a {
        width: 38px !important; height: 38px !important; line-height: 38px !important;
        background: color-mix(in srgb, var(--dt-card) 94%, transparent) !important;
        color: var(--dt-text) !important;
        border-color: var(--dt-divider) !important;
        font-size: 20px !important;
        backdrop-filter: blur(8px);
      }
      .dt-map .leaflet-control-zoom a:hover { background: var(--dt-card) !important; }
      .dt-map .leaflet-control-attribution {
        font-size: 9px !important;
        background: color-mix(in srgb, var(--dt-card) 78%, transparent) !important;
        color: var(--dt-sub) !important;
        padding: 1px 5px !important;
      }
      .dt-map .leaflet-control-attribution a { color: var(--dt-sub) !important; }

      .dt-visit-marker { background: transparent; border: 0; }
      .dt-pin {
        width: 32px; height: 32px;
        display: flex; align-items: center; justify-content: center;
        border-radius: 50%;
        border: 2.5px solid #fff;
        color: #fff;
        background: var(--dt-confirmed);
        box-shadow: 0 3px 10px rgba(15, 23, 42, 0.4);
        transition: transform 0.15s ease;
      }
      .dt-pin svg { width: 18px; height: 18px; fill: currentColor; }
      .dt-pin-suggested { background: var(--dt-suggested); }
      .dt-pin-confirmed { background: var(--dt-confirmed); }
      .dt-pin-home { background: var(--dt-primary); }
      .dt-pin-home svg { width: 17px; height: 17px; }
      .dt-visit-marker:hover .dt-pin { transform: scale(1.12); }

      .dt-mode-marker { background: transparent; border: 0; }
      .dt-mode-marker-inner {
        width: 28px; height: 28px;
        display: flex; align-items: center; justify-content: center;
        border-radius: 50%;
        background: color-mix(in srgb, var(--dt-card) 96%, transparent);
        border: 2px solid var(--mode-color, #94a3b8);
        box-shadow: 0 2px 7px rgba(15, 23, 42, 0.3);
        font-size: 13px;
        line-height: 1;
      }

      .dt-arrow-marker { background: transparent; border: 0; }
      .dt-arrow {
        width: 14px; height: 14px;
        display: flex; align-items: center; justify-content: center;
        filter: drop-shadow(0 1px 1px rgba(15, 23, 42, 0.35));
      }
      .dt-arrow svg { width: 14px; height: 14px; display: block; }

      .dt-popup .leaflet-popup-content-wrapper {
        border-radius: 12px;
        background: var(--dt-card);
        color: var(--dt-text);
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.25);
      }
      .dt-popup .leaflet-popup-content { margin: 10px 12px; line-height: 1.35; }
      .dt-popup .leaflet-popup-tip { background: var(--dt-card); }
      .dt-pop-title { font-size: 13px; font-weight: 700; }
      .dt-pop-sub { margin-top: 3px; font-size: 11.5px; color: var(--dt-sub); }

      /* ---------------- responsive ---------------- */
      @media (max-width: 980px) {
        .dt-main { grid-template-columns: minmax(0, 1fr) 380px; }
      }

      @media (max-width: 820px) {
        .dt-topbar {
          flex-wrap: wrap;
          gap: 6px 8px;
          padding: 8px 10px;
        }
        .dt-brand-sub { display: none; }
        .dt-brand { flex: 1 1 auto; }
        .dt-brand-icon { width: 34px; height: 34px; flex-basis: 34px; border-radius: 10px; }
        .dt-title { font-size: 17px; }
        .dt-datenav { order: 3; width: 100%; justify-content: center; margin-left: 0; }
        .dt-spacer { display: none; }
        .dt-placesbtn { margin-left: auto; }
        .dt-refresh { margin-left: 0; }
        .dt-datebtn { flex: 0 1 auto; min-width: 0; }
        .dt-datelabel { overflow: hidden; text-overflow: ellipsis; }
        .dt-todaybtn { display: none; }

        .dt-main {
          grid-template-columns: 1fr;
          grid-template-rows: var(--dt-map-h, 40vh) minmax(0, 1fr);
        }
        .dt-side { border-left: 0; border-top: 1px solid var(--dt-divider); }

        .dt-resizer {
          display: flex; align-items: center; justify-content: center;
          flex: 0 0 24px;
          height: 24px;
          margin-top: -1px;
          background: var(--dt-bg);
          border-bottom: 1px solid var(--dt-divider);
          cursor: ns-resize;
          touch-action: none;
          outline: none;
        }
        .dt-resizer span {
          width: 46px; height: 5px;
          border-radius: 999px;
          background: var(--dt-divider);
          transition: background 0.15s ease, width 0.15s ease;
        }
        .dt-resizer:hover span,
        .dt-resizer.dt-dragging span { background: var(--dt-primary); width: 58px; }
        .dt-resizer:focus-visible { box-shadow: inset 0 0 0 2px var(--dt-primary); }
        .dt-sidehead { padding: 12px 14px 6px; }
        .dt-daytitle { font-size: 14px; margin-bottom: 8px; }
        .dt-summary { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; }
        .dt-summary::-webkit-scrollbar { display: none; }
        .dt-list { padding: 0 10px 24px; }
        .dt-legend { max-width: 72%; bottom: 22px; }
        .dt-map-badge { left: 54px; font-size: 12px; }

        .dt-placespop {
          top: 8px; right: 8px; left: 8px;
          width: auto;
          max-height: calc(100vh - 16px);
        }
      }

      @media (max-width: 560px) {
        .dt-modal { padding: 0; align-items: flex-end; }
        .dt-dialog {
          width: 100%;
          max-height: 90vh;
          border-radius: 22px 22px 0 0;
        }
        .dt-entry-title { font-size: 14px; }
        .dt-actions .dt-btn { flex: 1; }
        .dt-legend { display: none; }
      }

      @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
          animation-duration: 0.001ms !important;
          animation-iteration-count: 1 !important;
          transition-duration: 0.001ms !important;
        }
      }
    `;
  }
}

if (!customElements.get("geopulse-card")) {
  customElements.define("geopulse-card", GeoPulseCard);
}

console.info(
  `%c GEOPULSE %c ${CARD_VERSION} `,
  "color:white;background:#0ea5e9;font-weight:700;border-radius:4px 0 0 4px;padding:2px 6px",
  "color:#0ea5e9;background:#e0f2fe;font-weight:700;border-radius:0 4px 4px 0;padding:2px 6px"
);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "geopulse-card",
  name: "GeoPulse",
  description: "Google Timeline-achtige dagweergave met kaart, ritten en bezoeken.",
  preview: false,
});
