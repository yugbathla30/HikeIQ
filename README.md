# Terrain Intelligence Dashboard

This repository now includes a Streamlit portfolio app under [terrain_dashboard/](terrain_dashboard/) that turns the existing DEM lookup engine into an interactive terrain exploration dashboard.

## Run the app

```bash
pip install -r requirements.txt
streamlit run terrain_dashboard/app.py
```

## Legacy engine

The original command-line enrichment workflow remains available in [global_elevation_enrichment.py](global_elevation_enrichment.py) and is still covered by the test suite.
