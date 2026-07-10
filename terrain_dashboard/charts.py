from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from terrain_dashboard.config import STEEPNESS_CHART_COLORS, STEEPNESS_ORDER
from terrain_dashboard.analytics import RouteAnalysis


def _dark_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=title,
        template="plotly_dark",
        margin=dict(l=18, r=18, t=54, b=18),
        font=dict(family="Inter, ui-sans-serif, system-ui", size=13, color="#F8FAFC"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title_font=dict(size=18, color="#F8FAFC"),
        hoverlabel=dict(bgcolor="#101D2C", font_color="#F8FAFC"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def _apply_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=title,
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=20),
        font=dict(family="Inter, ui-sans-serif, system-ui", size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title_font=dict(size=18, color="#1f2937"),
    )
    return fig


def build_elevation_histogram(df: pd.DataFrame) -> go.Figure:
    """Create an elevation histogram."""

    values = df[["elevation_m"]].dropna()
    fig = px.histogram(
        values,
        x="elevation_m",
        nbins=24,
        color_discrete_sequence=["#2a9d8f"],
        labels={"elevation_m": "Elevation (m)"},
    )
    fig.update_traces(marker_line_color="rgba(255,255,255,0.45)", marker_line_width=1)
    return _apply_layout(fig, "Elevation Distribution")


def build_slope_histogram(df: pd.DataFrame) -> go.Figure:
    """Create a slope histogram."""

    values = df[["slope_degrees"]].dropna()
    fig = px.histogram(
        values,
        x="slope_degrees",
        nbins=24,
        color_discrete_sequence=["#d08c60"],
        labels={"slope_degrees": "Slope (degrees)"},
    )
    fig.update_traces(marker_line_color="rgba(255,255,255,0.45)", marker_line_width=1)
    return _apply_layout(fig, "Slope Distribution")


def build_terrain_distribution_chart(df: pd.DataFrame) -> go.Figure:
    """Create a local terrain steepness distribution chart."""

    counts = df["terrain_steepness"].value_counts().reindex(STEEPNESS_ORDER, fill_value=0)
    plot_frame = pd.DataFrame({"terrain_steepness": counts.index, "count": counts.values})
    fig = px.bar(
        plot_frame,
        x="terrain_steepness",
        y="count",
        color="terrain_steepness",
        color_discrete_sequence=STEEPNESS_CHART_COLORS,
        labels={"terrain_steepness": "Local Terrain Steepness", "count": "Count"},
    )
    fig.update_traces(marker_line_width=0, hovertemplate="%{x}: %{y}<extra></extra>")
    fig.update_layout(showlegend=False)
    return _apply_layout(fig, "Local Terrain Steepness Distribution")


def build_gradient_gauge(slope_percent: float | None, steepness_name: str) -> go.Figure:
    """Create a gauge for the current slope percentage."""

    value = 0.0 if slope_percent is None or pd.isna(slope_percent) else float(slope_percent)
    max_axis = max(60.0, value * 1.2 if value > 0 else 60.0)

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=min(value, max_axis),
            number={"suffix": "%"},
            title={"text": f"Gradient gauge · {steepness_name}"},
            gauge={
                "axis": {"range": [0, max_axis]},
                "bar": {"color": "#2a9d8f"},
                "steps": [
                    {"range": [0, 5], "color": "rgba(42,157,143,0.18)"},
                    {"range": [5, 15], "color": "rgba(208,140,96,0.18)"},
                    {"range": [15, 30], "color": "rgba(199,125,255,0.18)"},
                    {"range": [30, max_axis], "color": "rgba(193,18,31,0.18)"},
                ],
            },
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, ui-sans-serif, system-ui", size=13),
    )
    return fig


def build_elevation_profile(analysis: RouteAnalysis) -> go.Figure:
    """Create an interactive elevation profile for the analyzed route."""

    frame = analysis.points.copy()
    hover_text = []
    for _, row in frame.iterrows():
        waypoint = row.get("point_name") or f"Waypoint {int(row['point_index'])}"
        hover_text.append(
            f"Distance: {float(row['cumulative_distance_km']):.2f} km<br>"
            f"Elevation: {('--' if pd.isna(row.get('elevation_m')) else f'{float(row['elevation_m']):.1f} m')}<br>"
            f"Slope: {('--' if pd.isna(row.get('slope_percent')) else f'{float(row['slope_percent']):.1f}%')}<br>"
            f"Waypoint: {waypoint}"
        )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frame["cumulative_distance_km"],
            y=frame["elevation_m"],
            mode="lines+markers",
            name="Elevation",
            line=dict(color="#3B82F6", width=3),
            marker=dict(size=7, color="#22C55E", line=dict(color="#08131F", width=1)),
            text=hover_text,
            hovertemplate="%{text}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=frame["cumulative_distance_km"],
            y=frame["segment_gradient_percent"],
            mode="lines",
            name="Slope %",
            yaxis="y2",
            line=dict(color="#F59E0B", width=2, dash="dot"),
            hovertemplate="Distance: %{x:.2f} km<br>Slope: %{y:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis=dict(title="Distance (km)", gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(title="Elevation (m)", gridcolor="rgba(255,255,255,0.08)"),
        yaxis2=dict(
            title="Slope (%)",
            overlaying="y",
            side="right",
            showgrid=False,
            zeroline=False,
            color="#F59E0B",
        ),
        dragmode="pan",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return _dark_layout(fig, "Elevation profile")


def build_difficulty_gauge(analysis: RouteAnalysis) -> go.Figure:
    """Create a progress ring for the route difficulty score."""

    score = max(0, min(100, int(analysis.difficulty_score)))
    label = analysis.difficulty_label
    colors = {"Easy": "#22C55E", "Moderate": "#3B82F6", "Hard": "#F59E0B", "Extreme": "#EF4444"}
    color = colors.get(label, "#3B82F6")

    fig = go.Figure(
        go.Pie(
            values=[score, 100 - score],
            hole=0.78,
            sort=False,
            direction="clockwise",
            marker=dict(colors=[color, "rgba(255,255,255,0.08)"], line=dict(color="#08131F", width=0)),
            textinfo="none",
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_annotation(
        text=f"<b>{score}</b><br><span style='font-size:14px;color:#94A3B8'>{label}</span>",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=28, color="#F8FAFC"),
    )
    fig.update_layout(
        margin=dict(l=18, r=18, t=18, b=18),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_terrain_breakdown_pie(analysis: RouteAnalysis) -> go.Figure:
    """Create a terrain class breakdown pie chart."""

    frame = analysis.terrain_breakdown.copy()
    fig = px.pie(
        frame,
        names="terrain_class",
        values="count",
        color="terrain_class",
        color_discrete_sequence=STEEPNESS_CHART_COLORS,
        hole=0.54,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label", hovertemplate="%{label}: %{value}<extra></extra>")
    return _dark_layout(fig, "Terrain breakdown")


def build_time_estimates_chart(analysis: RouteAnalysis) -> go.Figure:
    """Create a comparison chart for hiking, running, and biking estimates."""

    frame = pd.DataFrame(
        {
            "activity": ["Hiking", "Running", "Trail running", "Mountain biking"],
            "hours": [
                analysis.hiking_time_hours,
                analysis.running_time_hours,
                analysis.trail_running_time_hours,
                analysis.mountain_biking_time_hours,
            ],
        }
    )
    fig = px.bar(frame, x="activity", y="hours", color="activity", color_discrete_sequence=["#22C55E", "#3B82F6", "#F59E0B", "#EF4444"])
    fig.update_traces(hovertemplate="%{x}: %{y:.2f} hours<extra></extra>")
    fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Hours")
    return _dark_layout(fig, "Activity time estimates")


def build_comparison_bars(left_analysis: RouteAnalysis, right_analysis: RouteAnalysis) -> go.Figure:
    """Create a side-by-side comparison chart for two routes."""

    frame = pd.DataFrame(
        {
            "metric": ["Distance", "Gain", "Difficulty", "Time", "Calories"],
            f"{left_analysis.route_name}": [
                left_analysis.total_distance_km,
                left_analysis.elevation_gain_m,
                left_analysis.difficulty_score,
                left_analysis.hiking_time_hours,
                left_analysis.calories_burned,
            ],
            f"{right_analysis.route_name}": [
                right_analysis.total_distance_km,
                right_analysis.elevation_gain_m,
                right_analysis.difficulty_score,
                right_analysis.hiking_time_hours,
                right_analysis.calories_burned,
            ],
        }
    )
    fig = go.Figure()
    fig.add_bar(name=left_analysis.route_name, x=frame["metric"], y=frame[left_analysis.route_name], marker_color="#22C55E")
    fig.add_bar(name=right_analysis.route_name, x=frame["metric"], y=frame[right_analysis.route_name], marker_color="#3B82F6")
    fig.update_layout(barmode="group", xaxis_title=None, yaxis_title="Value")
    return _dark_layout(fig, "Trail comparison")
