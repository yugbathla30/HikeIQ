from __future__ import annotations

import html

import folium

from terrain_dashboard.config import DEFAULT_MAP_ZOOM, MAP_TILES
from terrain_dashboard.utils import aspect_compass_icon, format_coordinate


def build_terrain_map(
    latitude: float,
    longitude: float,
    elevation_m: float | None,
    slope_degrees: float | None,
    aspect_direction: str | None,
    terrain_steepness: str,
    terrain_steepness_color: str,
    zoom_start: int = DEFAULT_MAP_ZOOM,
) -> folium.Map:
    """Build a Folium map for a single terrain observation."""

    fmap = folium.Map(location=[latitude, longitude], zoom_start=zoom_start, tiles=MAP_TILES, control_scale=True)
    folium.CircleMarker(
        location=[latitude, longitude],
        radius=9,
        color=terrain_steepness_color,
        weight=2,
        fill=True,
        fill_color=terrain_steepness_color,
        fill_opacity=0.9,
    ).add_to(fmap)

    popup_html = f"""
    <div style="font-family: Inter, ui-sans-serif, system-ui; min-width: 220px;">
      <div style="font-size: 15px; font-weight: 700; margin-bottom: 6px;">Terrain Observation</div>
      <div><strong>Coordinate:</strong> {html.escape(format_coordinate(latitude, longitude))}</div>
      <div><strong>Elevation:</strong> {"--" if elevation_m is None else f"{elevation_m:.1f} m"}</div>
      <div><strong>Slope:</strong> {"--" if slope_degrees is None else f"{slope_degrees:.2f}°"}</div>
      <div><strong>Aspect:</strong> {"--" if aspect_direction is None else f"{aspect_compass_icon(aspect_direction)} {aspect_direction}"}</div>
            <div><strong>Local terrain steepness:</strong> {html.escape(terrain_steepness)}</div>
    </div>
    """
    folium.Marker(
        location=[latitude, longitude],
        popup=folium.Popup(popup_html, max_width=320),
                tooltip=f"{terrain_steepness} steepness",
        icon=folium.Icon(color="green", icon="info-sign"),
    ).add_to(fmap)
    return fmap
