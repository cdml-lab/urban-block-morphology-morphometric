"""Thirteen-city set: refinement of street-enclosure blocks into comparable
sampling units (study procedure; the three-city set keeps plain blocks).

A block is a sampling unit of fabric: one observation, one descriptor
vector. Where the mapped street network leaves thousands of buildings in
one enclosure (informal settlements, untagged lanes) the unit stops being
comparable. Three measured tiers apply, after the built-envelope trimming:

0. trimming - a block whose built envelope (buildings buffered by 30 m,
   holes filled) covers less than half of it is cut down to that envelope;
   the remainder joins the open/context enclosures (`block_trim` = share
   kept).
1. every mapped way cuts blocks when the default cutting classes leave
   more than 20 % of the buildings in mega-blocks (> 8 ha and > 150
   buildings);
2. a remaining mega-block is split along its own alleys: buildings
   buffered by d and unioned, widest corridors first (d = 3, 2, 1.5, 1 m;
   the first d that leaves no unit above 150 buildings); patches under 3
   buildings merge into the nearest larger patch;
3. fabric without readable gaps is partitioned into contiguous units of
   at most ~150 buildings (k-means on building centroids, seed 42).

Exempt from splitting: open land with scattered structures (GSI < 0.15)
and big-shed estates (median footprint >= 300 m2). Sub-block polygons are
unions of the enclosed-tessellation cells of their buildings, clipped to
the parent block. Every block carries `block_kind` = street | patch |
partition.

Order in the study pipeline: blocks -> tier 1 -> tessellation -> trimming
-> tiers 2 and 3. Ported from the study pipeline's blocks.py (same numbers, same
order of operations).
"""
from __future__ import annotations

from dataclasses import dataclass, fields

import geopandas as gpd
import numpy as np
import pandas as pd
from blockmorph.inputs import log


@dataclass
class RefineParams:
    mega_block_ha: float = 8.0           # mega-block = larger than this AND ...
    mega_block_bldg: int = 150           # ... holding more buildings than this
    share_all_roads: float = 0.20        # tier-1 trigger (share of buildings in mega-blocks)
    split_ds: tuple = (3.0, 2.0, 1.5, 1.0)   # tier-2 buffer radii, widest first
    target_bldg: int = 150               # no unit above this after tiers 2-3
    min_patch_bldg: int = 3              # smaller patches merge into a neighbour
    trim_buffer_m: float = 30.0          # built-envelope buffer
    trim_max_envelope: float = 0.5       # trim when the envelope covers less than this
    split_min_gsi: float = 0.15          # exempt: open land with scattered structures
    split_max_footprint_m2: float = 300.0    # exempt: big-shed estates (median footprint)
    partition_seed: int = 42             # tier-3 k-means seed (study: RANDOM_STATE)

    @classmethod
    def from_dict(cls, d: dict | None) -> "RefineParams":
        d = dict(d or {})
        if "split_ds" in d:
            d["split_ds"] = tuple(float(x) for x in d["split_ds"])
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


def mega_share(blocks: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame,
               rp: RefineParams | None = None):
    """Share of the city's (in-block) buildings sitting in mega-blocks, and
    the number of mega-blocks."""
    rp = rp or RefineParams()
    n = buildings.dropna(subset=["block_id"]).groupby("block_id").size()
    b = blocks.set_index("block_id")
    cnt = n.reindex(b.index).fillna(0)
    mega = (b.geometry.area / 1e4 > rp.mega_block_ha) & (cnt > rp.mega_block_bldg)
    return float(cnt[mega].sum() / max(cnt.sum(), 1)), int(mega.sum())


def _patch_ids(bld: gpd.GeoDataFrame, d: float, rp: RefineParams) -> pd.Series:
    """Built patches: buildings buffered by d and unioned; every building
    takes the id of the patch it falls in; patches under min_patch_bldg
    buildings merge into the nearest larger one."""
    import shapely
    u = shapely.union_all(bld.geometry.buffer(d, join_style="mitre").values)
    geoms = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
    P = gpd.GeoDataFrame({"pid": range(len(geoms))}, geometry=geoms, crs=bld.crs)
    pts = gpd.GeoDataFrame(geometry=bld.geometry.representative_point(), index=bld.index)
    j = gpd.sjoin(pts, P, how="left", predicate="within")
    pid = j[~j.index.duplicated(keep="first")]["pid"].reindex(bld.index)
    pid = pid.fillna(-1).astype(int)
    cnt = pid.value_counts()
    small = cnt[cnt < rp.min_patch_bldg].index
    big = P[~P["pid"].isin(small)]
    if len(small) and len(big):
        for sid in small:
            g = P.loc[P["pid"] == sid, "geometry"].iloc[0] if sid >= 0 else None
            if g is None:
                continue
            near = big["pid"].iloc[int(np.argmin(big.geometry.distance(g).values))]
            pid[pid == sid] = near
    return pid


def _partition_ids(bld: gpd.GeoDataFrame, rp: RefineParams) -> np.ndarray:
    """Tier 3: contiguous chunks of at most ~target_bldg buildings by k-means
    on the building centroids, re-split until no chunk exceeds the target
    (at most 8 rounds)."""
    from sklearn.cluster import KMeans
    target = rp.target_bldg
    xy = np.c_[bld.geometry.centroid.x.values, bld.geometry.centroid.y.values]
    labels = np.zeros(len(bld), dtype=int)
    for _ in range(8):
        counts = np.bincount(labels)
        big = np.flatnonzero(counts > target)
        if not len(big):
            break
        nxt = labels.max() + 1
        for c in big:
            sel = np.flatnonzero(labels == c)
            k = int(np.ceil(len(sel) / target))
            if k <= 1:
                continue
            sub = KMeans(k, n_init=4, random_state=rp.partition_seed).fit_predict(xy[sel])
            labels[sel] = np.where(sub == 0, c, nxt + sub - 1)
            nxt += k - 1
    return labels


def trim_open_blocks(blocks: gpd.GeoDataFrame, context: gpd.GeoDataFrame,
                     buildings: gpd.GeoDataFrame, rp: RefineParams | None = None):
    """Built-envelope trimming. Returns (blocks, context, number trimmed);
    adds `block_trim` (share of the original area kept, 1.0 = untouched)."""
    import shapely
    from shapely.geometry import MultiPolygon, Polygon
    rp = rp or RefineParams()
    blocks = blocks.copy()
    context = context.copy()
    B = rp.trim_buffer_m
    grp = buildings.dropna(subset=["block_id"]).groupby(
        buildings["block_id"].dropna().astype(int))
    keep_share = np.ones(len(blocks))
    new_geoms = list(blocks.geometry.values)
    leftovers = []
    bid_pos = {int(b): i for i, b in enumerate(blocks["block_id"])}
    for bid, g in grp:
        i = bid_pos.get(int(bid))
        if i is None:
            continue
        poly = new_geoms[i]
        env = shapely.union_all(g.geometry.buffer(B, join_style="mitre").values)
        parts = list(env.geoms) if env.geom_type == "MultiPolygon" else [env]
        env = MultiPolygon([Polygon(p_.exterior) for p_ in parts]) \
            if len(parts) > 1 else Polygon(parts[0].exterior)
        clip = poly.intersection(env).buffer(0)
        share = clip.area / poly.area if poly.area > 0 else 1.0
        if share < rp.trim_max_envelope and clip.area > 0:
            keep_share[i] = share
            new_geoms[i] = clip
            rest = poly.difference(clip).buffer(0)
            if not rest.is_empty:
                leftovers.append({"eID": int(blocks["eID"].iloc[i]), "geometry": rest})
    blocks["geometry"] = gpd.GeoSeries(new_geoms, crs=blocks.crs).values
    blocks["block_trim"] = keep_share
    blocks["area_m2"] = blocks.geometry.area
    blocks["gsi"] = blocks["footprint_m2"] / blocks["area_m2"]
    if leftovers:
        lo = gpd.GeoDataFrame(leftovers, geometry="geometry", crs=blocks.crs)
        lo["footprint_m2"] = 0.0
        lo["area_m2"] = lo.geometry.area
        lo["gsi"] = 0.0
        context = pd.concat([context, lo[[c for c in context.columns if c in lo.columns]]],
                            ignore_index=True)
        context = gpd.GeoDataFrame(context, geometry="geometry", crs=blocks.crs)
    n_trim = int((keep_share < 1).sum())
    log(f"[refine] built-envelope trimming: {n_trim} blocks reduced"
        + (f" (median kept share {np.median(keep_share[keep_share < 1]):.0%})" if n_trim else ""))
    return blocks, context, n_trim


def split_mega_blocks(blocks: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame,
                      tess: gpd.GeoDataFrame, rp: RefineParams | None = None):
    """Tiers 2 + 3 on every non-exempt mega-block. Returns (blocks,
    buildings, stats) with block ids renumbered (untouched blocks keep
    their order, sub-blocks are appended) and `block_kind`."""
    rp = rp or RefineParams()
    blocks = blocks.copy()
    buildings = buildings.copy()
    if "block_kind" not in blocks.columns:
        blocks["block_kind"] = "street"
    n_by = buildings.dropna(subset=["block_id"]).groupby("block_id").size()
    bi = blocks.set_index("block_id")
    area_ha = bi.geometry.area / 1e4
    fp_med = buildings.dropna(subset=["block_id"]).groupby("block_id")["footprint_m2"].median()
    gsi = bi["footprint_m2"] / bi.geometry.area
    cand = [int(b) for b in blocks["block_id"]
            if area_ha[b] > rp.mega_block_ha and n_by.get(b, 0) > rp.mega_block_bldg]
    exempt_open = [b for b in cand if gsi[b] < rp.split_min_gsi]
    exempt_big = [b for b in cand if b not in exempt_open
                  and fp_med.get(b, 0) >= rp.split_max_footprint_m2]
    mega_ids = [b for b in cand if b not in exempt_open and b not in exempt_big]
    stats = {"mega_blocks": len(mega_ids), "exempt_open": len(exempt_open),
             "exempt_bigbox": len(exempt_big), "patch_units": 0,
             "partition_units": 0, "d_used": {}}
    if exempt_open or exempt_big:
        log(f"[refine] mega-units left whole: {len(exempt_open)} open land "
            f"(GSI < {rp.split_min_gsi}), {len(exempt_big)} big-shed "
            f"(median footprint >= {rp.split_max_footprint_m2:.0f} m2)")
    if not mega_ids:
        return blocks, buildings, stats
    keep = blocks[~blocks["block_id"].isin(mega_ids)]
    new_rows = []
    for bid in mega_ids:
        bb = buildings[buildings["block_id"] == bid]
        cells = tess.loc[tess.index.intersection(bb.index)]
        chosen_d, pid = None, None
        for d in rp.split_ds:                       # tier 2: widest corridors first
            pid = _patch_ids(bb, d, rp)
            if pid.value_counts().max() <= rp.target_bldg:
                chosen_d = d
                break
        if chosen_d is None:
            chosen_d = rp.split_ds[-1]
        stats["d_used"][str(chosen_d)] = stats["d_used"].get(str(chosen_d), 0) + 1
        kind = pd.Series("patch", index=bb.index)
        unit = pid.astype(str)
        for p_, cnt in pid.value_counts().items():  # tier 3
            if cnt > rp.target_bldg:
                sel = pid.index[pid == p_]
                part = _partition_ids(bb.loc[sel], rp)
                unit.loc[sel] = [f"{p_}.{q}" for q in part]
                kind.loc[sel] = "partition"
        c = cells.assign(unit=unit.reindex(cells.index))
        c = c.dropna(subset=["unit"])
        sub = c.dissolve(by="unit")
        parent_geom = blocks.loc[blocks["block_id"] == bid, "geometry"].iloc[0]
        for u_, row in sub.iterrows():
            members = unit.index[unit == u_]
            k_ = kind.loc[members].iloc[0]
            geom = row.geometry.buffer(0).intersection(parent_geom).buffer(0)
            if geom.is_empty:
                geom = row.geometry.buffer(0)
            new_rows.append({"eID": int(blocks.loc[blocks["block_id"] == bid, "eID"].iloc[0]),
                             "geometry": geom, "block_kind": k_,
                             "__members": list(members)})
            stats["patch_units" if k_ == "patch" else "partition_units"] += 1
    new = gpd.GeoDataFrame(new_rows, geometry="geometry", crs=blocks.crs)
    new["footprint_m2"] = [buildings.loc[m, "footprint_m2"].sum() for m in new["__members"]]
    new["area_m2"] = new.geometry.area
    new["gsi"] = new["footprint_m2"] / new["area_m2"]
    keep = keep.reset_index(drop=True)
    old_to_new = {int(b): i for i, b in enumerate(keep["block_id"])}
    buildings["block_id"] = buildings["block_id"].map(old_to_new)
    base = len(keep)
    for i, m in enumerate(new["__members"]):
        buildings.loc[m, "block_id"] = base + i
    new["block_id"] = np.arange(base, base + len(new))
    keep["block_id"] = np.arange(base)
    new["block_trim"] = 1.0
    if "block_trim" not in keep.columns:
        keep["block_trim"] = 1.0
    cols = ["eID", "footprint_m2", "area_m2", "gsi", "block_id", "block_kind",
            "block_trim", "geometry"]
    out = pd.concat([keep[cols], new[cols]], ignore_index=True)
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=blocks.crs)
    log(f"[refine] mega-block refinement: {len(mega_ids)} mega-blocks -> "
        f"{stats['patch_units']} patch + {stats['partition_units']} partition units "
        f"(d used: {stats['d_used']}); {len(out)} blocks now")
    return out, buildings, stats
