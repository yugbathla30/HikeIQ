from __future__ import annotations
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from terrain_dashboard import analytics, charts, config, demo_data, exports, gpx_parser, maps, terrain_engine, utils


STYLE_PATH = APP_DIR / "styles.css"


st.set_page_config(
    page_title=f"{config.APP_TITLE} – {config.APP_TAGLINE}",
    page_icon=config.PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    """Load the premium CSS shell."""

    css = STYLE_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def initialize_state() -> None:
    """Create all session state used by the HikeIQ shell."""

    defaults = {
        "active_page": config.DEFAULT_ACTIVE_PAGE,
        "route_mode": "Demo trail",
        "units": config.DEFAULT_UNITS,
        "show_contours": False,
        "show_labels": True,
        "selected_demo_route_name": None,
        "cache_dir": config.DEFAULT_CACHE_DIR,
        "max_workers": config.DEFAULT_MAX_WORKERS,
        "max_retries": config.DEFAULT_MAX_RETRIES,
        "retry_backoff": config.DEFAULT_RETRY_BACKOFF,
        "timeout": config.DEFAULT_TIMEOUT,
        "weight_kg": config.DEFAULT_WEIGHT_KG,
        "gender": config.DEFAULT_GENDER,
        "fitness_level": config.DEFAULT_FITNESS_LEVEL,
        "current_route_payload": None,
        "current_analysis": None,
        "current_analysis_signature": None,
        "analysis_history": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    demo_routes = list(cached_demo_routes())
    if demo_routes and st.session_state.selected_demo_route_name is None:
        st.session_state.selected_demo_route_name = demo_routes[0].name
    if demo_routes and st.session_state.current_route_payload is None:
        set_demo_route(st.session_state.selected_demo_route_name or demo_routes[0].name)


@st.cache_data(show_spinner=False)
def cached_enrich_route(
    route_json: str,
    cache_dir: str,
    max_workers: int,
    max_retries: int,
    retry_backoff: float,
    timeout: int,
) -> pd.DataFrame:
    """Enrich a route frame with terrain data using the existing engine."""

    frame = pd.read_json(io.StringIO(route_json), orient="split")
    return terrain_engine.enrich_batch_dataframe(
        frame,
        cache_dir=cache_dir,
        max_workers=max_workers,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        timeout=timeout,
    )


@st.cache_data(show_spinner=False)
def cached_parse_gpx(file_bytes: bytes, file_name: str) -> gpx_parser.ParsedRoute:
    """Parse a GPX upload into route points."""

    return gpx_parser.load_route_from_bytes(file_bytes, file_name)


@st.cache_data(show_spinner=False)
def cached_demo_route() -> gpx_parser.ParsedRoute:
    """Return the first bundled demo route."""

    routes = cached_demo_routes()
    if not routes:
        raise ValueError("No bundled demo routes were found.")
    return routes[0]


@st.cache_data(show_spinner=False)
def cached_demo_routes() -> tuple[gpx_parser.ParsedRoute, ...]:
    """Return every bundled demo route."""

    return demo_data.load_demo_routes()


def frame_signature(frame: pd.DataFrame, route_name: str, source: str) -> str:
    payload = frame.to_json(orient="split")
    return hashlib.sha256(f"{route_name}:{source}:{payload}".encode("utf-8")).hexdigest()


def payload_from_parsed_route(parsed: gpx_parser.ParsedRoute) -> dict[str, Any]:
    """Convert parsed route data into a serializable payload for caching and history."""

    return {
        "route_name": parsed.name,
        "source": parsed.source,
        "frame_json": parsed.points.to_json(orient="split"),
        "signature": frame_signature(parsed.points, parsed.name, parsed.source),
    }


def settings_signature() -> str:
    """Hash the analysis settings that influence route calculations."""

    settings = {
        "weight_kg": float(st.session_state.weight_kg),
        "gender": st.session_state.gender,
        "fitness_level": st.session_state.fitness_level,
        "cache_dir": st.session_state.cache_dir,
        "max_workers": int(st.session_state.max_workers),
        "max_retries": int(st.session_state.max_retries),
        "retry_backoff": float(st.session_state.retry_backoff),
        "timeout": int(st.session_state.timeout),
    }
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode("utf-8")).hexdigest()


def analysis_signature(payload: dict[str, Any]) -> str:
    """Build a stable signature for the current route plus analysis settings."""

    return hashlib.sha256(f"{payload['signature']}:{settings_signature()}".encode("utf-8")).hexdigest()


def analysis_from_payload(payload: dict[str, Any]) -> analytics.RouteAnalysis:
    """Enrich and analyze the route currently stored in session state."""

    enriched = cached_enrich_route(
        payload["frame_json"],
        st.session_state.cache_dir,
        st.session_state.max_workers,
        st.session_state.max_retries,
        st.session_state.retry_backoff,
        st.session_state.timeout,
    )
    return analytics.analyze_route(
        payload["route_name"],
        payload["source"],
        enriched,
        weight_kg=float(st.session_state.weight_kg),
        gender=str(st.session_state.gender),
        fitness_level=str(st.session_state.fitness_level),
    )


def get_or_compute_analysis() -> analytics.RouteAnalysis | None:
    """Return the current analysis, recomputing only when the payload or settings change."""

    payload = st.session_state.get("current_route_payload")
    if not payload:
        st.session_state.current_analysis = None
        st.session_state.current_analysis_signature = None
        return None

    signature = analysis_signature(payload)
    if st.session_state.current_analysis_signature != signature or st.session_state.current_analysis is None:
        with st.status("Analyzing trail", expanded=True) as status:
            progress = st.progress(5, text="Loading route points...")
            progress.progress(25, text="Enriching terrain samples...")
            analysis = analysis_from_payload(payload)
            progress.progress(70, text="Computing route metrics...")
            progress.progress(100, text="Finalizing insights...")
            status.update(label="Trail analysis complete", state="complete")
        st.session_state.current_analysis = analysis
        st.session_state.current_analysis_signature = signature
        register_history_entry(analysis, payload)
    return st.session_state.current_analysis


def register_history_entry(analysis: analytics.RouteAnalysis, payload: dict[str, Any]) -> None:
    """Store the latest trail in the recent trail history."""

    history = list(st.session_state.analysis_history)
    current_key = payload["signature"]
    if history and history[0]["signature"] == current_key:
        return

    history.insert(
        0,
        {
            "route_name": analysis.route_name,
            "source": analysis.source,
            "signature": current_key,
            "payload": payload,
            "distance_km": analysis.total_distance_km,
            "elevation_gain_m": analysis.elevation_gain_m,
            "difficulty_score": analysis.difficulty_score,
            "difficulty_label": analysis.difficulty_label,
            "hiking_time_hours": analysis.hiking_time_hours,
            "calories_burned": analysis.calories_burned,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    st.session_state.analysis_history = history[:8]


def format_distance(value_km: float, units: str) -> str:
    """Format a distance using the selected unit system."""

    if units == "imperial":
        return f"{value_km * 0.621371:.2f} mi"
    return f"{value_km:.2f} km"


def format_elevation(value_m: float, units: str) -> str:
    """Format an elevation using the selected unit system."""

    if units == "imperial":
        return f"{value_m * 3.28084:.0f} ft"
    return f"{value_m:.0f} m"


def format_duration(hours: float) -> str:
    """Format a duration as hours and minutes."""

    total_minutes = max(0, int(round(hours * 60)))
    result_hours, result_minutes = divmod(total_minutes, 60)
    return f"{result_hours}h {result_minutes:02d}m"


def route_badge(label: str, color: str) -> str:
    return f'<span class="route-pill" style="border-color:{color}33;color:{color};background:{color}14;">{label}</span>'


def vertical_space(size: str = "medium") -> None:
    heights = {"small": "0.5rem", "medium": "1rem", "large": "1.5rem"}
    st.markdown(f"<div style='height:{heights.get(size, '1rem')};'></div>", unsafe_allow_html=True)


def metric_card_html(icon: str, label: str, value: str, caption: str, accent: str) -> str:
    return f"""
    <div class="kpi-card">
        <div class="kpi-label"><span style="color:{accent};margin-right:0.45rem;">{icon}</span>{label}</div>
        <div class="kpi-value" style="color:{accent};">{value}</div>
        <div class="kpi-caption">{caption}</div>
    </div>
    """


def render_metric_row(metrics: list[tuple[str, str, str, str, str]]) -> None:
    """Render a row of premium KPI cards."""

    columns = st.columns(len(metrics), gap="medium")
    for column, metric in zip(columns, metrics, strict=True):
        with column:
            st.markdown(metric_card_html(*metric), unsafe_allow_html=True)


def demo_route_payload() -> dict[str, Any]:
    selected_name = st.session_state.get("selected_demo_route_name")
    for route in cached_demo_routes():
        if route.name == selected_name:
            return payload_from_parsed_route(route)
    return payload_from_parsed_route(cached_demo_route())


def set_demo_route(route_name: str) -> None:
    routes = {route.name: route for route in cached_demo_routes()}
    route = routes.get(route_name)
    if route is None:
        return
    st.session_state.selected_demo_route_name = route_name
    st.session_state.current_route_payload = payload_from_parsed_route(route)
    st.session_state.current_analysis = None
    st.session_state.current_analysis_signature = None


def set_payload(parsed: gpx_parser.ParsedRoute) -> None:
    st.session_state.current_route_payload = payload_from_parsed_route(parsed)
    st.session_state.current_analysis = None
    st.session_state.current_analysis_signature = None


def clear_current_trail() -> None:
    if cached_demo_routes():
        set_demo_route(st.session_state.selected_demo_route_name or cached_demo_routes()[0].name)
    else:
        st.session_state.current_route_payload = None
        st.session_state.selected_demo_route_name = None
    st.session_state.current_analysis = None
    st.session_state.current_analysis_signature = None


def recent_trail_buttons() -> None:
    """Render the recent trail list in the sidebar."""

    history = st.session_state.analysis_history
    if not history:
        st.caption("No recent trails yet.")
        return

    for entry in history:
        with st.container(border=True):
            st.markdown(f"**{entry['route_name']}**")
            st.caption(f"{entry['source'].title()} · {entry['created_at']}")
            st.caption(
                f"{format_distance(entry['distance_km'], st.session_state.units)} · {format_elevation(entry['elevation_gain_m'], st.session_state.units)} gain · {entry['difficulty_label']}"
            )
            if st.button("Load trail", key=f"load-history-{entry['signature']}", width="stretch", help="Reload this trail into the active analysis view."):
                st.session_state.current_route_payload = entry["payload"]
                st.session_state.current_analysis = None
                st.session_state.current_analysis_signature = None
                st.rerun()


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="hikeiq-brand">
                <div>
                    <div class="hikeiq-brand-title">HikeIQ</div>
                    <div class="hikeiq-brand-subtitle">Hiking & Trek Difficulty Analyzer</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.session_state.active_page = st.segmented_control(
            "Navigation",
            options=config.PAGE_OPTIONS,
            default=st.session_state.active_page,
            key="sidebar-nav",
        )

        st.markdown("### Demo trails")
        demo_routes = list(cached_demo_routes())
        if demo_routes:
            route_names = [route.name for route in demo_routes]
            selected_demo_name = st.selectbox(
                "Selected demo trail",
                route_names,
                index=route_names.index(st.session_state.selected_demo_route_name) if st.session_state.selected_demo_route_name in route_names else 0,
                key="selected-demo-route",
                help="Switch the active trail used by the home and analysis views.",
            )
            if selected_demo_name != st.session_state.selected_demo_route_name or st.session_state.current_route_payload is None:
                set_demo_route(selected_demo_name)
        if st.button("Reset demo trail", width="stretch", help="Restore the first bundled demo trail and its analysis."):
            if demo_routes:
                set_demo_route(demo_routes[0].name)
            st.rerun()

        st.markdown("### Upload GPX")
        uploaded_file = st.file_uploader(
            "Upload a GPX route",
            type=["gpx", "xml"],
            label_visibility="collapsed",
            help="Upload a GPX file to replace the current active route.",
        )
        if uploaded_file is not None:
            try:
                parsed = cached_parse_gpx(uploaded_file.getvalue(), uploaded_file.name)
                set_payload(parsed)
                st.session_state.route_mode = "Upload GPX"
                st.session_state.active_page = "Trail analysis"
                st.success(f"Loaded {parsed.name}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

        action_left, action_right = st.columns(2)
        with action_left:
            if st.button("Open analysis", type="primary", width="stretch", help="Open the terrain analysis workspace for the active route."):
                st.session_state.active_page = "Trail analysis"
                st.rerun()
        with action_right:
            if st.button("Clear selection", width="stretch", help="Clear the active uploaded route and restore the demo selection."):
                clear_current_trail()
                st.session_state.route_mode = "Demo trail"
                st.rerun()

        st.markdown("### Recent trails")
        recent_trail_buttons()

        st.markdown("### Analysis settings")
        st.session_state.units = st.segmented_control("Units", options=config.UNITS_OPTIONS, default=st.session_state.units, key="sidebar-units")
        st.session_state.weight_kg = st.number_input("Weight (kg)", min_value=30.0, max_value=180.0, value=float(st.session_state.weight_kg), step=0.5)
        st.session_state.gender = st.segmented_control("Gender", options=config.GENDER_OPTIONS, default=st.session_state.gender, key="sidebar-gender")
        st.session_state.fitness_level = st.segmented_control("Fitness level", options=config.FITNESS_LEVEL_OPTIONS, default=st.session_state.fitness_level, key="sidebar-fitness")

        with st.expander("Advanced cache settings", expanded=False):
            st.session_state.cache_dir = st.text_input("Cache directory", value=str(st.session_state.cache_dir), help="Local folder used for terrain tile caching.")
            st.session_state.max_workers = st.number_input("Max workers", min_value=1, max_value=32, value=int(st.session_state.max_workers), step=1)
            st.session_state.max_retries = st.number_input("Max retries", min_value=0, max_value=10, value=int(st.session_state.max_retries), step=1)
            st.session_state.retry_backoff = st.number_input("Retry backoff", min_value=0.1, max_value=10.0, value=float(st.session_state.retry_backoff), step=0.5)
            st.session_state.timeout = st.number_input("Timeout (seconds)", min_value=5, max_value=120, value=int(st.session_state.timeout), step=1)


def render_home_page() -> None:
    analysis = get_or_compute_analysis()
    hero_distance = format_distance(analysis.total_distance_km, st.session_state.units) if analysis else "0.0 km"
    hero_gain = format_elevation(analysis.elevation_gain_m, st.session_state.units) if analysis else "0 m"
    hero_score = f"{analysis.difficulty_score}/100" if analysis else "--"
    hero_time = format_duration(analysis.hiking_time_hours) if analysis else "--"

    st.markdown(
        f"""
        <section class="hero-shell">
            <div class="hero-kicker">Terrain intelligence · bundled demo trails · live route analysis</div>
            <div class="hero-title">HikeIQ</div>
            <div class="hero-subtitle">The dashboard starts with every bundled GPX trail already loaded. Switch routes, inspect the map, compare terrain, or upload your own GPX file without waiting for a blank screen.</div>
            <div class="hero-actions">
                <button class="stButton" disabled style="display:none"></button>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    action_left, action_right = st.columns([1, 1], gap="small")
    with action_left:
        if st.button("Open analysis", type="primary", width="stretch", help="Open the analysis workspace for the currently selected route."):
            st.session_state.active_page = "Trail analysis"
            st.rerun()
    with action_right:
        if st.button("Switch demo trail", width="stretch", help="Jump to the analysis workspace and switch routes if needed."):
            st.session_state.active_page = "Trail analysis"
            st.rerun()

    vertical_space("medium")
    render_metric_row(
        [
            (":material/route:", "Distance", hero_distance, "Total trail length", config.ACCENT_BLUE),
            (":material/altitude:", "Elevation gain", hero_gain, "Positive climbing effort", config.ACCENT_GREEN),
            (":material/bar_chart:", "Difficulty", hero_score, "0–100 route score", config.ACCENT_ORANGE),
            (":material/schedule:", "Hiking time", hero_time, "Naismith-style estimate", config.ACCENT_BLUE),
        ]
    )

    if analysis is not None:
        vertical_space("medium")
        render_map_panel(analysis)

    if analysis is not None:
        vertical_space("medium")
        with st.container(border=True):
            st.markdown("<div class='panel-title'>Current trail snapshot</div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='panel-subtitle'>The last analyzed trail already has a full terrain profile. Reopen it from Trail analysis to inspect the map, charts, and export bundle.</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<div class='badge-group'>"
                + route_badge(analysis.difficulty_label, {"Easy": config.ACCENT_GREEN, "Moderate": config.ACCENT_BLUE, "Hard": config.ACCENT_ORANGE, "Extreme": config.DANGER}.get(analysis.difficulty_label, config.ACCENT_BLUE))
                + route_badge(analysis.source.title(), config.TEXT_SECONDARY)
                + "</div>",
                unsafe_allow_html=True,
            )


def render_analysis_header(analysis: analytics.RouteAnalysis) -> None:
    accent_map = {
        "Easy": config.ACCENT_GREEN,
        "Moderate": config.ACCENT_BLUE,
        "Hard": config.ACCENT_ORANGE,
        "Extreme": config.DANGER,
    }
    accent = accent_map.get(analysis.difficulty_label, config.ACCENT_BLUE)
    st.markdown(
        f"""
        <div class="section-header">
            <div>
                <div class="muted-label">Trail analysis</div>
                <h2 class="section-title">{analysis.route_name}</h2>
                <p class="section-subtitle">{analysis.points.shape[0]} points · {format_distance(analysis.total_distance_km, st.session_state.units)} · {analysis.source.replace('-', ' ').title()} route source</p>
            </div>
            <div class="badge-group">
                {route_badge(analysis.difficulty_label, accent)}
                {route_badge(f"Score {analysis.difficulty_score}/100", accent)}
                {route_badge(f"{format_duration(analysis.hiking_time_hours)} hike", config.TEXT_SECONDARY)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_map_panel(analysis: analytics.RouteAnalysis) -> None:
    with st.container(border=True):
        st.markdown("<div class='panel-title'>Route map</div>", unsafe_allow_html=True)
        st.markdown("<p class='panel-subtitle'>Pan, zoom, and inspect the active route. Demo mode shows all bundled trails at once and highlights the selected one.</p>", unsafe_allow_html=True)
        payload = st.session_state.get("current_route_payload") or {}
        payload_source = payload.get("source")
        if payload_source == "demo":
            demo_routes = [(route.name, route.points) for route in cached_demo_routes()]
            route_map = maps.build_multi_route_map(
                demo_routes,
                selected_route_name=st.session_state.selected_demo_route_name,
                show_contours=st.session_state.show_contours,
                show_labels=st.session_state.show_labels,
            )
            st_folium(route_map, height=620, key=f"demo-map-{st.session_state.selected_demo_route_name}", returned_objects=[])
        elif st.session_state.route_mode == "Draw route":
            if analysis is not None:
                draw_map = maps.build_route_map(
                    analysis.points,
                    route_name=analysis.route_name,
                    tile_theme="Light",
                    show_contours=st.session_state.show_contours,
                    show_labels=st.session_state.show_labels,
                    draw_controls=True,
                )
            else:
                draw_map = maps.build_draw_map(
                    center_lat=config.DEFAULT_LATITUDE,
                    center_lon=config.DEFAULT_LONGITUDE,
                    tile_theme="Light",
                    show_contours=st.session_state.show_contours,
                )
            drawn = st_folium(draw_map, height=620, key=f"draw-map-{st.session_state.show_contours}", returned_objects=["all_drawings", "last_active_drawing"])
            drawings = drawn.get("all_drawings") or drawn.get("last_active_drawing")
            if drawings:
                try:
                    parsed = gpx_parser.parse_drawn_route(drawings, fallback_name="Drawn trail")
                    set_payload(parsed)
                    st.session_state.route_mode = "Draw route"
                    st.toast("Drawn route captured.")
                    st.rerun()
                except ValueError as exc:
                    st.warning(str(exc))
        else:
            route_map = maps.build_route_map(
                analysis.points,
                route_name=analysis.route_name,
                tile_theme="Light",
                show_contours=st.session_state.show_contours,
                show_labels=st.session_state.show_labels,
                draw_controls=False,
            )
            st_folium(route_map, height=620, key=f"route-map-{st.session_state.current_analysis_signature}", returned_objects=[])


def render_profile_panel(analysis: analytics.RouteAnalysis) -> None:
    with st.container(border=True):
        st.markdown("<div class='panel-title'>Elevation profile</div>", unsafe_allow_html=True)
        st.markdown("<p class='panel-subtitle'>Hover for distance, elevation, slope, and waypoint details. Use zoom and pan to inspect local terrain changes.</p>", unsafe_allow_html=True)
        st.plotly_chart(charts.build_elevation_profile(analysis), width="stretch")


def render_summary_metrics(analysis: analytics.RouteAnalysis) -> None:
    render_metric_row(
        [
            (":material/straighten:", "Distance", format_distance(analysis.total_distance_km, st.session_state.units), "Trail length between the first and last point.", config.ACCENT_BLUE),
            (":material/arrow_upward:", "Elevation gain", format_elevation(analysis.elevation_gain_m, st.session_state.units), "Total ascent accumulated along the route.", config.ACCENT_GREEN),
            (":material/arrow_downward:", "Elevation loss", format_elevation(analysis.elevation_loss_m, st.session_state.units), "All downhill sections combined.", config.ACCENT_ORANGE),
            (":material/landscape:", "Maximum elevation", format_elevation(analysis.maximum_elevation_m, st.session_state.units), "The highest sampled point on the trail.", config.ACCENT_BLUE),
            (":material/place:", "Minimum elevation", format_elevation(analysis.minimum_elevation_m, st.session_state.units), "The lowest sampled point on the trail.", config.ACCENT_GREEN),
        ]
    )
    vertical_space("small")
    render_metric_row(
        [
            (":material/trending_up:", "Maximum slope", f"{analysis.maximum_slope_degrees:.1f}°", "Steepest terrain sample.", config.DANGER),
            (":material/score:", "Difficulty score", f"{analysis.difficulty_score}/100", f"{analysis.difficulty_label} trail rating.", config.ACCENT_ORANGE),
            (":material/schedule:", "Hiking time", format_duration(analysis.hiking_time_hours), "Naismith-based hiking estimate.", config.ACCENT_BLUE),
            (":material/local_fire_department:", "Calories burned", f"{analysis.calories_burned:,}", "Estimated energy cost for the selected weight and fitness level.", config.ACCENT_GREEN),
            (":material/percent:", "Average slope", f"{analysis.average_slope_degrees:.1f}°", "Mean slope from the terrain samples.", config.ACCENT_BLUE),
        ]
    )


def render_insights_panel(analysis: analytics.RouteAnalysis) -> None:
    with st.container(border=True):
        st.markdown("<div class='panel-title'>Difficulty overview</div>", unsafe_allow_html=True)
        st.markdown("<p class='panel-subtitle'>A compact score built from distance, gain, slope, and average gradient. It is intentionally conservative for mountain routes.</p>", unsafe_allow_html=True)
        st.plotly_chart(charts.build_difficulty_gauge(analysis), width="stretch")

    with st.container(border=True):
        st.markdown("<div class='panel-title'>Route insights</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='insight-list'>"
            + "".join(f"<div class='insight-item'>{insight}</div>" for insight in analysis.insights)
            + "</div>",
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        st.markdown("<div class='panel-title'>Terrain breakdown</div>", unsafe_allow_html=True)
        st.plotly_chart(charts.build_terrain_breakdown_pie(analysis), width="stretch")


def render_export_panel(analysis: analytics.RouteAnalysis) -> None:
    with st.container(border=True):
        st.markdown("<div class='panel-title'>Export</div>", unsafe_allow_html=True)
        st.markdown("<p class='panel-subtitle'>Download the enriched route, a text-based PDF summary, and PNG chart snapshots.</p>", unsafe_allow_html=True)
        csv_bytes = exports.route_points_to_csv_bytes(analysis)
        gpx_bytes = exports.route_points_to_gpx_bytes(analysis)
        pdf_bytes = exports.route_report_pdf_bytes(analysis)
        profile_png = exports.figure_to_png_bytes(charts.build_elevation_profile(analysis))
        difficulty_png = exports.figure_to_png_bytes(charts.build_difficulty_gauge(analysis))
        terrain_png = exports.figure_to_png_bytes(charts.build_terrain_breakdown_pie(analysis))

        export_columns = st.columns(2, gap="small")
        with export_columns[0]:
            st.download_button("CSV report", csv_bytes, file_name=f"{analysis.route_name.lower().replace(' ', '_')}.csv", mime="text/csv", width="stretch", help="Download the enriched route points as CSV.")
        with export_columns[1]:
            st.download_button("GPX with terrain", gpx_bytes, file_name=f"{analysis.route_name.lower().replace(' ', '_')}_enriched.gpx", mime="application/gpx+xml", width="stretch", help="Download the route with the terrain values embedded in GPX extensions.")

        export_columns = st.columns(2, gap="small")
        with export_columns[0]:
            st.download_button("PDF summary", pdf_bytes, file_name=f"{analysis.route_name.lower().replace(' ', '_')}.pdf", mime="application/pdf", width="stretch", help="Download a compact PDF route summary.")
        with export_columns[1]:
            if profile_png is not None:
                st.download_button("PNG elevation profile", profile_png, file_name=f"{analysis.route_name.lower().replace(' ', '_')}_profile.png", mime="image/png", width="stretch", help="Download the elevation profile chart as PNG.")
            else:
                st.caption("PNG export needs Plotly image support in the runtime.")

        if difficulty_png is not None:
            st.download_button("PNG difficulty ring", difficulty_png, file_name=f"{analysis.route_name.lower().replace(' ', '_')}_difficulty.png", mime="image/png", width="stretch", help="Download the difficulty gauge as PNG.")
        if terrain_png is not None:
            st.download_button("PNG terrain breakdown", terrain_png, file_name=f"{analysis.route_name.lower().replace(' ', '_')}_terrain.png", mime="image/png", width="stretch", help="Download the terrain breakdown chart as PNG.")


def render_analysis_page() -> None:
    st.markdown(
        "<div class='section-shell'><div class='section-header'><div><div class='muted-label'>Trail analysis</div><h2 class='section-title'>Analyze a route</h2><p class='section-subtitle'>Upload a GPX file, draw a route, or load the demo trail. The engine enriches every point with elevation, slope, and aspect before the analyzer computes route metrics.</p></div></div></div>",
        unsafe_allow_html=True,
    )

    st.session_state.route_mode = st.segmented_control(
        "Route source",
        options=["Upload GPX", "Draw route", "Demo trail"],
        default=st.session_state.route_mode,
        key="route-source-control",
    )

    settings_left, settings_right = st.columns([1, 1], gap="large")
    with settings_left:
        if st.session_state.route_mode == "Demo trail":
            demo_routes = list(cached_demo_routes())
            if demo_routes:
                route_names = [route.name for route in demo_routes]
                selected_demo_name = st.selectbox(
                    "Demo trail",
                    route_names,
                    index=route_names.index(st.session_state.selected_demo_route_name) if st.session_state.selected_demo_route_name in route_names else 0,
                    key="analysis-demo-route",
                    help="Switch the active demo trail used for analysis and the multi-route map.",
                )
                if selected_demo_name != st.session_state.selected_demo_route_name:
                    set_demo_route(selected_demo_name)
                    st.rerun()
    with settings_right:
        toggle_left, toggle_right = st.columns(2)
        with toggle_left:
            st.session_state.show_labels = st.toggle("Show elevation labels", value=st.session_state.show_labels, help="Display point labels on the map.")
        with toggle_right:
            st.session_state.show_contours = st.toggle("Show contour lines", value=st.session_state.show_contours, help="Expand the layer control for basemap and overlay switching.")

    if st.session_state.route_mode == "Demo trail" and st.session_state.current_route_payload is None:
        set_demo_route(st.session_state.selected_demo_route_name or cached_demo_route().name)

    if st.session_state.route_mode == "Upload GPX" and st.session_state.current_route_payload is None:
        st.info("Use the sidebar uploader to load a GPX track or route.")

    payload = st.session_state.get("current_route_payload")
    payload_source = payload.get("source") if payload else None
    analysis = None
    if payload and (st.session_state.route_mode != "Draw route" or payload_source == "drawn-route"):
        analysis = get_or_compute_analysis()

    if analysis is None:
        if st.session_state.route_mode == "Draw route":
            with st.container(border=True):
                st.markdown("<div class='panel-title'>Draw your route</div>", unsafe_allow_html=True)
                st.markdown("<p class='panel-subtitle'>Sketch a trail on the map. When you finish drawing the line, HikeIQ will enrich it and generate a full terrain profile.</p>", unsafe_allow_html=True)
            draw_map = maps.build_draw_map(
                center_lat=config.DEFAULT_LATITUDE,
                center_lon=config.DEFAULT_LONGITUDE,
                tile_theme="Light",
                show_contours=st.session_state.show_contours,
            )
            drawn = st_folium(
                draw_map,
                height=620,
                key=f"draw-map-empty-{st.session_state.show_contours}",
                returned_objects=["all_drawings", "last_active_drawing"],
            )
            drawings = drawn.get("all_drawings") or drawn.get("last_active_drawing")
            if drawings:
                try:
                    parsed = gpx_parser.parse_drawn_route(drawings, fallback_name="Drawn trail")
                    set_payload(parsed)
                    st.session_state.route_mode = "Draw route"
                    st.toast("Drawn route captured.")
                    st.rerun()
                except ValueError as exc:
                    st.warning(str(exc))
            return

        with st.container(border=True):
            st.markdown("<div class='panel-title'>Ready when you are</div>", unsafe_allow_html=True)
            st.markdown("<p class='panel-subtitle'>Choose a source above, then either upload a GPX file, switch to draw mode and sketch a route on the map, or load the demo trail to inspect the full product experience.</p>", unsafe_allow_html=True)
            st.skeleton(height=260)
        return

    render_analysis_header(analysis)
    vertical_space("small")
    render_summary_metrics(analysis)
    vertical_space("medium")

    left_column, right_column = st.columns([2.15, 1], gap="large")
    with left_column:
        render_map_panel(analysis)
        vertical_space("small")
        render_profile_panel(analysis)
    with right_column:
        render_insights_panel(analysis)
        render_export_panel(analysis)

    vertical_space("medium")
    with st.container(border=True):
        st.markdown("<div class='panel-title'>Time and energy estimates</div>", unsafe_allow_html=True)
        st.markdown("<p class='panel-subtitle'>Naismith-style hiking time plus alternative activity estimates and calorie costs. Adjust weight and fitness in the sidebar to refine the estimate.</p>", unsafe_allow_html=True)
        st.plotly_chart(charts.build_time_estimates_chart(analysis), width="stretch")
        compare_columns = st.columns(2, gap="large")
        with compare_columns[0]:
            st.metric("Active time", format_duration(analysis.active_time_hours), delta="Includes rest and navigation time", border=True)
        with compare_columns[1]:
            st.metric("Moving time", format_duration(analysis.moving_time_hours), delta="Time in motion on the trail", border=True)

    vertical_space("medium")
    with st.expander("Compare trails", expanded=False):
        left_upload, right_upload = st.columns(2, gap="large")
        with left_upload:
            left_file = st.file_uploader("First GPX file", type=["gpx", "xml"], key="compare-left", label_visibility="visible", help="Select the first GPX file for comparison.")
        with right_upload:
            right_file = st.file_uploader("Second GPX file", type=["gpx", "xml"], key="compare-right", label_visibility="visible", help="Select the second GPX file for comparison.")

        if left_file is not None and right_file is not None:
            try:
                left_route = cached_parse_gpx(left_file.getvalue(), left_file.name)
                right_route = cached_parse_gpx(right_file.getvalue(), right_file.name)
                left_analysis = analysis_from_payload(payload_from_parsed_route(left_route))
                right_analysis = analysis_from_payload(payload_from_parsed_route(right_route))
                st.plotly_chart(charts.build_comparison_bars(left_analysis, right_analysis), width="stretch")
                compare_metrics = st.columns(2, gap="large")
                with compare_metrics[0]:
                    st.markdown(f"<div class='summary-card'><strong>{left_analysis.route_name}</strong><span>Distance {format_distance(left_analysis.total_distance_km, st.session_state.units)} · Gain {format_elevation(left_analysis.elevation_gain_m, st.session_state.units)} · Difficulty {left_analysis.difficulty_score}/100</span></div>", unsafe_allow_html=True)
                with compare_metrics[1]:
                    st.markdown(f"<div class='summary-card'><strong>{right_analysis.route_name}</strong><span>Distance {format_distance(right_analysis.total_distance_km, st.session_state.units)} · Gain {format_elevation(right_analysis.elevation_gain_m, st.session_state.units)} · Difficulty {right_analysis.difficulty_score}/100</span></div>", unsafe_allow_html=True)
            except ValueError as exc:
                st.error(str(exc))
        else:
            st.caption("Upload two GPX files to compare distance, gain, difficulty, time, and calories side by side.")


def render_history_page() -> None:
    st.markdown(
        "<div class='section-header'><div><div class='muted-label'>History</div><h2 class='section-title'>Recent trails</h2><p class='section-subtitle'>Trail snapshots are kept for the current session so you can reopen or compare previous analyses quickly.</p></div></div>",
        unsafe_allow_html=True,
    )
    history = st.session_state.analysis_history
    if not history:
        with st.container(border=True):
            st.caption("No trails have been analyzed yet.")
        return

    cards = st.columns(min(2, len(history)), gap="large")
    for index, entry in enumerate(history):
        column = cards[index % len(cards)]
        with column:
            with st.container(border=True):
                st.markdown(f"<div class='panel-title'>{entry['route_name']}</div>", unsafe_allow_html=True)
                st.markdown(f"<p class='panel-subtitle'>{entry['source'].title()} · {entry['created_at']}</p>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='insight-list'><div class='insight-item'>Distance: {format_distance(entry['distance_km'], st.session_state.units)}</div><div class='insight-item'>Elevation gain: {format_elevation(entry['elevation_gain_m'], st.session_state.units)}</div><div class='insight-item'>Difficulty: {entry['difficulty_label']} ({entry['difficulty_score']}/100)</div></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Load this trail", key=f"history-load-{entry['signature']}", width="stretch", help="Restore this trail to the active analysis view."):
                    st.session_state.current_route_payload = entry["payload"]
                    st.session_state.current_analysis = None
                    st.session_state.current_analysis_signature = None
                    st.session_state.active_page = "Trail analysis"
                    st.rerun()


initialize_state()
inject_styles()
render_sidebar()

page = st.session_state.active_page
if page == "Home":
    render_home_page()
elif page == "Trail analysis":
    render_analysis_page()
elif page == "History":
    render_history_page()
else:
    render_home_page()
