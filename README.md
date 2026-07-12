# Terrain Intelligence Dashboard

HikeIQ is a Streamlit app for analyzing hiking trails with global elevation data. It combines a reusable elevation engine, GPX parsing, trail analytics, and map/chart visualizations in one workspace.

## What lives where

- [terrain_dashboard/](terrain_dashboard/) contains the Streamlit app and all reusable UI/analysis modules.
- [global_elevation_enrichment.py](global_elevation_enrichment.py) is the legacy command-line enrichment engine.
- [tests/](tests/) contains the regression suite for the engine.
- [data/raw/](data/raw/) stores source GPX and CSV inputs.
- [outputs/](outputs/) stores generated CSV and HTML artifacts.

## Run locally

```bash
pip install -r requirements.txt
streamlit run terrain_dashboard/app.py
```

## Deploy

The cleanest deployment target for this codebase is Streamlit Community Cloud, because the app already has a single Streamlit entrypoint at [terrain_dashboard/app.py](terrain_dashboard/app.py) and a root `requirements.txt`.

Deployment checklist:

1. Push the repo to GitHub.
2. Connect the repository to Streamlit Community Cloud.
3. Set the app entrypoint to `terrain_dashboard/app.py`.
4. Keep `requirements.txt` at the repository root so dependency installation stays simple.

If a managed Streamlit host gives you trouble with geospatial wheels such as `rasterio`, deploy the same repo on a container-friendly host like Render or a small VPS and run the same Streamlit command there.

## Notes on the file layout

The repository used to keep sample GPX files and generated outputs at the root. Those files now live under `data/raw/` and `outputs/` so the project root stays focused on code and documentation.

## Legacy engine

The original command-line enrichment workflow remains available in [global_elevation_enrichment.py](global_elevation_enrichment.py) and is still covered by the test suite.

## Current stack

- Streamlit for the app shell
- Pandas for route and batch data handling
- Folium and Streamlit-Folium for map rendering
- Plotly for charts
- Rasterio and requests for elevation tile access
