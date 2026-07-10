# Terrain Intelligence Dashboard

Terrain Intelligence Dashboard is a production-style Streamlit application for exploring terrain anywhere in the world from latitude and longitude. It combines a reusable elevation engine with a modern analytics UI for recruiters, portfolio demos, and lightweight field analysis.

## Features

- Single coordinate lookup with elevation, slope, aspect, and aspect direction
- Folium world map with marker, popup, and zoomed location context
- Automatic terrain classification with color-coded badges
- Gradient gauge and progress-style visualization
- Batch CSV upload with validation, enrichment, summary statistics, and download
- Plotly charts for elevation, slope, and terrain distribution
- Responsive layout with sidebar controls, tabs, containers, and expanders
- Caching for coordinate lookups, uploaded datasets, and map rendering

## Architecture

- `app.py` orchestrates the Streamlit UI and user interactions
- `terrain_engine.py` wraps the existing elevation engine as an importable backend
- `utils.py` handles validation, formatting, classification, and statistics
- `charts.py` builds Plotly figures for analysis
- `map.py` builds the cached Folium map
- `config.py` stores rules, defaults, colors, and layout constants

## Installation

```bash
pip install -r requirements.txt
```

## Run Locally

```bash
streamlit run terrain_dashboard/app.py
```

If you prefer the module entry point:

```bash
python -m streamlit run terrain_dashboard/app.py
```

## Screenshots

Add screenshots here after deployment or when capturing the final portfolio build.

## Future Improvements

- Multi-point map overlays and route profiling
- Elevation profile lines for uploaded paths
- Export to GeoJSON and shapefile formats
- User-selectable basemap themes
- Optional geocoder lookup by place name
