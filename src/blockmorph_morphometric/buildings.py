"""Building footprints of the international cities (study procedure).

Sources (city YAML `buildings.source`):
  osm       OpenStreetMap building=* polygons fetched with osmnx inside the
            city boundary (Manhattan, Amsterdam);
  overture  Overture Maps footprints (release 2026-08-19.0) fetched for the
            boundary bbox by `blockmorph-morphometric fetch buildings`: either the
            OSM polygons only (`overture_datasets: [OpenStreetMap]`; Montreal,
            Barcelona, Tokyo) or the conflated set (Google Open Buildings +
            OSM + Microsoft; the Global-South cities and Sydney). Overture's
            `class` (else `subtype`) plays the role of the OSM building tag;
  file      any footprint file with optional `height_m`/`floors` columns
            (City A: the core archive's buildings).

Cleaning, in this order (as in the study): non-building types dropped
(roof, carport, shed, garage(s), greenhouse, hut, tent, ruins,
construction); floors > 0; heights 2 m .. max_height_m; geometries made
valid, the largest part kept, polygons only; footprints below
min_area_m2 dropped (25 m2; 10 m2 in informal-fabric cities); stacked
duplicate footprints merged (tallest wins); heights enriched
(`heights.enrich`); height = floors x 3.2 m where only floors are known;
floors = round(height / 3.2) where only the height is known; footprint,
volume and floor area; buildings whose representative point lies outside
the study area dropped.

Ported from the study pipeline's prep.py (construction years and land use are not
part of this repository).
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from blockmorph.inputs import OSM_DROP_TYPES, log

from . import heights as H

FLOOR_HEIGHT_M = 3.2


def standardise_tags(g: gpd.GeoDataFrame, max_height_m: float) -> gpd.GeoDataFrame:
    """OSM-style tag columns (btype / levels / height_tag) -> floors, height_m."""
    g = g.copy()
    g["btype"] = g["btype"].fillna("yes")
    g = g[~g["btype"].isin(OSM_DROP_TYPES)]
    g["floors"] = pd.to_numeric(g["levels"], errors="coerce")
    g["floors"] = g["floors"].where(g["floors"] > 0)
    h = (g["height_tag"].str.extract(r"([\d.]+)")[0]).astype(float)
    g["height_m"] = h.where((h >= 2.0) & (h <= max_height_m))
    return g[["geometry", "btype", "floors", "height_m"]]


def load_overture(path, crs) -> gpd.GeoDataFrame:
    """Overture footprints (GeoParquet written by acquire.fetch_overture)
    -> OSM-style tag columns, in the analysis CRS."""
    src = gpd.read_parquet(path).to_crs(crs)

    def get(c):
        return src[c] if c in src.columns else pd.Series(None, index=src.index)
    g = gpd.GeoDataFrame({"btype": get("class").fillna(get("subtype")),
                          "levels": get("num_floors"), "height_tag": get("height"),
                          "source": get("source")}, geometry=src.geometry.values, crs=src.crs)
    for c in ("btype", "levels", "height_tag", "source"):
        g[c] = g[c].astype("string")
    g = g.reset_index(drop=True)
    share = g["source"].value_counts(normalize=True)
    log(f"[buildings] {len(g)} Overture footprints; sources: "
        + ", ".join(f"{k} {v:.0%}" for k, v in share.items()))
    return g


def load_osm(boundary_wgs, crs) -> gpd.GeoDataFrame:
    """OSM building polygons inside the boundary (osmnx), OSM-style tags."""
    import osmnx as ox
    ox.settings.requests_timeout = 600
    raw = ox.features_from_polygon(boundary_wgs, {"building": True})
    raw = raw[raw.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    cols = {"building": "btype", "building:levels": "levels", "height": "height_tag"}
    g = raw[[c for c in cols if c in raw.columns] + ["geometry"]].rename(columns=cols)
    g = g.reset_index(drop=True).to_crs(crs)
    for c in ("btype", "levels", "height_tag"):
        if c not in g.columns:
            g[c] = None
        g[c] = g[c].astype("string")
    log(f"[buildings] {len(g)} OSM buildings")
    return g


def load_file(path, crs, max_height_m: float) -> gpd.GeoDataFrame:
    """Footprints with optional height_m (or height) and floors (or levels)."""
    from blockmorph.inputs import _file_buildings          # core reader (v1.0.0)
    g = _file_buildings(path).to_crs(crs)
    g["floors"] = g["floors"].where(g["floors"] > 0)
    g["height_m"] = g["height_m"].where((g["height_m"] >= 2.0) & (g["height_m"] <= max_height_m))
    return g


def clean_footprints(g: gpd.GeoDataFrame, min_area_m2: float, crs) -> gpd.GeoDataFrame:
    g = g.copy()
    g["geometry"] = g.geometry.make_valid()
    g = g[~g.geometry.is_empty & g.geometry.notna()]
    ex = g.explode(index_parts=False)
    ex["__a"] = ex.geometry.area
    g = ex.sort_values("__a").groupby(level=0).tail(1).drop(columns="__a")
    g = g[g.geometry.geom_type == "Polygon"]
    g = g[g.geometry.area >= min_area_m2]
    wkb = g.geometry.to_wkb()                       # stacked duplicate parts: tallest wins
    g = g.sort_values("height_m", na_position="first")
    agg = {c: "last" for c in g.columns}
    agg.update({"floors": "max", "height_m": "max"})
    before = len(g)
    g = gpd.GeoDataFrame(g.groupby(wkb, sort=False).agg(agg), geometry="geometry", crs=crs)
    g = g.reset_index(drop=True)
    if before - len(g):
        log(f"[buildings] merged {before - len(g)} duplicate footprints")
    return g


def derive_3d(g: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    g["height_m"] = g["height_m"].fillna(g["floors"] * FLOOR_HEIGHT_M)
    g["floors"] = g["floors"].fillna((g["height_m"] / FLOOR_HEIGHT_M).round())
    g["footprint_m2"] = g.geometry.area
    g["volume_m3"] = g["footprint_m2"] * g["height_m"]
    g["floor_area_m2"] = g["footprint_m2"] * g["floors"]
    return g


def prepare_buildings(city, area: gpd.GeoSeries, boundary: gpd.GeoSeries, data_dir):
    """Clean buildings of one city in its analysis CRS. `area` = study area,
    `boundary` = the full boundary (OSM download extent). Returns
    (buildings, height decision)."""
    crs = city.crs
    src = city.buildings.get("source", "osm")
    if src == "overture":
        g = standardise_tags(load_overture(city.file(city.buildings["file"], data_dir), crs),
                             city.max_height_m)
    elif src == "osm":
        g = standardise_tags(load_osm(boundary.to_crs(4326).iloc[0], crs), city.max_height_m)
    elif src == "file":
        g = load_file(city.file(city.buildings["file"], data_dir), crs, city.max_height_m)
    else:
        raise ValueError(f"{city.id}: buildings.source osm | overture | file")
    g = clean_footprints(g, city.min_building_area_m2, crs)
    g, decision = H.enrich(g, city, data_dir, crs)
    g = derive_3d(g)
    g = g[g.geometry.representative_point().within(area.iloc[0])].reset_index(drop=True)
    g = g[["geometry", "floors", "height_m", "footprint_m2", "volume_m3", "floor_area_m2"]]
    log(f"[buildings] {city.id}: {len(g)} buildings in the study area; height known "
        f"{g['height_m'].notna().mean():.0%}")
    return gpd.GeoDataFrame(g, geometry="geometry", crs=crs), decision
