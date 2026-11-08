"""City boundary and study area.

Study area = city boundary ∩ the extent of the aerial imagery used by the
study (`study_area.clip_bbox` in the city's CRS; the imagery itself is not
needed by Track A and is not distributed). Boundaries are read from any
vector file (all polygons merged) or from the ESRI-JSON rings files of the
study pipeline, where every ring is an exterior.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


def read_rings_json(path) -> gpd.GeoSeries:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rings = []
    if "features" in raw:
        for f in raw["features"]:
            rings.extend(f.get("geometry", {}).get("rings", []))
    elif "rings" in raw:
        rings = raw["rings"]
    polys = [Polygon(r) for r in rings if len(r) >= 4]
    geom = unary_union([p if p.is_valid else p.buffer(0) for p in polys])
    sr = raw.get("spatialReference") or {}
    return gpd.GeoSeries([geom], crs=sr.get("latestWkid") or sr.get("wkid") or 4326)


def read_boundary(path) -> gpd.GeoSeries:
    """One merged boundary geometry with its CRS."""
    p = Path(path)
    if p.suffix.lower() == ".json":
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if "rings" in raw or any("rings" in (f.get("geometry") or {})
                                     for f in raw.get("features", [])):
                return read_rings_json(p)
        except (ValueError, AttributeError):
            pass
    from blockmorph.inputs import load_boundary                 # core reader
    return load_boundary(p)


def study_area(city, data_dir) -> tuple[gpd.GeoSeries, gpd.GeoSeries]:
    """(study area, boundary), both in the city's analysis CRS."""
    path = city.file(city.boundary.get("file", "boundary.gpkg"), data_dir)
    if not path or not Path(path).exists():
        raise FileNotFoundError(
            f"{city.id}: boundary file {path} not found - run "
            f"`blockmorph-morphometric fetch boundary --city {city.id}` or provide it")
    b = read_boundary(path).to_crs(city.crs)
    clip = (city.study_area or {}).get("clip_bbox")
    geom = b.iloc[0].intersection(box(*clip)) if clip else b.iloc[0]
    return gpd.GeoSeries([geom], crs=city.crs), b
