from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd


@dataclass(frozen=True)
class ParsedRoute:
    """Parsed route payload extracted from GPX or drawn map data."""

    name: str
    source: str
    points: pd.DataFrame


def _namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[0][1:]
    return ""


def _child_text(element: ET.Element, local_name: str) -> str | None:
    for child in element:
        if child.tag.rsplit("}", 1)[-1] == local_name and child.text:
            return child.text.strip()
    return None


def _dedupe_points(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    result = frame.copy()
    result["point_key"] = (
        result["latitude"].round(6).astype(str)
        + ","
        + result["longitude"].round(6).astype(str)
    )
    result = result.drop_duplicates(subset=["point_key"]).drop(columns=["point_key"])
    result = result.reset_index(drop=True)
    result["point_index"] = result.index + 1
    return result


def parse_gpx_bytes(file_bytes: bytes, fallback_name: str = "uploaded-route") -> ParsedRoute:
    """Parse GPX track or route points into a normalized dataframe.

    The parser keeps the implementation dependency-light so the app can run even
    when optional GPX packages are not installed in the active environment.
    """

    if not file_bytes:
        raise ValueError("The GPX file is empty.")

    try:
        root = ET.fromstring(file_bytes)
    except ET.ParseError as exc:
        raise ValueError("Invalid GPX file: XML parsing failed.") from exc

    namespace = _namespace(root.tag)
    ns = {"gpx": namespace} if namespace else {}
    route_name = (
        root.findtext(".//gpx:name", default=fallback_name, namespaces=ns)
        if namespace
        else root.findtext(".//name", default=fallback_name)
    ) or fallback_name

    rows: list[dict[str, Any]] = []
    point_index = 0

    trksegs = root.findall(".//gpx:trkseg", ns) if namespace else root.findall(".//trkseg")
    rtepts = root.findall(".//gpx:rtept", ns) if namespace else root.findall(".//rtept")

    if trksegs:
        for segment_index, trkseg in enumerate(trksegs, start=1):
            for segment_point_index, trkpt in enumerate(trkseg, start=1):
                latitude = trkpt.attrib.get("lat")
                longitude = trkpt.attrib.get("lon")
                if latitude is None or longitude is None:
                    continue
                point_index += 1
                rows.append(
                    {
                        "route_name": route_name,
                        "source": "gpx-track",
                        "segment_index": segment_index,
                        "segment_point_index": segment_point_index,
                        "point_index": point_index,
                        "latitude": float(latitude),
                        "longitude": float(longitude),
                        "point_name": _child_text(trkpt, "name"),
                        "time": _child_text(trkpt, "time"),
                        "elevation_m": float(_child_text(trkpt, "ele")) if _child_text(trkpt, "ele") else None,
                    }
                )
    elif rtepts:
        for segment_point_index, rtept in enumerate(rtepts, start=1):
            latitude = rtept.attrib.get("lat")
            longitude = rtept.attrib.get("lon")
            if latitude is None or longitude is None:
                continue
            point_index += 1
            rows.append(
                {
                    "route_name": route_name,
                    "source": "gpx-route",
                    "segment_index": 1,
                    "segment_point_index": segment_point_index,
                    "point_index": point_index,
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "point_name": _child_text(rtept, "name"),
                    "time": _child_text(rtept, "time"),
                    "elevation_m": float(_child_text(rtept, "ele")) if _child_text(rtept, "ele") else None,
                }
            )
    else:
        raise ValueError("The GPX file does not contain any route or track points.")

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("The GPX file did not produce any usable route points.")

    frame = _dedupe_points(frame)
    if len(frame) < 2:
        raise ValueError("A route must contain at least two distinct points.")

    return ParsedRoute(name=str(route_name), source=frame.loc[0, "source"], points=frame)


def parse_drawn_route(drawings: list[dict[str, Any]] | dict[str, Any] | None, fallback_name: str = "drawn-route") -> ParsedRoute:
    """Convert a folium/st_folium drawing payload into a route dataframe."""

    if not drawings:
        raise ValueError("No route was drawn on the map.")

    drawings_list: list[dict[str, Any]]
    if isinstance(drawings, dict):
        drawings_list = [drawings]
    else:
        drawings_list = list(drawings)

    coordinates: list[list[float]] | None = None
    for drawing in drawings_list:
        geometry = drawing.get("geometry") if isinstance(drawing, dict) else None
        if not isinstance(geometry, dict):
            continue
        if geometry.get("type") == "LineString":
            coordinates = geometry.get("coordinates")
            if coordinates:
                break
        if geometry.get("type") == "Feature" and geometry.get("geometry", {}).get("type") == "LineString":
            coordinates = geometry["geometry"].get("coordinates")
            if coordinates:
                break

    if not coordinates:
        raise ValueError("The drawn feature must be a line string route.")

    rows = []
    for point_index, (longitude, latitude, *_) in enumerate(coordinates, start=1):
        rows.append(
            {
                "route_name": fallback_name,
                "source": "drawn-route",
                "segment_index": 1,
                "segment_point_index": point_index,
                "point_index": point_index,
                "latitude": float(latitude),
                "longitude": float(longitude),
                "point_name": None,
                "time": None,
                "elevation_m": None,
            }
        )

    frame = pd.DataFrame(rows)
    frame = _dedupe_points(frame)
    if len(frame) < 2:
        raise ValueError("A drawn route must contain at least two distinct points.")

    return ParsedRoute(name=fallback_name, source="drawn-route", points=frame)


def load_route_from_bytes(file_bytes: bytes, file_name: str) -> ParsedRoute:
    """Load a route from GPX bytes or raise a clear validation error."""

    return parse_gpx_bytes(file_bytes, fallback_name=file_name.rsplit(".", 1)[0] or "uploaded-route")
