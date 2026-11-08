"""Building heights for the international cities (study procedure).

Height priority per building: the source's own height (OSM `height` tag or
Overture `height`) > ONE enrichment source per city > floors x 3.2 m; what
is still missing is imputed later by the core's missing-data treatment
(block median, else median of the 10 nearest known heights).

Enrichment sources:
  file    a city file with per-building heights joined by point-in-polygon
          (Manhattan: NYC Open Data building footprints, `height_roof` in
          feet; the tallest part wins);
  globfp  3D-GloBFP per-building heights (column `Height`), joined by the
          building's representative point; several grid tiles are read
          together;
  ob25d   Google Open Buildings 2.5D Temporal building height (2023),
          stored as a 2 m block-max raster: mean of the positive pixels in
          the footprint, else the 5x5 maximum at the representative point;
  auto    automatic selection (`select_height_source`): every available
          candidate is tried on its own on a random sample of 500
          buildings (seed 42); the highest-ranked candidate covering at
          least 70 % of the sample wins (rank: file > osm > globfp > ob25d),
          else the best-covering one. The decision is recorded.

Heights outside 2 m .. max_height_m are discarded. Ported from the study
pipeline's prep.py (same numbers, same order of operations).
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from blockmorph.inputs import log

HEIGHT_SOURCE_RANK = ("file", "osm", "globfp", "ob25d")
HEIGHT_SAMPLE = 500
HEIGHT_MIN_COVERAGE = 0.70
SAMPLE_SEED = 42


def _valid(h: pd.Series, max_height_m: float) -> pd.Series:
    return h.where((h >= 2.0) & (h <= max_height_m))


def heights_from_file(gdf, path, field, crs, max_height_m=260.0, unit="m"):
    """Fill missing heights from a footprint file with a height column."""
    path = Path(path)
    if not path.exists() or not field:
        log("[heights] height file/field missing - enrichment skipped")
        return gdf
    src = gpd.read_file(path, columns=[field, "geometry"]).to_crs(crs)
    h = pd.to_numeric(src[field], errors="coerce")
    if unit == "ft":
        h = h * 0.3048
    pts = gpd.GeoDataFrame({"h": h}, geometry=src.geometry.representative_point(),
                           crs=crs).dropna(subset=["h"])
    j = gpd.sjoin(pts, gdf[["geometry"]], how="inner", predicate="within")
    h_by_fp = j.groupby("index_right")["h"].max()          # tallest part wins
    h_by_fp = _valid(h_by_fp, max_height_m)
    before = gdf["height_m"].notna().mean()
    gdf["height_m"] = gdf["height_m"].fillna(h_by_fp.reindex(gdf.index))
    log(f"[heights] file heights: {before:.0%} -> {gdf['height_m'].notna().mean():.0%}")
    return gdf


def heights_from_globfp(gdf, shp_paths, crs, max_height_m=260.0):
    """Fill missing heights from 3D-GloBFP tile(s) (column `Height`)."""
    paths = [Path(p) for p in shp_paths or []]
    paths = [p for p in paths if p.exists()]
    if not paths:
        log("[heights] 3D-GloBFP tiles missing - enrichment skipped")
        return gdf
    bbox = tuple(gpd.GeoSeries(gdf.geometry.union_all().envelope, crs=crs)
                 .to_crs(4326).total_bounds)
    parts = []
    for p in paths:
        g = gpd.read_file(p, bbox=bbox)
        if len(g):
            parts.append(g[["Height", "geometry"]])
    if not parts:
        log("[heights] 3D-GloBFP: no polygons inside the city extent")
        return gdf
    gb = pd.concat(parts, ignore_index=True)
    gb = gpd.GeoDataFrame(gb, geometry="geometry", crs=parts[0].crs).to_crs(crs)
    pts = gpd.GeoDataFrame(geometry=gdf.geometry.representative_point(), index=gdf.index)
    j = gpd.sjoin(pts, gb[["Height", "geometry"]], how="left", predicate="within")
    h = pd.to_numeric(j[~j.index.duplicated(keep="first")]["Height"], errors="coerce")
    h = _valid(h, max_height_m)
    before = gdf["height_m"].notna().mean()
    gdf["height_m"] = gdf["height_m"].fillna(h)
    log(f"[heights] 3D-GloBFP: {before:.0%} -> {gdf['height_m'].notna().mean():.0%} "
        f"({len(gb)} polygons in extent)")
    return gdf


def heights_from_ob25d(gdf, tif_path, max_height_m=260.0):
    """Fill missing heights from the Open Buildings 2.5D height raster."""
    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import rowcol
    from scipy.ndimage import maximum_filter
    tif_path = Path(tif_path)
    if not tif_path.exists():
        log("[heights] Open Buildings 2.5D raster missing - enrichment skipped")
        return gdf
    with rasterio.open(tif_path) as src:
        arr = src.read(1)
        tr, rcrs = src.transform, src.crs
    g = gdf.to_crs(rcrs)
    ids = rasterize(((geom, i + 1) for i, geom in enumerate(g.geometry)),
                    out_shape=arr.shape, transform=tr, fill=0, dtype="int32",
                    all_touched=True)
    valid = (arr > 0) & (ids > 0)
    n = len(g)
    sums = np.bincount(ids[valid], weights=arr[valid], minlength=n + 1)
    cnts = np.bincount(ids[valid], minlength=n + 1)
    h = np.full(n, np.nan)
    has = cnts[1:] > 0
    h[has] = sums[1:][has] / cnts[1:][has]
    mx = maximum_filter(arr, size=5)                 # footprints smaller than a cell
    pts = g.geometry.representative_point()
    rows, cols = rowcol(tr, pts.x.values, pts.y.values)
    rows = np.clip(np.asarray(rows), 0, arr.shape[0] - 1)
    cols = np.clip(np.asarray(cols), 0, arr.shape[1] - 1)
    h2 = mx[rows, cols]
    fill = ~has & (h2 > 0)
    h[fill] = h2[fill]
    hs = _valid(pd.Series(h, index=gdf.index), max_height_m)
    before = gdf["height_m"].notna().mean()
    gdf["height_m"] = gdf["height_m"].fillna(hs)
    log(f"[heights] Open Buildings 2.5D: {before:.0%} -> {gdf['height_m'].notna().mean():.0%}")
    return gdf


def candidates(city, data_dir, crs) -> dict:
    """Available enrichment functions of a city, by source name."""
    hc = city.heights
    mh = city.max_height_m
    out = {}
    if hc.get("file"):
        f = city.file(hc["file"], data_dir)
        if f and Path(f).exists():
            out["file"] = lambda g, _f=f: heights_from_file(g, _f, hc.get("field"), crs, mh,
                                                            hc.get("unit", "m"))
    out["osm"] = None
    cand = hc.get("candidates", {}) or {}
    tiles = [p for p in (_find(t, city, data_dir) for t in cand.get("globfp", []) or []) if p]
    if tiles:
        out["globfp"] = lambda g, _t=tiles: heights_from_globfp(g, _t, crs, mh)
    if cand.get("ob25d"):
        t = city.file(cand["ob25d"], data_dir)
        if t and Path(t).exists():
            out["ob25d"] = lambda g, _t=t: heights_from_ob25d(g, _t, mh)
    return out


def _find(name, city, data_dir) -> str | None:
    """A 3D-GloBFP tile: <data_dir>/<city>/<name>, else anywhere under
    <data_dir>/globfp/."""
    p = Path(city.file(name, data_dir))
    if p.exists():
        return str(p)
    hits = sorted((Path(data_dir) / "globfp").glob(f"**/{Path(name).name}"))
    return str(hits[0]) if hits else None


def select_height_source(gdf, cands: dict, seed: int = SAMPLE_SEED):
    """ONE height source per city (see module notes). Returns (chosen,
    decision table)."""
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(gdf), min(HEIGHT_SAMPLE, len(gdf)), replace=False)
    sample = gdf.iloc[idx]
    table = []
    for name in HEIGHT_SOURCE_RANK:
        if name not in cands:
            continue
        if name == "osm":
            cov = float(sample["height_m"].notna().mean())
        else:
            probe = sample.copy()
            probe["height_m"] = np.nan                 # the source on its own
            probe = cands[name](probe)
            cov = float(probe["height_m"].notna().mean())
        table.append({"source": name, "sample_coverage": round(cov, 3)})
    chosen = next((r["source"] for r in table
                   if r["sample_coverage"] >= HEIGHT_MIN_COVERAGE), None)
    if chosen is None and table:
        chosen = max(table, key=lambda r: r["sample_coverage"])["source"]
    return chosen, table


def enrich(gdf, city, data_dir, crs):
    """Apply the city's height policy (none | file | globfp | ob25d | auto).
    Returns (buildings, decision record)."""
    policy = (city.heights or {}).get("policy", "none") or "none"
    if policy == "none":
        return gdf, {"policy": "none"}
    cands = candidates(city, data_dir, crs)
    if policy == "auto":
        chosen, table = select_height_source(gdf, cands)
        decision = {"policy": "auto", "chosen": chosen, "candidates": table,
                    "rule": f"highest-ranked source with >= {HEIGHT_MIN_COVERAGE:.0%} coverage "
                            f"on a {HEIGHT_SAMPLE}-building sample, else the best-covering; "
                            f"rank {list(HEIGHT_SOURCE_RANK)}"}
        log("[heights] candidates: " + ", ".join(f"{r['source']} {r['sample_coverage']:.0%}"
                                                 for r in table) + f" -> chosen: {chosen}")
    else:
        chosen, decision = policy, {"policy": policy, "chosen": policy}
        if policy not in cands:
            log(f"[heights] source '{policy}' not available - enrichment skipped")
            decision["available"] = False
            return gdf, decision
    if chosen and chosen != "osm":
        gdf = cands[chosen](gdf)
    return gdf, decision


def write_decision(decision: dict, path):
    Path(path).write_text(json.dumps(decision, indent=2), encoding="utf-8")
