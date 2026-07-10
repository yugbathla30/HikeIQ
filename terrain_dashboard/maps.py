from __future__ import annotations

from math import isfinite

import folium
from folium import FeatureGroup
from folium.plugins import Draw, Fullscreen, MeasureControl, MiniMap
import pandas as pd

from terrain_dashboard.config import MAP_TILES


TILE_VARIANTS = {
    "Street": "CartoDB positron",
    "Light": "CartoDB positron",
    "Dark": "CartoDB dark_matter",
    "Terrain": "OpenTopoMap",
    "Satellite": "Esri.WorldImagery",
}


def build_draw_map(
    *,
    center_lat: float,
    center_lon: float,
    tile_theme: str = "Street",
    show_contours: bool = False,
) -> folium.Map:
    """Build an empty map with drawing controls for capturing a user-defined route."""

    base_tiles = TILE_VARIANTS.get(tile_theme, MAP_TILES)
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles=base_tiles, control_scale=True)
    for name, tiles in TILE_VARIANTS.items():
        if name == tile_theme:
            continue
        folium.TileLayer(tiles=tiles, name=name, control=True, attr=name).add_to(fmap)

    Draw(
        export=True,
        position="topleft",
        draw_options={
            "polyline": True,
            "polygon": False,
            "circle": False,
            "marker": True,
            "circlemarker": False,
            "rectangle": False,
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(fmap)
    Fullscreen(position="topright").add_to(fmap)
    MeasureControl(position="topright", primary_length_unit="kilometers", primary_area_unit="sqmeters").add_to(fmap)
    MiniMap(toggle_display=True).add_to(fmap)

    if show_contours:
        folium.LayerControl(collapsed=False).add_to(fmap)
    else:
        folium.LayerControl(collapsed=True).add_to(fmap)
    return fmap


def _gradient_color(value: float, minimum: float, maximum: float) -> str:
    if not isfinite(value):
        return "#22c55e"
    if maximum <= minimum:
        return "#3b82f6"
    ratio = min(1.0, max(0.0, (value - minimum) / (maximum - minimum)))
    red = int(34 + (239 - 34) * ratio)
    green = int(197 - (197 - 76) * ratio)
    blue = int(94 - (94 - 44) * ratio)
    return f"#{red:02x}{green:02x}{blue:02x}"


def build_route_map(
    route_points: pd.DataFrame,
    *,
    tile_theme: str = "Street",
    show_contours: bool = False,
    show_labels: bool = True,
    draw_controls: bool = True,
) -> folium.Map:
    """Build a multi-layer route map with a premium trail overlay."""

    if route_points.empty:
        raise ValueError("Route points are required to build the map.")

    center_lat = float(route_points["latitude"].mean())
    center_lon = float(route_points["longitude"].mean())
    base_tiles = TILE_VARIANTS.get(tile_theme, MAP_TILES)
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles=base_tiles, control_scale=True)

    for name, tiles in TILE_VARIANTS.items():
        if name == tile_theme:
            continue
        folium.TileLayer(tiles=tiles, name=name, control=True, attr=name).add_to(fmap)

    elevations = route_points["elevation_m"].fillna(method="ffill").fillna(method="bfill") if "elevation_m" in route_points else pd.Series([0.0] * len(route_points))
    elevation_min = float(elevations.min()) if not elevations.empty else 0.0
    elevation_max = float(elevations.max()) if not elevations.empty else 1.0

    route_group = FeatureGroup(name="Trail line", show=True)
    for index in range(1, len(route_points)):
        start = route_points.iloc[index - 1]
        end = route_points.iloc[index]
        elevation_value = float(elevations.iloc[index]) if index < len(elevations) else float(elevations.iloc[-1])
        color = _gradient_color(elevation_value, elevation_min, elevation_max)
        folium.PolyLine(
            locations=[(float(start["latitude"]), float(start["longitude"])), (float(end["latitude"]), float(end["longitude"]))],
            color=color,
            weight=6,
            opacity=0.92,
        ).add_to(route_group)

    route_group.add_to(fmap)

    start_row = route_points.iloc[0]
    end_row = route_points.iloc[-1]
    folium.Marker(
        location=[float(start_row["latitude"]), float(start_row["longitude"])],
        icon=folium.Icon(color="green", icon="play"),
        tooltip="Start",
    ).add_to(fmap)
    folium.Marker(
        location=[float(end_row["latitude"]), float(end_row["longitude"])],
        icon=folium.Icon(color="red", icon="flag"),
        tooltip="Finish",
    ).add_to(fmap)

    if show_labels:
        label_group = FeatureGroup(name="Waypoints", show=True)
        for _, row in route_points.iterrows():
            tooltip = row.get("point_name") or f"Waypoint {int(row['point_index'])}"
            elevation_text = "--" if pd.isna(row.get("elevation_m")) else f"{float(row['elevation_m']):.1f} m"
            slope_text = "--" if pd.isna(row.get("slope_degrees")) else f"{float(row['slope_degrees']):.1f}°"
            popup_html = "<br>".join(
                [
                    f"<strong>{tooltip}</strong>",
                    f"Lat: {float(row['latitude']):.5f}",
                    f"Lon: {float(row['longitude']):.5f}",
                    f"Elevation: {elevation_text}",
                    f"Slope: {slope_text}",
                ]
            )
            folium.CircleMarker(
                location=[float(row["latitude"]), float(row["longitude"])],
                radius=4,
                color="#f8fafc",
                weight=1,
                fill=True,
                fill_color="#22c55e",
                fill_opacity=0.95,
                tooltip=tooltip,
                popup=folium.Popup(popup_html, max_width=300),
            ).add_to(label_group)
        label_group.add_to(fmap)

    if draw_controls:
        Draw(
            export=True,
            position="topleft",
            draw_options={
                "polyline": True,
                "polygon": False,
                "circle": False,
                "marker": False,
                "circlemarker": False,
                "rectangle": False,
            },
            edit_options={"edit": True, "remove": True},
        ).add_to(fmap)
        Fullscreen(position="topright").add_to(fmap)
        MeasureControl(position="topright", primary_length_unit="kilometers", primary_area_unit="sqmeters").add_to(fmap)
        MiniMap(toggle_display=True).add_to(fmap)

    if show_contours:
        folium.LayerControl(collapsed=False).add_to(fmap)
    else:
        folium.LayerControl(collapsed=True).add_to(fmap)

    fmap.fit_bounds(
        [
            [float(route_points["latitude"].min()), float(route_points["longitude"].min())],
            [float(route_points["latitude"].max()), float(route_points["longitude"].max())],
        ]
    )
    return fmap
