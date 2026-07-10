from __future__ import annotations

import html
from datetime import datetime, timezone
from io import BytesIO
from typing import Iterable
from xml.etree import ElementTree as ET

from terrain_dashboard.analytics import RouteAnalysis


def route_points_to_csv_bytes(analysis: RouteAnalysis) -> bytes:
    """Export the enriched route dataframe to CSV bytes."""

    return analysis.points.to_csv(index=False).encode("utf-8")


def route_points_to_gpx_bytes(analysis: RouteAnalysis) -> bytes:
    """Export a GPX document with enriched terrain values preserved in extensions."""

    gpx = ET.Element(
        "gpx",
        attrib={
            "version": "1.1",
            "creator": "HikeIQ",
            "xmlns": "http://www.topografix.com/GPX/1/1",
        },
    )
    metadata = ET.SubElement(gpx, "metadata")
    ET.SubElement(metadata, "name").text = analysis.route_name
    ET.SubElement(metadata, "time").text = datetime.now(timezone.utc).isoformat()
    trk = ET.SubElement(gpx, "trk")
    ET.SubElement(trk, "name").text = analysis.route_name
    trkseg = ET.SubElement(trk, "trkseg")

    for _, row in analysis.points.iterrows():
        trkpt = ET.SubElement(trkseg, "trkpt", lat=f"{float(row['latitude']):.6f}", lon=f"{float(row['longitude']):.6f}")
        if row.get("elevation_m") is not None and row.get("elevation_m") == row.get("elevation_m"):
            ET.SubElement(trkpt, "ele").text = f"{float(row['elevation_m']):.2f}"
        if row.get("point_name"):
            ET.SubElement(trkpt, "name").text = str(row["point_name"])
        extensions = ET.SubElement(trkpt, "extensions")
        for key in ["slope_degrees", "slope_percent", "aspect_degrees", "aspect_direction", "terrain_steepness"]:
            value = row.get(key)
            if value is None or value != value:
                continue
            ET.SubElement(extensions, key).text = str(value)

    return ET.tostring(gpx, encoding="utf-8", xml_declaration=True)


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf_lines(analysis: RouteAnalysis) -> list[str]:
    lines = [
        "HikeIQ Route Report",
        f"Route: {analysis.route_name}",
        f"Distance: {analysis.total_distance_km:.2f} km",
        f"Elevation gain: {analysis.elevation_gain_m:.0f} m",
        f"Elevation loss: {analysis.elevation_loss_m:.0f} m",
        f"Difficulty: {analysis.difficulty_label} ({analysis.difficulty_score}/100)",
        f"Estimated hiking time: {analysis.hiking_time_hours:.2f} hours",
        f"Calories burned: {analysis.calories_burned} kcal",
        "",
        "Route insights:",
    ]
    lines.extend(f"- {insight}" for insight in analysis.insights[:4])
    return lines


def route_report_pdf_bytes(analysis: RouteAnalysis) -> bytes:
    """Create a compact single-page PDF summary without external dependencies."""

    lines = _build_pdf_lines(analysis)
    content_lines = ["BT", "/F1 12 Tf", "50 770 Td"]
    for index, line in enumerate(lines):
        escaped = _escape_pdf_text(line)
        if index == 0:
            content_lines.append("/F1 18 Tf")
            content_lines.append(f"({escaped}) Tj")
            content_lines.append("/F1 12 Tf")
        else:
            content_lines.append(f"0 -18 Td ({escaped}) Tj")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n"
    )
    objects.append(b"4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
    objects.append(
        f"5 0 obj<< /Length {len(stream)} >>stream\n".encode("latin-1") + stream + b"\nendstream endobj\n"
    )

    buffer = BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(buffer.tell())
        buffer.write(obj)

    xref_position = buffer.tell()
    buffer.write(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        buffer.write(f"{offset:010d} 00000 n \n".encode("latin-1"))
    buffer.write(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF".encode("latin-1")
    )
    return buffer.getvalue()


def figure_to_png_bytes(figure) -> bytes | None:
    """Render a Plotly figure to PNG bytes if the image renderer is available."""

    try:
        import plotly.io as pio
    except Exception:
        return None

    try:
        return pio.to_image(figure, format="png", engine="kaleido")
    except Exception:
        return None
