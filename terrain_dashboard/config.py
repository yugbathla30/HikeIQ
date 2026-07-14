from __future__ import annotations

from dataclasses import dataclass
from math import inf


APP_TITLE = "HikeIQ"
APP_SUBTITLE = "Analyze any hiking trail using high-resolution global terrain data."
PAGE_ICON = ":material/explore:"

BRAND_NAME = "HikeIQ"
APP_TAGLINE = "Hiking & Trek Difficulty Analyzer"

PRIMARY_DARK = "#2E0219"
BACKGROUND_LIGHT = "#F0DFAD"
PRIMARY_ACCENT = "#F564A9"
SECONDARY_ACCENT = "#FAA4BD"
SECONDARY_DARK = "#712F79"

PRIMARY_BACKGROUND = BACKGROUND_LIGHT
SECONDARY_SURFACE = "#f8ecd0"
CARD_SURFACE = "rgba(255, 255, 255, 0.7)"
ACCENT_GREEN = PRIMARY_ACCENT
ACCENT_BLUE = SECONDARY_DARK
ACCENT_ORANGE = SECONDARY_ACCENT
DANGER = PRIMARY_DARK
TEXT_PRIMARY = PRIMARY_DARK
TEXT_SECONDARY = "#5d4a63"
BORDER_COLOR = "rgba(46, 2, 25, 0.14)"

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
DEFAULT_UNITS = "metric"
DEFAULT_ACTIVE_PAGE = "Home"

MAP_TILES = "CartoDB positron"
ROUTE_COLORS = [PRIMARY_ACCENT, SECONDARY_DARK, SECONDARY_ACCENT, PRIMARY_DARK]

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
    SteepnessRule("Flat", 2.0, SECONDARY_ACCENT, "🟢", "Almost level ground with minimal change in slope."),
    SteepnessRule("Gentle", 6.0, PRIMARY_ACCENT, "🟩", "Slight incline with smooth terrain."),
    SteepnessRule("Rolling", 12.0, SECONDARY_DARK, "🟨", "Gentle undulations with moderate slope changes."),
    SteepnessRule("Hilly", 20.0, PRIMARY_DARK, "🟧", "Noticeable slopes that require more effort to traverse."),
    SteepnessRule("Steep", 35.0, "#a63d6f", "🟥", "Steep local terrain with challenging movement."),
    SteepnessRule("Very Steep", inf, SECONDARY_DARK, "⛰️", "Extremely steep terrain such as cliffs, escarpments, or rugged mountain faces."),
)

STEEPNESS_ORDER = [rule.name for rule in STEEPNESS_RULES]

CARD_ACCENTS = {
    "elevation": PRIMARY_ACCENT,
    "slope": SECONDARY_DARK,
    "aspect": SECONDARY_ACCENT,
    "steepness": PRIMARY_DARK,
    "gradient": "#a63d6f",
}

STEEPNESS_CHART_COLORS = [rule.color for rule in STEEPNESS_RULES]

UNITS_OPTIONS = ["metric", "imperial"]
FITNESS_LEVEL_OPTIONS = ["recreational", "fit", "athletic"]
GENDER_OPTIONS = ["Prefer not to say", "Woman", "Man", "Non-binary"]
PAGE_OPTIONS = ["Home", "Trail analysis", "History"]

TerrainRule = SteepnessRule
TERRAIN_RULES = STEEPNESS_RULES
TERRAIN_ORDER = STEEPNESS_ORDER
CHART_COLORS = STEEPNESS_CHART_COLORS
