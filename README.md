# HikeIQ

HikeIQ is a terrain intelligence dashboard for hiking and trekking routes. It analyzes GPX files using high-resolution global elevation data to generate route statistics, terrain insights, difficulty estimates, and interactive visualizations.

The project combines a reusable terrain enrichment engine with an interactive Streamlit interface, making it easy to upload a trail, inspect its terrain characteristics, and export the results.

**Live demo:** https://hikeiq.streamlit.app/

---

## Features

* Upload and analyze GPX routes
* Explore bundled demo trails
* Enrich routes with elevation, slope, and aspect data from the Copernicus 30 m Digital Elevation Model
* Calculate distance, elevation gain/loss, terrain statistics, and route difficulty
* Estimate hiking time using Naismith-style calculations
* Estimate calories burned based on user weight and fitness level
* Visualize routes with interactive maps and elevation charts
* Export enriched routes as CSV, GPX

---

## Project Structure

```text
.
├── terrain_dashboard/
│   ├── app.py
│   ├── analytics.py
│   ├── terrain_engine.py
│   ├── maps.py
│   ├── charts.py
│   ├── exports.py
│   ├── config.py
│   ├── utils.py
│   └── demo_trails/
│
├── data/
│   └── raw/
│
├── outputs/
├── tests/
├── global_elevation_enrichment.py
├── requirements.txt
└── README.md
```

---

## What Lives Where

* **terrain_dashboard/** contains the Streamlit application and reusable modules for analytics, mapping, visualizations, exports, and terrain processing.
* **global_elevation_enrichment.py** contains the standalone terrain enrichment engine used by the application.
* **tests/** contains regression tests for the enrichment engine.
* **data/raw/** stores sample GPX and CSV files.
* **outputs/** stores generated CSV, GPX outputs

---

## How It Works

1. Load a GPX file or choose one of the bundled demo trails.
2. Enrich the route with elevation data from the Copernicus DEM.
3. Compute terrain metrics such as slope, aspect, elevation gain, and cumulative distance.
4. Analyze the route to generate difficulty scores, hiking time estimates, and terrain statistics.
5. Visualize the results through interactive maps and charts.
6. Export the analyzed route if required.

---

## Technology Stack

* Streamlit
* Pandas
* NumPy
* Plotly
* Folium
* Streamlit-Folium
* Rasterio
* Requests
* Affine
* Pytest

---

## Running Locally

Clone the repository:

```bash
git clone https://github.com/yugbathla30/HikeIQ.git
cd HikeIQ
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
streamlit run terrain_dashboard/app.py
```

---

## Deployment

The project is designed to run directly on Streamlit Community Cloud.

1. Push the repository to GitHub.
2. Create a new Streamlit Community Cloud app.
3. Select this repository.
4. Set the entry point to:

```text
terrain_dashboard/app.py
```

---

## Notes

The original command-line terrain enrichment workflow is still available in `global_elevation_enrichment.py` and is used by the reusable terrain engine.

---

## Future Work

Some ideas for future improvements include:

* improvement in UI fixing bugs with frontend
* Multi-route comparison
* Weather-aware hiking recommendations
* Offline terrain datasets
* Additional activity profiles
* Mobile-friendly layout
* Integration with services such as Strava or Garmin
