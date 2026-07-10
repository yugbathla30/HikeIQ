import numpy as np
import pandas as pd
import pytest
from affine import Affine
from rasterio.io import MemoryFile

from global_elevation_enrichment import enrich_with_global_elevation


def test_tile_boundary_uses_floor_for_negative_longitude(monkeypatch):
    captured = {}

    def fake_load_tile(lat_idx, lon_idx):
        captured["tile"] = (lat_idx, lon_idx)
        return (
            np.full((100, 200), 100.0, dtype=float),
            {
                "transform": Affine(1, 0, -105, 0, 1, 0),
                "res": (1.0, 1.0),
                "shape": (100, 200),
            },
        )

    monkeypatch.setattr("global_elevation_enrichment._load_tile", fake_load_tile)

    df = pd.DataFrame(
        [{"latitude": 39.0, "longitude": -104.9999, "location": "Denver"}]
    )
    result = enrich_with_global_elevation(df)

    assert captured["tile"] == (39, -105)
    assert result.loc[0, "elevation_m"] == 100.0


def test_ocean_fallback_sets_zeroed_output(monkeypatch):
    monkeypatch.setattr("global_elevation_enrichment._load_tile", lambda lat_idx, lon_idx: "OCEAN")

    df = pd.DataFrame([{"latitude": 0.0, "longitude": -140.0, "location": "Pacific"}])
    result = enrich_with_global_elevation(df)

    assert result.loc[0, "elevation_m"] == 0.0
    assert result.loc[0, "slope_degrees"] == 0.0
    assert result.loc[0, "aspect_direction"] == "N"


def test_invalid_coordinates_are_skipped():
    df = pd.DataFrame(
        [
            {"latitude": 91.0, "longitude": 10.0, "location": "bad-lat"},
            {"latitude": 10.0, "longitude": 181.0, "location": "bad-lon"},
            {"latitude": np.nan, "longitude": 10.0, "location": "bad-nan"},
        ]
    )
    result = enrich_with_global_elevation(df)

    assert result["elevation_m"].isna().all()


def test_disk_cache_is_used_across_calls(tmp_path, monkeypatch):
    calls = []

    def fake_download_tile(url, timeout):
        calls.append(url)
        with MemoryFile() as memfile:
            with memfile.open(
                driver="GTiff",
                width=200,
                height=100,
                count=1,
                dtype="float32",
                transform=Affine(1, 0, -105, 0, 1, 0),
            ) as dataset:
                dataset.write(np.full((1, 100, 200), 100.0, dtype=np.float32))
            return memfile.read()

    monkeypatch.setattr("global_elevation_enrichment.requests.get", fake_download_tile)

    df = pd.DataFrame([{"latitude": 17.4, "longitude": 78.4, "location": "Hyderabad"}])
    first = enrich_with_global_elevation(df, cache_dir=str(tmp_path))
    second = enrich_with_global_elevation(df, cache_dir=str(tmp_path))

    assert len(calls) == 1
    assert first.loc[0, "elevation_m"] == pytest.approx(100.0)
    assert second.loc[0, "elevation_m"] == pytest.approx(100.0)
