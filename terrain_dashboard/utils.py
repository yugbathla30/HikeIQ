from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import pandas as pd

from terrain_dashboard.config import STEEPNESS_ORDER, STEEPNESS_RULES


@dataclass(frozen=True)
class TerrainSteepnessClassification:
    name: str
    color: str
    emoji: str
    description: str


COMPASS_EMOJI = {
    "N": "⬆️",
    "NE": "↗️",
    "E": "➡️",
    "SE": "↘️",
    "S": "⬇️",
    "SW": "↙️",
    "W": "⬅️",
    "NW": "↖️",
}


def hash_bytes(data: bytes) -> str:
    """Return a stable hash for uploaded file caching."""

    return hashlib.sha256(data).hexdigest()


def is_valid_coordinate(latitude: float | int | None, longitude: float | int | None) -> bool:
    """Validate a latitude/longitude pair."""

    if latitude is None or longitude is None:
        return False
    if pd.isna(latitude) or pd.isna(longitude):
        return False
    return -90.0 <= float(latitude) <= 90.0 and -180.0 <= float(longitude) <= 180.0


def format_coordinate(latitude: float, longitude: float) -> str:
    """Format a coordinate pair for display."""

    return f"{latitude:.5f}, {longitude:.5f}"


def format_number(value: float | int | None, precision: int = 1, suffix: str = "") -> str:
    """Format a numeric value while preserving missing values."""

    if value is None or pd.isna(value):
        return "--"
    return f"{float(value):.{precision}f}{suffix}"


def aspect_compass_icon(direction: str | None) -> str:
    """Return an arrow icon that matches a compass direction."""

    if not direction:
        return "❔"
    return COMPASS_EMOJI.get(direction.upper(), "❔")


def classify_terrain_steepness(slope_degrees: float | int | None) -> TerrainSteepnessClassification:
    """Classify local terrain steepness from slope degrees using the dashboard rules."""

    if slope_degrees is None or pd.isna(slope_degrees):
        return TerrainSteepnessClassification("Unknown", "#6c757d", "❔", "Local terrain steepness is unavailable.")

    slope_value = float(slope_degrees)
    for rule in STEEPNESS_RULES:
        if slope_value < rule.max_slope_degrees:
            return TerrainSteepnessClassification(rule.name, rule.color, rule.emoji, rule.description)

    last_rule = STEEPNESS_RULES[-1]
    return TerrainSteepnessClassification(last_rule.name, last_rule.color, last_rule.emoji, last_rule.description)


def add_terrain_steepness_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add local terrain steepness metadata columns to an enriched dataframe."""

    result = df.copy()
    classifications = result["slope_degrees"].apply(classify_terrain_steepness)
    result["terrain_steepness"] = classifications.map(lambda item: item.name)
    result["terrain_steepness_color"] = classifications.map(lambda item: item.color)
    result["terrain_steepness_emoji"] = classifications.map(lambda item: item.emoji)
    result["terrain_steepness_description"] = classifications.map(lambda item: item.description)
    return result


def compute_terrain_statistics(df: pd.DataFrame) -> dict[str, Any]:
    """Compute the dashboard statistics from an enriched dataframe."""

    stats: dict[str, Any] = {}
    valid = df[df["elevation_m"].notna()].copy()
    valid_slope = valid[valid["slope_degrees"].notna()].copy()

    stats["average_elevation"] = float(valid["elevation_m"].mean()) if not valid.empty else None
    stats["maximum_elevation"] = float(valid["elevation_m"].max()) if not valid.empty else None
    stats["minimum_elevation"] = float(valid["elevation_m"].min()) if not valid.empty else None
    stats["average_slope"] = float(valid_slope["slope_degrees"].mean()) if not valid_slope.empty else None
    stats["highest_slope"] = float(valid_slope["slope_degrees"].max()) if not valid_slope.empty else None

    if "terrain_steepness" in df.columns:
        terrain_counts = df["terrain_steepness"].value_counts().reindex(STEEPNESS_ORDER, fill_value=0)
    else:
        terrain_counts = pd.Series(dtype=int, index=STEEPNESS_ORDER)

    stats["terrain_steepness_distribution"] = terrain_counts
    return stats


def ensure_required_columns(df: pd.DataFrame) -> list[str]:
    """Return a list of missing required coordinate columns."""

    required = ["latitude", "longitude"]
    return [column for column in required if column not in df.columns]


def has_ocean_like_result(elevation_m: float | int | None, slope_degrees: float | int | None) -> bool:
    """Best-effort flag for ocean or no-data style fallback results."""

    if elevation_m is None or slope_degrees is None:
        return False
    if pd.isna(elevation_m) or pd.isna(slope_degrees):
        return False
    return float(elevation_m) == 0.0 and float(slope_degrees) == 0.0


TerrainClassification = TerrainSteepnessClassification
classify_terrain = classify_terrain_steepness
add_terrain_columns = add_terrain_steepness_columns
