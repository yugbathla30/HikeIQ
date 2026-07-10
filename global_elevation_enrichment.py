import argparse
import json
import math
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from affine import Affine
from rasterio.io import MemoryFile

# =============================================================================
# GLOBAL HELPER FUNCTIONS & CACHING
# =============================================================================

_tile_cache: dict[tuple[int, int], Any] = {}


def _tile_indices(lat, lon):
    """
    Return the (lat_idx, lon_idx) integer tile indices for a coordinate,
    using floor() so tiles are keyed by their south-west corner — matching
    the Copernicus DEM naming convention. This must be used consistently
    everywhere a tile is looked up or a pixel is located within it.
    """
    return math.floor(lat), math.floor(lon)


def get_tile_url(lat_idx, lon_idx):
    """Get the correct Copernicus DEM 30m tile URL structure used by AWS S3,
    given floor-based tile indices (NOT raw lat/lon)."""
    lat_prefix = 'N' if lat_idx >= 0 else 'S'
    lon_prefix = 'E' if lon_idx >= 0 else 'W'
    lat_int = abs(lat_idx)
    lon_int = abs(lon_idx)

    tile_name = f"Copernicus_DSM_COG_10_{lat_prefix}{lat_int:02d}_00_{lon_prefix}{lon_int:03d}_00_DEM"
    url = f"https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com/{tile_name}/{tile_name}.tif"
    return url, tile_name


def _normalize_response_payload(payload):
    if hasattr(payload, "content"):
        return payload.content
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)
    raise TypeError(f"Unsupported tile payload type: {type(payload)!r}")


def _cache_tile(tile_name, dem_array, meta, cache_dir):
    if not cache_dir:
        return
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    npz_path = cache_path / f"{tile_name}.npz"
    json_path = cache_path / f"{tile_name}.json"
    np.savez_compressed(npz_path, data=dem_array.astype(np.float32))
    meta_payload = {
        "transform": [meta["transform"].a, meta["transform"].b, meta["transform"].c, meta["transform"].d, meta["transform"].e, meta["transform"].f],
        "res": list(meta["res"]),
        "shape": list(meta["shape"]),
    }
    json_path.write_text(json.dumps(meta_payload), encoding="utf-8")


def _read_cached_tile(tile_name, cache_dir):
    if not cache_dir:
        return None
    cache_path = Path(cache_dir)
    npz_path = cache_path / f"{tile_name}.npz"
    json_path = cache_path / f"{tile_name}.json"
    if not npz_path.exists() or not json_path.exists():
        return None
    try:
        with np.load(npz_path, allow_pickle=False) as data:
            dem_array = data["data"].astype(np.float32)
        meta_payload = json.loads(json_path.read_text(encoding="utf-8"))
        meta = {
            "transform": Affine(*meta_payload["transform"]),
            "res": tuple(meta_payload["res"]),
            "shape": tuple(meta_payload["shape"]),
        }
        return dem_array, meta
    except Exception as exc:
        print(f"Warning: unable to read cached tile {tile_name}: {exc}")
        return None


def _load_tile(lat_idx, lon_idx, cache_dir=None, max_retries=3, retry_backoff=1.0, timeout=30):
    """Load a DEM tile from AWS S3, with local caching and retries. Handles ocean gaps safely."""
    tile_key = (lat_idx, lon_idx)

    if tile_key in _tile_cache:
        return _tile_cache[tile_key]

    url, tile_name = get_tile_url(lat_idx, lon_idx)
    cached_tile = _read_cached_tile(tile_name, cache_dir) if cache_dir else None
    if cached_tile is not None:
        _tile_cache[tile_key] = cached_tile
        return cached_tile

    for attempt in range(max_retries):
        try:
            payload = requests.get(url, timeout=timeout)
            response_bytes = _normalize_response_payload(payload)

            if hasattr(payload, "status_code") and payload.status_code == 404:
                _tile_cache[tile_key] = "OCEAN"
                return "OCEAN"

            if hasattr(payload, "status_code") and payload.status_code != 200:
                raise RuntimeError(f"Unexpected status code {payload.status_code}")

            with MemoryFile(response_bytes) as memfile:
                with memfile.open() as dataset:
                    dem_array = dataset.read(1).astype(np.float32)
                    meta = {
                        "transform": dataset.transform,
                        "res": dataset.res,
                        "shape": dem_array.shape,
                    }
                    _cache_tile(tile_name, dem_array, meta, cache_dir)
                    _tile_cache[tile_key] = (dem_array, meta)
                    return _tile_cache[tile_key]
        except Exception as exc:
            if attempt < max_retries - 1:
                sleep_for = retry_backoff * (attempt + 1)
                time.sleep(sleep_for)
                continue
            print(f"Error downloading tile {tile_name}: {exc}")
            _tile_cache[tile_key] = None
            return None

    _tile_cache[tile_key] = None
    return None


def _compute_slope_at_pixel(dem_array, row, col, pixel_size_y, pixel_size_x):
    """Compute slope and aspect at a specific pixel from a full DEM array."""
    r_start = max(0, row - 1)
    r_end = min(dem_array.shape[0], row + 2)
    c_start = max(0, col - 1)
    c_end = min(dem_array.shape[1], col + 2)

    window = dem_array[r_start:r_end, c_start:c_end].astype(float)

    if window.shape[0] < 3 or window.shape[1] < 3:
        return 0.0, 0.0, 0.0

    dz_dy, dz_dx = np.gradient(window, pixel_size_y, pixel_size_x)
    cr, cc = row - r_start, col - c_start

    slope_rad = np.arctan(np.sqrt(dz_dx[cr, cc] ** 2 + dz_dy[cr, cc] ** 2))
    slope_deg = float(np.degrees(slope_rad))
    slope_pct = float(np.tan(slope_rad) * 100)

    aspect_rad = np.arctan2(-dz_dx[cr, cc], dz_dy[cr, cc])
    aspect_deg = float(np.degrees(aspect_rad))
    if aspect_deg < 0:
        aspect_deg += 360

    return slope_deg, slope_pct, aspect_deg


def get_aspect_direction(aspect_deg):
    """Convert aspect degrees to cardinal direction."""
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N']
    idx = int((aspect_deg + 22.5) // 45)
    return dirs[idx]


def _call_load_tile(load_fn, lat_idx, lon_idx, cache_dir=None, max_retries=3, retry_backoff=1.0, timeout=30):
    try:
        return load_fn(
            lat_idx,
            lon_idx,
            cache_dir=cache_dir,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            timeout=timeout,
        )
    except TypeError:
        return load_fn(lat_idx, lon_idx)


def enrich_with_global_elevation(df, cache_dir=None, max_workers=8, max_retries=3, retry_backoff=1.0, timeout=30):
    """Enrich a pandas DataFrame with elevation and slope data worldwide."""
    pdf = df.copy()

    cols = pdf.columns.tolist()
    assert 'latitude' in cols, "DataFrame must have a 'latitude' column"
    assert 'longitude' in cols, "DataFrame must have a 'longitude' column"

    pdf['elevation_m'] = np.nan
    pdf['slope_degrees'] = np.nan
    pdf['slope_percent'] = np.nan
    pdf['aspect_degrees'] = np.nan
    pdf['aspect_direction'] = None

    valid_mask = (
        pdf['latitude'].notna() &
        pdf['longitude'].notna() &
        (pdf['latitude'].between(-90, 90)) &
        (pdf['longitude'].between(-180, 180))
    )
    valid_indices = pdf.index[valid_mask].tolist()

    if not valid_indices:
        print("No valid global coordinates found.")
        return pdf

    tile_groups = defaultdict(list)
    for idx in valid_indices:
        lat, lon = pdf.at[idx, 'latitude'], pdf.at[idx, 'longitude']
        lat_idx, lon_idx = _tile_indices(lat, lon)
        tile_groups[(lat_idx, lon_idx)].append((idx, lat, lon))

    total_tiles = len(tile_groups)
    print(f"Processing {len(valid_indices)} coordinates across {total_tiles} global DEM tiles...")

    tile_results = {}
    tile_keys = list(tile_groups.keys())
    if len(tile_keys) > 1:
        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(tile_keys)))) as executor:
            future_map = {
                executor.submit(
                    _call_load_tile,
                    _load_tile,
                    lat_idx,
                    lon_idx,
                    cache_dir=cache_dir,
                    max_retries=max_retries,
                    retry_backoff=retry_backoff,
                    timeout=timeout,
                ): (lat_idx, lon_idx)
                for lat_idx, lon_idx in tile_keys
            }
            for future in as_completed(future_map):
                tile_key = future_map[future]
                try:
                    tile_results[tile_key] = future.result()
                except Exception as exc:
                    print(f"Tile {tile_key} failed: {exc}")
                    tile_results[tile_key] = None
    else:
        for tile_key in tile_keys:
            lat_idx, lon_idx = tile_key
            tile_results[tile_key] = _call_load_tile(
                _load_tile,
                lat_idx,
                lon_idx,
                cache_dir=cache_dir,
                max_retries=max_retries,
                retry_backoff=retry_backoff,
                timeout=timeout,
            )

    for tile_num, (tile_key, points_list) in enumerate(tile_groups.items(), 1):
        tile_data = tile_results.get(tile_key)
        if tile_data is None:
            print(f"  [{tile_num}/{total_tiles}] tile {tile_key} failed to load, skipping {len(points_list)} point(s)")
            continue

        if tile_data == "OCEAN":
            for idx, _, _ in points_list:
                pdf.at[idx, 'elevation_m'] = 0.0
                pdf.at[idx, 'slope_degrees'] = 0.0
                pdf.at[idx, 'slope_percent'] = 0.0
                pdf.at[idx, 'aspect_degrees'] = 0.0
                pdf.at[idx, 'aspect_direction'] = 'N'
            continue

        dem_array, meta = tile_data
        transform = meta['transform']
        pixel_size_y = abs(meta['res'][1]) * 111320

        point_rows = np.array([lat for _, lat, _ in points_list], dtype=float)
        point_cols = np.array([lon for _, _, lon in points_list], dtype=float)
        row_idx = np.floor((point_rows - transform.f) / transform.e).astype(int)
        col_idx = np.floor((point_cols - transform.c) / transform.a).astype(int)

        valid_point_mask = (
            (row_idx >= 0) &
            (row_idx < dem_array.shape[0]) &
            (col_idx >= 0) &
            (col_idx < dem_array.shape[1])
        )

        for point_idx, (row, col, lat, lon) in enumerate(zip(row_idx, col_idx, point_rows, point_cols)):
            if not valid_point_mask[point_idx]:
                print(f"    Point ({lat}, {lon}) fell outside tile {tile_key} bounds (row={row}, col={col})")
                continue
            idx = points_list[point_idx][0]
            try:
                elevation = float(dem_array[row, col])
                pixel_size_x = abs(meta['res'][0]) * 111320 * np.cos(np.radians(lat))
                slope_deg, slope_pct, aspect_deg = _compute_slope_at_pixel(
                    dem_array, row, col, pixel_size_y, pixel_size_x
                )
                pdf.at[idx, 'elevation_m'] = round(elevation, 1)
                pdf.at[idx, 'slope_degrees'] = round(slope_deg, 2)
                pdf.at[idx, 'slope_percent'] = round(slope_pct, 2)
                pdf.at[idx, 'aspect_degrees'] = round(aspect_deg, 1)
                pdf.at[idx, 'aspect_direction'] = get_aspect_direction(aspect_deg)
            except Exception as exc:
                print(f"    Error processing point ({lat}, {lon}): {exc}")

        if tile_num % 10 == 0 or tile_num == total_tiles:
            print(f"  [{tile_num}/{total_tiles}] tiles processed")

    matched = pdf['elevation_m'].notna().sum()
    print(f"\nDone. {matched}/{len(pdf)} coordinates enriched globally.")
    return pdf


def main(argv=None):
    parser = argparse.ArgumentParser(description="Enrich a CSV of lat/lon points with global elevation data")
    parser.add_argument("input_csv", help="Path to an input CSV containing latitude and longitude columns")
    parser.add_argument("--output", "-o", required=True, help="Path to write the enriched CSV")
    parser.add_argument("--cache-dir", default=".cache/elevation_tiles", help="Directory for the tile disk cache")
    parser.add_argument("--workers", type=int, default=8, help="Maximum number of tile download workers")
    parser.add_argument("--max-retries", type=int, default=3, help="How many times to retry failed tile downloads")
    parser.add_argument("--retry-backoff", type=float, default=1.0, help="Seconds to wait before each retry")
    parser.add_argument("--timeout", type=int, default=30, help="Per-request timeout in seconds")
    args = parser.parse_args(argv)

    df = pd.read_csv(args.input_csv)
    result = enrich_with_global_elevation(
        df,
        cache_dir=args.cache_dir,
        max_workers=args.workers,
        max_retries=args.max_retries,
        retry_backoff=args.retry_backoff,
        timeout=args.timeout,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)

    print(f"Wrote enriched results to {output_path}")


if __name__ == "__main__":
    main()
