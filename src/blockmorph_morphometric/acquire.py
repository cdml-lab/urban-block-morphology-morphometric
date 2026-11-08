"""Acquisition of the open inputs of the international cities (network).

    blockmorph-morphometric fetch boundary  --set universal --city RIO
    blockmorph-morphometric fetch buildings --set universal --city RIO
    blockmorph-morphometric fetch heights   --set universal --city RIO
    blockmorph-morphometric fetch streets   --set universal --city TYO   (Overture road segments)

Everything is written to `<data_dir>/<city id>/`. Nothing here is needed
to reproduce the published partitions from the study's descriptor tables;
it documents (and re-runs) how the inputs were obtained. Live services
change: OSM and Overture are updated continuously and Overture keeps only
recent releases online, so a fetch today is not byte-identical to the
study's inputs (pinned Overture release: 2026-08-19.0).

Boundary kinds (city YAML `boundary.kind`):
  osm_relations         union of OSM administrative relations (Nominatim
                        lookup by id) plus optional Nominatim name queries;
  gadm                  a GADM 4.1 level-2 selection (Cairo);
  nyc_borough           NYC DCP borough boundary, largest polygon;
  amsterdam_stadsdelen  union of named Amsterdam districts, largest polygon;
  file                  supplied by the user (City A: on request).
For osm_relations and gadm the union is closed by 20 m (hairline gaps),
clipped to the country's GADM level-0 land polygon, and only parts of at
least 0.25 km2 within 2 km of the largest part are kept. As in the study,
only exterior rings are kept (holes are not written) and coordinates are
rounded to 1e-7 degrees.

Ported from the study pipeline's fetch scripts (universal cities, Manhattan,
Amsterdam). Optional dependencies: requests, duckdb (Overture), rasterio
(Open Buildings 2.5D) - `pip install urban-block-morphology-morphometric[fetch]`.
"""
from __future__ import annotations

import io
import json
import re
import time
import zipfile
from pathlib import Path

import numpy as np

UA = {"User-Agent": "urban-block-morphology-morphometric (academic research; Python requests)"}
OVERTURE_RELEASE = "2026-08-19.0"
OVERTURE = ("s3://overturemaps-us-west-2/release/{release}/"
            "theme=buildings/type=building/*")
ZENODO_GLOBFP = "https://zenodo.org/api/records/11319912"
OB25D = "https://storage.googleapis.com/open-buildings-temporal-data/"
OB25D_API = "https://storage.googleapis.com/storage/v1/b/open-buildings-temporal-data/o"
OB25D_YEAR = "2023"
GADM = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_{iso}_{lvl}.json.zip"
NYC_BOROUGHS = ("https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/"
                "NYC_Borough_Boundary/FeatureServer/0/query")
NYC_FOOTPRINTS = "https://data.cityofnewyork.us/resource/5zhs-2jue.geojson"
AMS_STADSDELEN = "https://api.data.amsterdam.nl/v1/gebieden/stadsdelen/"
ISO3 = {"MTL": "CAN", "BCN": "ESP", "RIO": "BRA", "SAO": "BRA", "NBO": "KEN",
        "CAI": "EGY", "LOS": "NGA", "BOM": "IND", "TYO": "JPN", "SYD": "AUS"}


def _requests():
    import requests
    return requests


def city_dir(city, data_dir) -> Path:
    d = Path(data_dir) / city.id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------- boundary
def write_boundary(geom_wgs, path: Path):
    """Exterior rings only, one polygon feature per ring, 1e-7 degrees."""
    import geopandas as gpd
    from shapely.geometry import Polygon
    polys = [geom_wgs] if geom_wgs.geom_type == "Polygon" else list(geom_wgs.geoms)
    rings = [Polygon([(round(x, 7), round(y, 7)) for x, y in p.exterior.coords])
             for p in polys]
    gpd.GeoDataFrame(geometry=rings, crs=4326).to_file(path)
    print(f"[boundary] {path.name}: {len(rings)} ring(s)")


def _gadm(iso: str, lvl: int, cache: Path):
    import geopandas as gpd
    cache.mkdir(parents=True, exist_ok=True)
    local = cache / f"gadm41_{iso}_{lvl}.json"
    if not local.exists():
        r = _requests().get(GADM.format(iso=iso, lvl=lvl), headers=UA, timeout=300)
        r.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        local.write_bytes(zf.read(zf.namelist()[0]))
    return gpd.read_file(local)


def fetch_boundary(city, data_dir):
    import geopandas as gpd
    from shapely.geometry import shape
    from shapely.ops import unary_union
    spec = city.boundary
    kind = spec.get("kind")
    out = city_dir(city, data_dir) / spec.get("file", "boundary.gpkg")
    req = _requests()
    if kind == "nyc_borough":
        r = req.get(NYC_BOROUGHS, params={"where": f"BoroCode={spec.get('borough_code', 1)}",
                                          "outFields": "BoroName", "f": "geojson",
                                          "outSR": "4326"}, headers=UA, timeout=120)
        r.raise_for_status()
        geom = shape(r.json()["features"][0]["geometry"])
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda p: p.area)
        return write_boundary(geom, out)
    if kind == "amsterdam_stadsdelen":
        want = set(spec.get("districts", []))
        r = req.get(AMS_STADSDELEN, params={"_format": "geojson", "_pageSize": "20"},
                    headers=UA, timeout=120)
        r.raise_for_status()
        geoms = [shape(f["geometry"]) for f in r.json()["features"]
                 if f["properties"].get("naam") in want]
        if len(geoms) != len(want):
            raise RuntimeError(f"expected {len(want)} districts, got {len(geoms)}")
        merged = unary_union(geoms).buffer(0)
        if merged.geom_type == "MultiPolygon":
            merged = max(merged.geoms, key=lambda p: p.area)
        return write_boundary(merged, out)
    if kind not in ("osm_relations", "gadm"):
        raise ValueError(f"{city.id}: boundary kind '{kind}' is not fetched (supply the file)")
    gcache = Path(data_dir) / "gadm"
    geoms = []
    if kind == "gadm":
        g = _gadm(spec["gadm"]["iso3"], spec["gadm"]["level"], gcache)
        lvl = spec["gadm"]["level"]
        g = g[g[f"NAME_{lvl - 1}"].str.contains(spec["gadm"]["name1"], case=False)]
        sel = g[g[f"NAME_{lvl}"].isin(set(spec["names"]))]
        missing = set(spec["names"]) - set(sel[f"NAME_{lvl}"])
        if missing:
            print(f"[boundary] GADM names not found: {sorted(missing)}")
        geoms = list(sel.geometry)
    else:
        import osmnx as ox
        ids = list(spec.get("relations", []))
        if ids:
            g = ox.geocode_to_gdf(ids, by_osmid=True)
            geoms += [row.geometry for _, row in g.iterrows()
                      if row.geometry.geom_type in ("Polygon", "MultiPolygon")]
        for q in spec.get("queries", []) or []:
            row = ox.geocode_to_gdf(q).iloc[0]
            if row.geometry.geom_type in ("Polygon", "MultiPolygon"):
                geoms.append(row.geometry)
            else:
                print(f"[boundary] query {q!r}: no polygon - skipped")
    if not geoms:
        raise RuntimeError(f"{city.id}: no boundary geometry could be fetched")
    u = unary_union(list(gpd.GeoSeries(geoms, crs=4326).to_crs(city.crs).geometry))
    c = float(spec.get("closing_m", 20))
    u = u.buffer(c).buffer(-c)
    lc = spec.get("land_clip") or {}
    iso = lc.get("gadm_level0", ISO3.get(city.id))
    if iso:
        land = _gadm(iso, 0, gcache).geometry.make_valid().to_crs(city.crs).iloc[0]
        u = u.intersection(land).buffer(0)
        parts = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
        main = max(parts, key=lambda g_: g_.area)
        keep = [g_ for g_ in parts if g_.area >= float(lc.get("min_part_km2", 0.25)) * 1e6
                and g_.distance(main) <= float(lc.get("max_gap_m", 2000))]
        u = unary_union(keep)
    wgs = gpd.GeoSeries([u], crs=city.crs).to_crs(4326).iloc[0]
    print(f"[boundary] {city.id}: {u.area / 1e6:.1f} km2")
    return write_boundary(wgs, out)


def _bbox(city, data_dir, pad_deg):
    from .areas import read_boundary
    b = read_boundary(city.file(city.boundary.get("file", "boundary.gpkg"), data_dir))
    x0, y0, x1, y1 = b.to_crs(4326).total_bounds
    return x0 - pad_deg, y0 - pad_deg, x1 + pad_deg, y1 + pad_deg


# --------------------------------------------------------------- buildings
def fetch_overture(city, data_dir, release=None):
    """Overture building footprints for the boundary bbox (+0.003 deg)."""
    import duckdb
    import geopandas as gpd
    release = release or city.buildings.get("overture_release", OVERTURE_RELEASE)
    xmin, ymin, xmax, ymax = _bbox(city, data_dir, 0.003)
    only = city.buildings.get("overture_datasets")
    src_filter = "" if not only else (" AND sources[1].dataset IN ("
                                      + ", ".join(f"'{x}'" for x in only) + ")")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;"
                " SET s3_region='us-west-2';")
    df = con.execute(f"""
        SELECT id, class, subtype, height, num_floors,
               sources[1].dataset AS source, ST_AsWKB(geometry) AS wkb
        FROM read_parquet('{OVERTURE.format(release=release)}', hive_partitioning=1)
        WHERE bbox.xmin <= {xmax} AND bbox.xmax >= {xmin}
          AND bbox.ymin <= {ymax} AND bbox.ymax >= {ymin}{src_filter}
    """).df()
    geoms = gpd.GeoSeries.from_wkb([bytes(b) for b in df["wkb"]], crs=4326)
    gdf = gpd.GeoDataFrame(df.drop(columns="wkb"), geometry=geoms, crs=4326)
    out = city_dir(city, data_dir) / city.buildings.get("file", "buildings_overture.parquet")
    gdf.to_parquet(out)
    print(f"[buildings] {city.id}: {len(gdf):,} Overture footprints (release {release})")
    return out


def fetch_overture_streets(city, data_dir, release=None):
    """The OSM road ways as served by Overture Maps (transportation segments,
    subtype road; `class` = the OSM highway value, subclass 'link' = the
    *_link variants), kept where they touch the study area. The study used
    this source for Tokyo, where no Overpass instance answered."""
    import duckdb
    import geopandas as gpd

    from .areas import study_area
    release = release or city.buildings.get("overture_release", OVERTURE_RELEASE)
    area, _ = study_area(city, data_dir)
    poly = area.to_crs(4326).iloc[0]
    xmin, ymin, xmax, ymax = poly.bounds
    path = (f"s3://overturemaps-us-west-2/release/{release}/"
            "theme=transportation/type=segment/*")
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;"
                " SET s3_region='us-west-2';")
    df = con.execute(f"""
        SELECT class, subclass, ST_AsWKB(geometry) AS wkb
        FROM read_parquet('{path}', hive_partitioning=1)
        WHERE subtype = 'road'
          AND bbox.xmin <= {xmax} AND bbox.xmax >= {xmin}
          AND bbox.ymin <= {ymax} AND bbox.ymax >= {ymin}
    """).df()
    geoms = gpd.GeoSeries.from_wkb([bytes(b) for b in df["wkb"]], crs=4326)
    hw = df["class"].fillna("unclassified").astype(str)
    hw = hw.where(df["subclass"].astype(str) != "link", hw + "_link")
    gdf = gpd.GeoDataFrame({"highway": hw.values}, geometry=geoms.values, crs=4326)
    gdf = gdf[gdf.intersects(poly)].reset_index(drop=True)
    out = city_dir(city, data_dir) / city.streets.get("file", "streets_overture.parquet")
    gdf.to_parquet(out)
    print(f"[streets] {city.id}: {len(gdf):,} Overture road segments (release {release})")
    return out


def fetch_nyc_heights(city, data_dir):
    """NYC Open Data building footprints (roof height) for Manhattan."""
    import geopandas as gpd
    import pandas as pd
    frames, offset, page = [], 0, 50000
    while True:
        r = _requests().get(NYC_FOOTPRINTS, params={
            "$select": "bin,height_roof,the_geom",
            "$where": "bin >= 1000000 and bin < 2000000",
            "$order": "bin", "$limit": str(page), "$offset": str(offset)},
            headers=UA, timeout=300)
        r.raise_for_status()
        gdf = gpd.read_file(io.BytesIO(r.content))
        if not len(gdf):
            break
        frames.append(gdf)
        offset += page
        if len(gdf) < page:
            break
    out = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs=4326)
    path = city_dir(city, data_dir) / city.heights.get("file", "nyc_building_footprints.geojson")
    out.to_file(path, driver="GeoJSON")
    print(f"[heights] {city.id}: {len(out):,} NYC footprints with roof height")
    return path


# ----------------------------------------------------------------- heights
def fetch_globfp(city, data_dir) -> list[str]:
    """3D-GloBFP grid tile(s) covering the boundary (zenodo world grid ->
    figshare part -> tile zip), extracted to <data_dir>/globfp/<grid id>/."""
    import geopandas as gpd

    from .areas import read_boundary
    req = _requests()
    gdir = Path(data_dir) / "globfp"
    gdir.mkdir(parents=True, exist_ok=True)
    poly = read_boundary(city.file(city.boundary.get("file", "boundary.gpkg"), data_dir)) \
        .to_crs(4326).iloc[0]
    rec = req.get(ZENODO_GLOBFP, headers=UA, timeout=60).json()
    files = {f["key"]: f["links"]["self"] for f in rec["files"]}
    grid_dir = gdir / "world_grid"
    if not list(grid_dir.glob("**/*.shp")):
        z = req.get(files["world_grid.zip"], headers=UA, timeout=120).content
        zipfile.ZipFile(io.BytesIO(z)).extractall(grid_dir)
    grid = gpd.read_file(next(grid_dir.glob("**/*.shp")))
    ids = sorted(int(i) for i in grid[grid.intersects(poly)]["grid_ID"])
    txt = req.get(files["data_links.txt"], headers=UA, timeout=60).text
    parts, rng = [], None
    for line in txt.splitlines():
        m = re.search(r"grid ID:\s*(\d+)\s*-\s*(\d+)", line)
        if m:
            rng = (int(m.group(1)), int(m.group(2)))
        m = re.search(r"figshare\.com/.*?/(\d+)\s*$", line.strip())
        if m and rng:
            parts.append((rng[0], rng[1], m.group(1)))
            rng = None
    out = []
    for gid in ids:
        tdir = gdir / str(gid)
        shp = list(tdir.glob("**/*.shp")) if tdir.exists() else []
        if not shp:
            art = next((a for lo, hi, a in parts if lo <= gid <= hi), None)
            if art is None:
                continue
            fl, page = [], 1
            while True:
                chunk = req.get(f"https://api.figshare.com/v2/articles/{art}/files",
                                params={"page_size": 1000, "page": page}, headers=UA,
                                timeout=60).json()
                fl += chunk
                page += 1
                if len(chunk) < 1000:
                    break
            hit = [f for f in fl if f["name"].startswith(f"{gid}_")]
            if not hit:
                continue
            r = req.get(hit[0]["download_url"], headers=UA, timeout=1800, stream=True)
            r.raise_for_status()
            tdir.mkdir(exist_ok=True)
            zp = tdir / hit[0]["name"]
            with open(zp, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
            zipfile.ZipFile(zp).extractall(tdir)
            zp.unlink(missing_ok=True)
            shp = list(tdir.glob("**/*.shp"))
        out += [str(s) for s in shp]
    print(f"[heights] {city.id}: 3D-GloBFP tiles {ids}")
    return out


def fetch_ob25d(city, data_dir, year=OB25D_YEAR, res=2.0):
    """Open Buildings 2.5D Temporal `building_height` for the boundary bbox,
    read window-wise over HTTPS from the 0.5 m tiles and stored as a 2 m
    block-max GeoTIFF. None when the UTM zone/year has no tile here."""
    import geopandas as gpd
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.windows import Window

    from .areas import read_boundary
    req = _requests()
    epsg = int(str(city.crs).split(":")[-1])
    poly = read_boundary(city.file(city.boundary.get("file", "boundary.gpkg"), data_dir)) \
        .to_crs(4326).iloc[0]
    names, token = [], None
    while True:
        params = {"prefix": "v1/manifests/", "maxResults": "1000"}
        if token:
            params["pageToken"] = token
        j = req.get(OB25D_API, params=params, headers=UA, timeout=60).json()
        names += [i["name"] for i in j.get("items", [])]
        token = j.get("nextPageToken")
        if not token:
            break
    mans = [n for n in names if f"EPSG_{epsg}_{year}" in n]
    if not mans:
        print(f"[heights] Open Buildings 2.5D: no {year} manifest for EPSG:{epsg}")
        return None
    x0, y0, x1, y1 = gpd.GeoSeries([poly], crs=4326).to_crs(epsg).total_bounds
    x0, y0 = np.floor(x0 / res) * res - res, np.floor(y0 / res) * res - res
    x1, y1 = np.ceil(x1 / res) * res + res, np.ceil(y1 / res) * res + res
    W, H = int((x1 - x0) / res), int((y1 - y0) / res)
    mosaic = np.zeros((H, W), dtype=np.float32)
    n_tiles = 0
    for m in mans:
        j = req.get(OB25D + m, headers=UA, timeout=60).json()
        prefix = j["uriPrefix"].split("v1/geotiffs/")[1]
        band = [b.get("id") for b in j["bands"]].index("building_height") + 1
        for src in j["tilesets"][0]["sources"]:
            at, dims = src["affineTransform"], src["dimensions"]
            tx0, ty1, sx = at["translateX"], at["translateY"], at["scaleX"]
            tx1 = tx0 + dims["width"] * sx
            ty0 = ty1 + dims["height"] * at["scaleY"]
            if tx1 <= x0 or tx0 >= x1 or ty1 <= y0 or ty0 >= y1:
                continue
            ix0, ix1 = max(x0, tx0), min(x1, tx1)
            iy0, iy1 = max(y0, ty0), min(y1, ty1)
            col_off = int(round((ix0 - tx0) / sx))
            row_off = int(round((ty1 - iy1) / sx))
            width = int((ix1 - ix0) / sx) // 4 * 4
            height = int((iy1 - iy0) / sx) // 4 * 4
            if width < 4 or height < 4:
                continue
            uri = OB25D + "v1/geotiffs/" + prefix + src["uris"][0]
            r0 = int(round((y1 - (ty1 - row_off * sx)) / res))
            c0 = int(round((tx0 + col_off * sx - x0) / res))
            with rasterio.open(uri) as ds:
                step = 4096
                for r_off in range(0, height, step):
                    hh = min(step, height - r_off)
                    a = ds.read(band, window=Window(col_off, row_off + r_off, width, hh))
                    a = a.reshape(hh // 4, 4, width // 4, 4).max(axis=(1, 3))
                    rr0 = r0 + r_off // 4
                    h, w = a.shape
                    r1, c1 = min(H, rr0 + h), min(W, c0 + w)
                    if r1 <= rr0 or c1 <= c0:
                        continue
                    mosaic[rr0:r1, c0:c1] = np.maximum(mosaic[rr0:r1, c0:c1],
                                                       a[:r1 - rr0, :c1 - c0])
            n_tiles += 1
    if not n_tiles:
        return None
    out = city_dir(city, data_dir) / (city.heights.get("candidates", {}) or {}).get(
        "ob25d", "ob25d_height.tif")
    with rasterio.open(out, "w", driver="GTiff", width=W, height=H, count=1, dtype="float32",
                       crs=f"EPSG:{epsg}", transform=from_origin(x0, y1, res, res),
                       compress="deflate", tiled=True) as dst:
        dst.write(mosaic, 1)
    print(f"[heights] Open Buildings 2.5D: {out.name} {W}x{H} @ {res} m ({n_tiles} tiles)")
    return out


def fetch_heights(city, data_dir):
    """All height sources the city's policy may use; records them in
    <data_dir>/<id>/heights_available.json."""
    pol = city.heights.get("policy", "none")
    rec = {}
    if pol == "file" and city.heights.get("fetch") == "nyc_open_data":
        rec["file"] = str(fetch_nyc_heights(city, data_dir))
    if pol in ("globfp", "auto"):
        rec["globfp"] = fetch_globfp(city, data_dir)
    if pol in ("ob25d", "auto"):
        p = fetch_ob25d(city, data_dir)
        rec["ob25d"] = str(p) if p else None
    (city_dir(city, data_dir) / "heights_available.json").write_text(json.dumps(rec, indent=2))
    return rec


STEPS = {"boundary": fetch_boundary, "buildings": fetch_overture, "heights": fetch_heights,
         "streets": fetch_overture_streets}


def fetch(city, data_dir, steps=("boundary", "buildings", "heights", "streets")):
    for s in steps:
        if s == "buildings" and city.buildings.get("source") != "overture":
            print(f"[fetch] {city.id}: buildings source '{city.buildings.get('source')}' "
                  "is read at run time - nothing to fetch")
            continue
        if s == "streets" and city.streets.get("fetch") != "overture_segments":
            print(f"[fetch] {city.id}: streets are read from OSM at run time - nothing to fetch")
            continue
        t0 = time.time()
        STEPS[s](city, data_dir)
        print(f"[fetch] {city.id} {s} done in {time.time() - t0:.0f}s")
