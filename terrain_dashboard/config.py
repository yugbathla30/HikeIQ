from __future__ import annotations

from dataclasses import dataclass
from math import inf


APP_TITLE = "HikeIQ"
APP_SUBTITLE = "Analyze any hiking trail using high-resolution global terrain data."
PAGE_ICON = ":material/explore:"

BRAND_NAME = "HikeIQ"
APP_TAGLINE = "Hiking & Trek Difficulty Analyzer"

PRIMARY_BACKGROUND = "#08131F"
SECONDARY_SURFACE = "#101D2C"
CARD_SURFACE = "#162433"
ACCENT_GREEN = "#22C55E"
ACCENT_BLUE = "#3B82F6"
ACCENT_ORANGE = "#F59E0B"
DANGER = "#EF4444"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
BORDER_COLOR = "rgba(255,255,255,0.08)"

DEFAULT_LATITUDE = 39.7392
DEFAULT_LONGITUDE = -104.9903
DEFAULT_MAP_ZOOM = 10

DEFAULT_CACHE_DIR = ".cache/elevation_tiles"
DEFAULT_MAX_WORKERS = 8
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF = 1.0
DEFAULT_TIMEOUT = 30
DEFAULT_WEIGHT_KG = 78.0
DEFAULT_GENDER = "Prefer not to say"
DEFAULT_FITNESS_LEVEL = "recreational"
DEFAULT_THEME = "dark"
DEFAULT_UNITS = "metric"
DEFAULT_ACTIVE_PAGE = "Home"
DEFAULT_ROUTE_THEME = "Street"

MAP_TILES = "CartoDB positron"

DIFFICULTY_BANDS: tuple[tuple[int, str], ...] = (
    (25, "Easy"),
    (50, "Moderate"),
    (75, "Hard"),
    (100, "Extreme"),
)

TERRAIN_CLASS_THRESHOLDS = {
    "Flat": 0.0,
    "Gentle": 5.0,
    "Rolling": 12.0,
    "Steep": 20.0,
    "Very Steep": inf,
}


@dataclass(frozen=True)
class SteepnessRule:
    name: str
    max_slope_degrees: float
    color: str
    emoji: str
    description: str


STEEPNESS_RULES: tuple[SteepnessRule, ...] = (
    SteepnessRule("Flat", 2.0, "#2a9d8f", "🟢", "Almost level ground with minimal change in slope."),
    SteepnessRule("Gentle", 6.0, "#5aa469", "🟩", "Slight incline with smooth terrain."),
    SteepnessRule("Rolling", 12.0, "#e9c46a", "🟨", "Gentle undulations with moderate slope changes."),
    SteepnessRule("Hilly", 20.0, "#d08c60", "🟧", "Noticeable slopes that require more effort to traverse."),
    SteepnessRule("Steep", 35.0, "#c1121f", "🟥", "Steep local terrain with challenging movement."),
    SteepnessRule("Very Steep", inf, "#7b2cbf", "⛰️", "Extremely steep terrain such as cliffs, escarpments, or rugged mountain faces."),
)

STEEPNESS_ORDER = [rule.name for rule in STEEPNESS_RULES]

CARD_ACCENTS = {
    "elevation": "#2a9d8f",
    "slope": "#d08c60",
    "aspect": "#457b9d",
    "steepness": "#5aa469",
    "gradient": "#c77dff",
}

STEEPNESS_CHART_COLORS = [rule.color for rule in STEEPNESS_RULES]

ROUTE_THEME_OPTIONS = ["Street", "Terrain", "Satellite", "Dark", "Light"]
UNITS_OPTIONS = ["metric", "imperial"]
FITNESS_LEVEL_OPTIONS = ["recreational", "fit", "athletic"]
GENDER_OPTIONS = ["Prefer not to say", "Woman", "Man", "Non-binary"]
PAGE_OPTIONS = ["Home", "Trail analysis", "History", "Settings", "About"]

TerrainRule = SteepnessRule
TERRAIN_RULES = STEEPNESS_RULES
TERRAIN_ORDER = STEEPNESS_ORDER
CHART_COLORS = STEEPNESS_CHART_COLORS
