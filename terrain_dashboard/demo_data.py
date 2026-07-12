from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from terrain_dashboard import gpx_parser


APP_DIR = Path(__file__).resolve().parent
DEMO_TRAILS_DIR = APP_DIR / "demo_trails"


@lru_cache(maxsize=1)
def load_demo_routes() -> tuple[gpx_parser.ParsedRoute, ...]:
	"""Load all bundled demo GPX routes."""

	routes: list[gpx_parser.ParsedRoute] = []
	if not DEMO_TRAILS_DIR.exists():
		return tuple(routes)

	for gpx_path in sorted(DEMO_TRAILS_DIR.glob("*.gpx")):
		fallback_name = gpx_path.stem.replace("_", " ").title()
		routes.append(gpx_parser.load_route_from_bytes(gpx_path.read_bytes(), fallback_name))
	return tuple(routes)


def demo_route_names() -> list[str]:
	return [route.name for route in load_demo_routes()]
