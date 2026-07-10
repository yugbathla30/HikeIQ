from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from global_elevation_enrichment import enrich_with_global_elevation

from terrain_dashboard.utils import add_terrain_steepness_columns, classify_terrain_steepness


@dataclass(frozen=True)
class TerrainObservation:
    latitude: float
    longitude: float
    elevation_m: float | None
    slope_degrees: float | None
    slope_percent: float | None
    aspect_degrees: float | None
    aspect_direction: str | None
    terrain_steepness: str
    terrain_steepness_color: str
    terrain_steepness_emoji: str
    terrain_steepness_description: str


def lookup_coordinate(
    latitude: float,
    longitude: float,
    cache_dir: str | None = None,
    max_workers: int = 1,
    max_retries: int = 3,
    retry_backoff: float = 1.0,
    timeout: int = 30,
) -> TerrainObservation:
    """Resolve one coordinate into a terrain observation."""

    df = pd.DataFrame([{"latitude": latitude, "longitude": longitude}])
    enriched = enrich_with_global_elevation(
        df,
        cache_dir=cache_dir,
        max_workers=max_workers,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        timeout=timeout,
    )
    row = enriched.iloc[0]
    classification = classify_terrain_steepness(row.get("slope_degrees"))
    return TerrainObservation(
        latitude=float(latitude),
        longitude=float(longitude),
        elevation_m=None if pd.isna(row.get("elevation_m")) else float(row["elevation_m"]),
        slope_degrees=None if pd.isna(row.get("slope_degrees")) else float(row["slope_degrees"]),
        slope_percent=None if pd.isna(row.get("slope_percent")) else float(row["slope_percent"]),
        aspect_degrees=None if pd.isna(row.get("aspect_degrees")) else float(row["aspect_degrees"]),
        aspect_direction=None if pd.isna(row.get("aspect_direction")) else str(row["aspect_direction"]),
        terrain_steepness=classification.name,
        terrain_steepness_color=classification.color,
        terrain_steepness_emoji=classification.emoji,
        terrain_steepness_description=classification.description,
    )


def enrich_batch_dataframe(
    df: pd.DataFrame,
    cache_dir: str | None = None,
    max_workers: int = 8,
    max_retries: int = 3,
    retry_backoff: float = 1.0,
    timeout: int = 30,
) -> pd.DataFrame:
    """Enrich an uploaded dataframe and append terrain classifications."""

    enriched = enrich_with_global_elevation(
        df,
        cache_dir=cache_dir,
        max_workers=max_workers,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        timeout=timeout,
    )
    return add_terrain_steepness_columns(enriched)


TerrainObservation.terrain_class = property(lambda self: self.terrain_steepness)  # type: ignore[attr-defined]
TerrainObservation.terrain_color = property(lambda self: self.terrain_steepness_color)  # type: ignore[attr-defined]
TerrainObservation.terrain_emoji = property(lambda self: self.terrain_steepness_emoji)  # type: ignore[attr-defined]
TerrainObservation.terrain_description = property(lambda self: self.terrain_steepness_description)  # type: ignore[attr-defined]
