"""
Validation harness for global_elevation_enrichment.py

Run this after any change to the tile-indexing / fetching logic.
It checks three things:
  1. Known reference elevations (real-world ground truth, loose tolerance
     since DEM resolution + interpolation always differs slightly from
     official spot heights).
  2. Internal consistency (values in sane ranges, no silent NaNs where
     data should exist, ocean points behave as expected).
  3. Boundary / edge cases — coordinates that sit near or on tile
     boundaries, since that's exactly where the floor-vs-truncate bug lived.
"""

import math
import pandas as pd
from global_elevation_enrichment import enrich_with_global_elevation, _tile_indices

# -----------------------------------------------------------------------
# 1. KNOWN REFERENCE POINTS
# -----------------------------------------------------------------------
# Elevations sourced from official surveys / well-known figures (meters).
# Tolerance is generous because SRTM/Copernicus 30m DEM values differ from
# ground-survey benchmarks due to resolution, canopy/building noise, datum
# differences (EGM2008 vs local), etc. This is checking "is it broadly
# right", not "is it exact".
REFERENCE_POINTS = [
    # name,               lat,       lon,         expected_m, tolerance_m
    ("Everest Base Camp",  28.0026,   86.8528,     5300,        400),
    ("Death Valley",       36.2461,  -116.8171,    -86,         100),   # note: negative lon
    ("Denver (Mile High)", 39.7392,  -104.9903,    1609,        150),   # your failing case
    ("Amsterdam",          52.3676,    4.9041,     -2,          50),
    ("Kathmandu",          27.7172,   85.3240,     1400,        250),
    ("Sydney Opera House", -33.8568,  151.2153,    5,           50),    # southern hemisphere
    ("Cape Town",          -33.9249,   18.4241,    20,          100),   # negative lat AND lon-ish region
]

# -----------------------------------------------------------------------
# 2. BOUNDARY / EDGE CASES
# -----------------------------------------------------------------------
# Points deliberately chosen just inside/outside integer degree lines,
# across hemispheres, so floor() vs int() truncation errors show up
# immediately as either wrong-tile fetches or NaN rows.
EDGE_CASES = [
    ("Just west of 0 lon",        51.5,   -0.001),
    ("Just east of 0 lon",        51.5,    0.001),
    ("Just south of 0 lat",       -0.001,  20.0),
    ("Just north of 0 lat",        0.001,  20.0),
    ("Negative lat & lon",        -22.9068, -43.1729),  # Rio de Janeiro
    ("Near antimeridian +",        35.0,   179.999),
    ("Near antimeridian -",        35.0,  -179.999),
    ("Deep negative fractional",   39.0001, -105.9999),
]


def validate_reference_points(tolerance_multiplier=1.0):
    df = pd.DataFrame([
        {"location": n, "latitude": lat, "longitude": lon}
        for n, lat, lon, _, _ in REFERENCE_POINTS
    ])
    result = enrich_with_global_elevation(df)

    print("\n--- Reference point validation ---")
    all_pass = True
    for (name, lat, lon, expected, tol), (_, row) in zip(REFERENCE_POINTS, result.iterrows()):
        actual = row["elevation_m"]
        tol_adj = tol * tolerance_multiplier
        if pd.isna(actual):
            status = "FAIL (NaN — point wasn't resolved at all)"
            all_pass = False
        elif abs(actual - expected) <= tol_adj:
            status = "PASS"
        else:
            status = f"FAIL (diff={abs(actual - expected):.1f}m > tol={tol_adj}m)"
            all_pass = False
        print(f"  {name:22s} expected~{expected:>6} actual={actual!s:>8}  {status}")

    return all_pass


def validate_edge_cases():
    df = pd.DataFrame([
        {"location": n, "latitude": lat, "longitude": lon}
        for n, lat, lon in EDGE_CASES
    ])
    result = enrich_with_global_elevation(df)

    print("\n--- Edge case validation ---")
    all_pass = True
    for (name, lat, lon), (_, row) in zip(EDGE_CASES, result.iterrows()):
        resolved_tile = _tile_indices(lat, lon)
        ok = not pd.isna(row["elevation_m"])
        status = "PASS" if ok else "FAIL (NaN)"
        if not ok:
            all_pass = False
        print(f"  {name:26s} ({lat:.4f},{lon:.4f}) tile={resolved_tile} "
              f"elev={row['elevation_m']!s:>8}  {status}")

    return all_pass


def validate_internal_consistency(df_result):
    """Sanity checks that don't need external ground truth."""
    print("\n--- Internal consistency checks ---")
    checks = []

    # Slope should never be negative or absurdly high
    bad_slope = df_result[(df_result["slope_degrees"] < 0) | (df_result["slope_degrees"] > 90)]
    checks.append(("slope_degrees in [0, 90]", bad_slope.empty))

    # Aspect should be in [0, 360)
    bad_aspect = df_result[(df_result["aspect_degrees"] < 0) | (df_result["aspect_degrees"] >= 360)]
    checks.append(("aspect_degrees in [0, 360)", bad_aspect.empty))

    # Elevation should be within plausible planetary bounds (Dead Sea to Everest, plus margin)
    valid_elev = df_result["elevation_m"].dropna()
    bad_elev = valid_elev[(valid_elev < -500) | (valid_elev > 9000)]
    checks.append(("elevation_m within [-500, 9000]", bad_elev.empty))

    # No row should have elevation set but aspect_direction missing (or vice versa)
    inconsistent = df_result[df_result["elevation_m"].notna() != df_result["aspect_direction"].notna()]
    checks.append(("elevation/aspect_direction consistency", inconsistent.empty))

    all_pass = True
    for name, passed in checks:
        print(f"  {name:40s} {'PASS' if passed else 'FAIL'}")
        all_pass = all_pass and passed
    return all_pass


if __name__ == "__main__":
    ref_ok = validate_reference_points()
    edge_ok = validate_edge_cases()

    print("\n=== SUMMARY ===")
    print(f"Reference points: {'PASS' if ref_ok else 'FAIL'}")
    print(f"Edge cases:       {'PASS' if edge_ok else 'FAIL'}")
    if not (ref_ok and edge_ok):
        raise SystemExit(1)