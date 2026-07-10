from __future__ import annotations

from dataclasses import dataclass
from math import asin, atan, cos, degrees, radians, sin, sqrt

import pandas as pd

from terrain_dashboard.config import DIFFICULTY_BANDS, TERRAIN_CLASS_THRESHOLDS
from terrain_dashboard.utils import classify_terrain_steepness


@dataclass(frozen=True)
class RouteSegmentSummary:
    """Summary for a contiguous section of a route."""

    start_index: int
    end_index: int
    start_distance_km: float
    end_distance_km: float
    distance_km: float
    elevation_change_m: float
    gradient_percent: float


@dataclass(frozen=True)
class RouteAnalysis:
    """Computed metrics for a hiking route."""

    route_name: str
    source: str
    points: pd.DataFrame
    total_distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    maximum_elevation_m: float
    minimum_elevation_m: float
    average_elevation_m: float
    maximum_slope_degrees: float
    average_slope_degrees: float
    average_slope_percent: float
    difficulty_score: int
    difficulty_label: str
    hiking_time_hours: float
    running_time_hours: float
    trail_running_time_hours: float
    mountain_biking_time_hours: float
    calories_burned: int
    active_time_hours: float
    moving_time_hours: float
    terrain_breakdown: pd.DataFrame
    insights: list[str]
    longest_climb: RouteSegmentSummary | None
    longest_descent: RouteSegmentSummary | None
    steepest_section: RouteSegmentSummary | None
    highest_point: dict[str, float | int | str | None]
    lowest_point: dict[str, float | int | str | None]
    terrain_class_counts: pd.Series


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute geodesic distance using the haversine approximation."""

    radius_m = 6_371_000.0
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    start_lat = radians(lat1)
    end_lat = radians(lat2)

    a = sin(delta_lat / 2) ** 2 + cos(start_lat) * cos(end_lat) * sin(delta_lon / 2) ** 2
    return 2 * radius_m * asin(min(1.0, sqrt(a)))


def _segment_summary(frame: pd.DataFrame, segment_mask: pd.Series) -> RouteSegmentSummary | None:
    if not segment_mask.any():
        return None

    selected = frame.loc[segment_mask].copy()
    if selected.empty:
        return None

    start_index = int(selected.iloc[0]["point_index"])
    end_index = int(selected.iloc[-1]["point_index"])
    start_distance = float(selected.iloc[0]["cumulative_distance_km"])
    end_distance = float(selected.iloc[-1]["cumulative_distance_km"])
    distance = float(selected["segment_distance_km"].sum())
    elevation_change = float(selected["elevation_delta_m"].sum())
    gradient = float(selected["segment_gradient_percent"].mean()) if not selected["segment_gradient_percent"].isna().all() else 0.0

    return RouteSegmentSummary(
        start_index=start_index,
        end_index=end_index,
        start_distance_km=start_distance,
        end_distance_km=end_distance,
        distance_km=distance,
        elevation_change_m=elevation_change,
        gradient_percent=gradient,
    )


def _find_best_segment(frame: pd.DataFrame, ascending: bool) -> RouteSegmentSummary | None:
    deltas = frame["elevation_delta_m"] > 0 if ascending else frame["elevation_delta_m"] < 0
    if not deltas.any():
        return None

    groups = (deltas != deltas.shift(fill_value=False)).cumsum()
    grouped = frame.loc[deltas].groupby(groups[deltas], sort=False)
    ranked = grouped.agg(
        start_index=("point_index", "first"),
        end_index=("point_index", "last"),
        start_distance_km=("cumulative_distance_km", "first"),
        end_distance_km=("cumulative_distance_km", "last"),
        distance_km=("segment_distance_km", "sum"),
        elevation_change_m=("elevation_delta_m", "sum"),
        gradient_percent=("segment_gradient_percent", "mean"),
    )
    if ranked.empty:
        return None

    ordered = ranked.sort_values("distance_km", ascending=False)
    best = ordered.iloc[0]
    return RouteSegmentSummary(
        start_index=int(best["start_index"]),
        end_index=int(best["end_index"]),
        start_distance_km=float(best["start_distance_km"]),
        end_distance_km=float(best["end_distance_km"]),
        distance_km=float(best["distance_km"]),
        elevation_change_m=float(best["elevation_change_m"]),
        gradient_percent=float(best["gradient_percent"]),
    )


def _difficulty_label(score: int) -> str:
    for threshold, label in DIFFICULTY_BANDS:
        if score <= threshold:
            return label
    return DIFFICULTY_BANDS[-1][1]


def _estimate_hours(distance_km: float, ascent_m: float, pace_kmh: float, climb_penalty_m_per_hour: float) -> float:
    distance_component = distance_km / pace_kmh if pace_kmh > 0 else 0.0
    climb_component = ascent_m / climb_penalty_m_per_hour if climb_penalty_m_per_hour > 0 else 0.0
    return distance_component + climb_component


def _fitness_multiplier(fitness_level: str) -> float:
    mapping = {"recreational": 1.0, "fit": 0.92, "athletic": 0.84}
    return mapping.get(fitness_level, 1.0)


def _activity_met(activity: str) -> float:
    return {
        "hiking": 6.0,
        "running": 9.8,
        "trail running": 10.5,
        "mountain biking": 8.5,
    }.get(activity, 6.0)


def _calories_burned(weight_kg: float, activity_hours: float, activity: str, fitness_level: str) -> int:
    met = _activity_met(activity) * _fitness_multiplier(fitness_level)
    return int(round(met * weight_kg * max(activity_hours, 0.0)))


def _terrain_breakdown(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    classes = frame["slope_degrees"].apply(lambda slope: classify_terrain_steepness(slope).name)
    counts = classes.value_counts().reindex(TERRAIN_CLASS_THRESHOLDS.keys(), fill_value=0)
    total = float(counts.sum()) or 1.0
    breakdown = pd.DataFrame(
        {
            "terrain_class": counts.index,
            "count": counts.values,
            "share": (counts.values / total) * 100.0,
        }
    )
    return breakdown, counts


def _gradient_degrees(gradient_percent: float) -> float:
    return degrees(atan(gradient_percent / 100.0))


def analyze_route(
    route_name: str,
    source: str,
    points: pd.DataFrame,
    *,
    weight_kg: float,
    gender: str,
    fitness_level: str,
) -> RouteAnalysis:
    """Compute hiking, terrain, difficulty, and energy metrics for a route."""

    del gender

    frame = points.copy().reset_index(drop=True)
    frame["segment_distance_m"] = 0.0
    frame["segment_distance_km"] = 0.0
    frame["cumulative_distance_km"] = 0.0
    frame["elevation_delta_m"] = 0.0
    frame["segment_gradient_percent"] = 0.0
    frame["segment_gradient_degrees"] = 0.0

    if len(frame) >= 2:
        for index in range(1, len(frame)):
            prev_row = frame.iloc[index - 1]
            current_row = frame.iloc[index]
            distance_m = haversine_distance_m(
                float(prev_row["latitude"]),
                float(prev_row["longitude"]),
                float(current_row["latitude"]),
                float(current_row["longitude"]),
            )
            frame.at[index, "segment_distance_m"] = distance_m
            frame.at[index, "segment_distance_km"] = distance_m / 1000.0
            frame.at[index, "cumulative_distance_km"] = frame.at[index - 1, "cumulative_distance_km"] + (distance_m / 1000.0)

            if pd.notna(prev_row.get("elevation_m")) and pd.notna(current_row.get("elevation_m")):
                elevation_delta = float(current_row["elevation_m"]) - float(prev_row["elevation_m"])
                frame.at[index, "elevation_delta_m"] = elevation_delta
                gradient_percent = (elevation_delta / distance_m) * 100.0 if distance_m > 0 else 0.0
                frame.at[index, "segment_gradient_percent"] = gradient_percent
                frame.at[index, "segment_gradient_degrees"] = _gradient_degrees(gradient_percent)

    valid_elevation = frame[frame["elevation_m"].notna()].copy()
    valid_slope = frame[frame["slope_degrees"].notna()].copy()

    total_distance_km = float(frame["segment_distance_km"].sum())
    elevation_gain_m = float(frame.loc[frame["elevation_delta_m"] > 0, "elevation_delta_m"].sum())
    elevation_loss_m = float(abs(frame.loc[frame["elevation_delta_m"] < 0, "elevation_delta_m"].sum()))
    maximum_elevation_m = float(valid_elevation["elevation_m"].max()) if not valid_elevation.empty else 0.0
    minimum_elevation_m = float(valid_elevation["elevation_m"].min()) if not valid_elevation.empty else 0.0
    average_elevation_m = float(valid_elevation["elevation_m"].mean()) if not valid_elevation.empty else 0.0
    maximum_slope_degrees = float(valid_slope["slope_degrees"].max()) if not valid_slope.empty else 0.0
    average_slope_degrees = float(valid_slope["slope_degrees"].mean()) if not valid_slope.empty else 0.0
    average_slope_percent = float(valid_slope["slope_percent"].mean()) if not valid_slope.empty else 0.0

    difficulty_score = int(
        round(
            min(
                100.0,
                (
                    min(total_distance_km / 25.0, 1.0) * 0.18
                    + min(elevation_gain_m / 1400.0, 1.0) * 0.34
                    + min(maximum_slope_degrees / 40.0, 1.0) * 0.26
                    + min(abs(average_slope_degrees) / 15.0, 1.0) * 0.22
                )
                * 100.0,
            )
        )
    )
    difficulty_label = _difficulty_label(difficulty_score)

    hiking_time_hours = _estimate_hours(total_distance_km, elevation_gain_m, pace_kmh=4.8, climb_penalty_m_per_hour=550.0)
    running_time_hours = _estimate_hours(total_distance_km, elevation_gain_m, pace_kmh=9.5, climb_penalty_m_per_hour=1_100.0)
    trail_running_time_hours = _estimate_hours(total_distance_km, elevation_gain_m, pace_kmh=11.0, climb_penalty_m_per_hour=1_250.0)
    mountain_biking_time_hours = _estimate_hours(total_distance_km, elevation_gain_m, pace_kmh=14.0, climb_penalty_m_per_hour=1_500.0)

    active_time_hours = hiking_time_hours * 1.12
    moving_time_hours = hiking_time_hours * 0.92
    calories_burned = _calories_burned(weight_kg, active_time_hours, "hiking", fitness_level)

    terrain_breakdown, terrain_counts = _terrain_breakdown(frame)

    longest_climb = _find_best_segment(frame, ascending=True)
    longest_descent = _find_best_segment(frame, ascending=False)
    steepest_section = None
    if frame["segment_gradient_percent"].abs().max() > 0:
        steepest_index = frame["segment_gradient_percent"].abs().idxmax()
        steepest_section = _segment_summary(frame, frame.index.isin([steepest_index]))

    high_point_index = int(valid_elevation["elevation_m"].idxmax()) if not valid_elevation.empty else 0
    low_point_index = int(valid_elevation["elevation_m"].idxmin()) if not valid_elevation.empty else 0

    highest_point = {
        "point_index": int(frame.loc[high_point_index, "point_index"]) if not frame.empty else None,
        "distance_km": float(frame.loc[high_point_index, "cumulative_distance_km"]) if not frame.empty else None,
        "elevation_m": float(frame.loc[high_point_index, "elevation_m"]) if not frame.empty else None,
        "latitude": float(frame.loc[high_point_index, "latitude"]) if not frame.empty else None,
        "longitude": float(frame.loc[high_point_index, "longitude"]) if not frame.empty else None,
        "point_name": frame.loc[high_point_index, "point_name"] if not frame.empty else None,
    }
    lowest_point = {
        "point_index": int(frame.loc[low_point_index, "point_index"]) if not frame.empty else None,
        "distance_km": float(frame.loc[low_point_index, "cumulative_distance_km"]) if not frame.empty else None,
        "elevation_m": float(frame.loc[low_point_index, "elevation_m"]) if not frame.empty else None,
        "latitude": float(frame.loc[low_point_index, "latitude"]) if not frame.empty else None,
        "longitude": float(frame.loc[low_point_index, "longitude"]) if not frame.empty else None,
        "point_name": frame.loc[low_point_index, "point_name"] if not frame.empty else None,
    }

    insights: list[str] = []
    if steepest_section is not None:
        insights.append(
            f"The steepest section spans {steepest_section.start_distance_km:.1f} km to {steepest_section.end_distance_km:.1f} km with an average gradient of {steepest_section.gradient_percent:.0f}%."
        )
    if longest_climb is not None:
        insights.append(
            f"The longest climb covers {longest_climb.distance_km:.2f} km and gains roughly {longest_climb.elevation_change_m:.0f} m."
        )
    if longest_descent is not None:
        insights.append(
            f"The longest descent runs for {longest_descent.distance_km:.2f} km and drops about {abs(longest_descent.elevation_change_m):.0f} m."
        )
    if highest_point["elevation_m"] is not None:
        insights.append(
            f"The highest point sits near {highest_point['distance_km']:.1f} km at {highest_point['elevation_m']:.0f} m."
        )
    insights.append(
        f"Terrain distribution leans toward {terrain_counts.idxmax()} terrain, which supports an overall {difficulty_label.lower()} hike rating."
    )

    return RouteAnalysis(
        route_name=route_name,
        source=source,
        points=frame,
        total_distance_km=total_distance_km,
        elevation_gain_m=elevation_gain_m,
        elevation_loss_m=elevation_loss_m,
        maximum_elevation_m=maximum_elevation_m,
        minimum_elevation_m=minimum_elevation_m,
        average_elevation_m=average_elevation_m,
        maximum_slope_degrees=maximum_slope_degrees,
        average_slope_degrees=average_slope_degrees,
        average_slope_percent=average_slope_percent,
        difficulty_score=difficulty_score,
        difficulty_label=difficulty_label,
        hiking_time_hours=hiking_time_hours,
        running_time_hours=running_time_hours,
        trail_running_time_hours=trail_running_time_hours,
        mountain_biking_time_hours=mountain_biking_time_hours,
        calories_burned=calories_burned,
        active_time_hours=active_time_hours,
        moving_time_hours=moving_time_hours,
        terrain_breakdown=terrain_breakdown,
        insights=insights,
        longest_climb=longest_climb,
        longest_descent=longest_descent,
        steepest_section=steepest_section,
        highest_point=highest_point,
        lowest_point=lowest_point,
        terrain_class_counts=terrain_counts,
    )


def analysis_to_dataframe(analysis: RouteAnalysis) -> pd.DataFrame:
    """Create a compact metric table for export and comparison views."""

    return pd.DataFrame(
        [
            {"metric": "Distance", "value": analysis.total_distance_km, "unit": "km"},
            {"metric": "Elevation gain", "value": analysis.elevation_gain_m, "unit": "m"},
            {"metric": "Elevation loss", "value": analysis.elevation_loss_m, "unit": "m"},
            {"metric": "Difficulty score", "value": analysis.difficulty_score, "unit": "/100"},
            {"metric": "Estimated hiking time", "value": analysis.hiking_time_hours, "unit": "hr"},
            {"metric": "Calories burned", "value": analysis.calories_burned, "unit": "kcal"},
        ]
    )
