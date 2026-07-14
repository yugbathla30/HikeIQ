from __future__ import annotations

from math import isfinite

import folium
from folium import FeatureGroup
from folium.plugins import Draw, Fullscreen, MeasureControl, MiniMap
import pandas as pd

from terrain_dashboard.config import MAP_TILES, ROUTE_COLORS


TILE_VARIANTS = {
    "Street": "CartoDB positron",
    "Light": "CartoDB positron",
    "Dark": "CartoDB dark_matter",
    "Terrain": "OpenTopoMap",
    "Satellite": "Esri.WorldImagery",
}


def _route_color(index: int) -> str:
    return ROUTE_COLORS[index % len(ROUTE_COLORS)]


def _elevation_series(route_points: pd.DataFrame) -> pd.Series:
    if "elevation_m" in route_points:
        return route_points["elevation_m"].ffill().bfill()
    return pd.Series([0.0] * len(route_points))


def _add_route_layer(
    fmap: folium.Map,
    route_name: str,
    route_points: pd.DataFrame,
    *,
    color: str,
    selected: bool,
    show_labels: bool,
) -> None:
    route_group = FeatureGroup(name=route_name, show=True)
    elevations = _elevation_series(route_points)
    elevation_min = float(elevations.min()) if not elevations.empty else 0.0
    elevation_max = float(elevations.max()) if not elevations.empty else 1.0

    for index in range(1, len(route_points)):
        start = route_points.iloc[index - 1]
        end = route_points.iloc[index]
        elevation_value = float(elevations.iloc[index]) if index < len(elevations) else float(elevations.iloc[-1])
        segment_color = color if selected else _gradient_color(elevation_value, elevation_min, elevation_max)
        folium.PolyLine(
            locations=[(float(start["latitude"]), float(start["longitude"])), (float(end["latitude"]), float(end["longitude"]))],
            color=segment_color,
            weight=8 if selected else 5,
            opacity=1.0 if selected else 0.78,
            tooltip=route_name,
        ).add_to(route_group)

    start_row = route_points.iloc[0]
    end_row = route_points.iloc[-1]
    folium.CircleMarker(
        location=[float(start_row["latitude"]), float(start_row["longitude"])],
        radius=6 if selected else 4,
        color=color,
        weight=2,
        fill=True,
        fill_color=color,
        fill_opacity=1.0,
        tooltip=f"{route_name} start",
    ).add_to(route_group)
    folium.CircleMarker(
        location=[float(end_row["latitude"]), float(end_row["longitude"])],
        radius=6 if selected else 4,
        color=color,
        weight=2,
        fill=True,
        fill_color=color,
        fill_opacity=1.0,
        tooltip=f"{route_name} finish",
    ).add_to(route_group)

    if show_labels:
        for _, row in route_points.iterrows():
            tooltip = row.get("point_name") or f"Waypoint {int(row['point_index'])}"
            folium.CircleMarker(
                location=[float(row["latitude"]), float(row["longitude"])],
                radius=4 if selected else 3,
                color="#fff7eb",
                weight=1,
                fill=True,
                fill_color=color,
                fill_opacity=0.95 if selected else 0.82,
                tooltip=tooltip,
            ).add_to(route_group)

    route_group.add_to(fmap)


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
    route_name: str | None = None,
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

    _add_route_layer(
        fmap,
        route_name or "Selected route",
        route_points,
        color=_route_color(0),
        selected=True,
        show_labels=show_labels,
    )

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


def build_multi_route_map(
    routes: list[tuple[str, pd.DataFrame]],
    *,
    selected_route_name: str | None = None,
    tile_theme: str = "Street",
    show_contours: bool = False,
    show_labels: bool = True,
) -> folium.Map:
    """Build a map that shows all routes and highlights the selected one."""

    if not routes:
        raise ValueError("At least one route is required to build the map.")

    combined = pd.concat([frame for _, frame in routes], ignore_index=True)
    center_lat = float(combined["latitude"].mean())
    center_lon = float(combined["longitude"].mean())
    base_tiles = TILE_VARIANTS.get(tile_theme, MAP_TILES)
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles=base_tiles, control_scale=True)

    for name, tiles in TILE_VARIANTS.items():
        if name == tile_theme:
            continue
        folium.TileLayer(tiles=tiles, name=name, control=True, attr=name).add_to(fmap)

    for index, (route_name, route_points) in enumerate(routes):
        _add_route_layer(
            fmap,
            route_name,
            route_points,
            color=_route_color(index),
            selected=route_name == selected_route_name,
            show_labels=show_labels and route_name == selected_route_name,
        )

    if show_contours:
        folium.LayerControl(collapsed=False).add_to(fmap)
    else:
        folium.LayerControl(collapsed=True).add_to(fmap)

    fmap.fit_bounds(
        [
            [float(combined["latitude"].min()), float(combined["longitude"].min())],
            [float(combined["latitude"].max()), float(combined["longitude"].max())],
        ]
    )
    return fmap
