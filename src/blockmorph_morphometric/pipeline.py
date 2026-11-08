"""End-to-end Track A for a set: cities -> blocks (-> sampling units) ->
46 descriptors -> city models + pooled model -> outputs.

Every city is analysed in its OWN projected CRS (city YAML `crs`); only the
descriptor tables are pooled. Building blocks come from the core
(`blockmorph` 1.0.0): street preparation, enclosures, blocks, enclosed
tessellation, building characters, missing-data treatment, descriptors,
block statistics and model fitting/reporting (`pipeline.fit_model`).

Outputs (`output_dir`):
  areas/<id>/blocks.gpkg, buildings.gpkg, streets.gpkg, boundary.gpkg,
           units.json (sampling-unit record), heights.json (height decision)
  descriptors.csv     46 model descriptors per block_key (after neutralisation)
  block_stats.csv     physical statistics (heights before imputation)
  assignments.csv     block_key, area, block_kind, city type, pooled type
  models/<model>/     k_selection.csv, profiles.csv, representatives.json, report.json
  run.json            versions, set, cities, parameters, models
"""
from __future__ import annotations

import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
from blockmorph.blocks import enclosures, make_blocks, tessellate
from blockmorph.descriptors import MORPHO_COLUMNS, block_descriptors, building_characters
from blockmorph.inputs import log, prepare_streets
from blockmorph.missing import impute_heights

from . import __version__
from .areas import study_area
from .buildings import prepare_buildings
from .descriptors import as_model_input, neutralise_partition_units
from .refine import mega_share, split_mega_blocks, trim_open_blocks


def _streets(city, area, p, data_dir):
    """(all mapped ways, block-cutting ways) in the city CRS."""
    src = city.streets.get("source", "osm")
    src = "osm" if src == "osm" else city.file(city.streets["file"], data_dir)
    s_all = prepare_streets(src, area, city.crs, p, cut_all_roads=True)
    if city.cut_all_roads:
        return s_all, s_all
    return s_all, s_all[s_all["highway"].isin(p.cutting_highways)].reset_index(drop=True)


def prepare_city(city, set_cfg, data_dir=None):
    """Blocks / sampling units and the 46 descriptors of one city."""
    t0 = time.time()
    data_dir = data_dir or set_cfg.data_dir
    p = city.params()
    area, boundary = study_area(city, data_dir)
    b, hdec = prepare_buildings(city, area, boundary, data_dir)
    s_all, s = _streets(city, area, p, data_dir)
    enc = enclosures(s, area)
    blocks, open_space, b = make_blocks(b, enc, p)
    rule = {"cut_all_roads": city.cut_all_roads, "mega_share_default": None,
            "tier1_applied": False, "refinement": set_cfg.refine is not None}
    rp = set_cfg.refine
    if rp is not None:
        share, n_mega = mega_share(blocks, b, rp)
        rule["mega_share_default"] = round(share, 3)
        log(f"[units] {city.id}: mega-blocks under the default cutting set: {n_mega} "
            f"holding {share:.0%} of the buildings")
        if share > rp.share_all_roads and not city.cut_all_roads:
            s = s_all                                     # tier 1: every mapped way cuts
            enc = enclosures(s, area)
            blocks, open_space, b = make_blocks(b, enc, p)
            rule["tier1_applied"] = True
            share2, n2 = mega_share(blocks, b, rp)
            rule["mega_share_all_roads"] = round(share2, 3)
            log(f"[units] tier 1 (all roads cut): {n2} mega-blocks holding {share2:.0%}")
        tess = tessellate(b, enc)
        blocks, open_space, n_trim = trim_open_blocks(blocks, open_space, b, rp)
        rule["trimmed_blocks"] = n_trim
        blocks, b, stats = split_mega_blocks(blocks, b, tess, rp)
        rule.update(stats)
        rule["block_kind"] = blocks["block_kind"].value_counts().to_dict()
    else:
        tess = tessellate(b, enc)
    chars = building_characters(b, tess, s, blocks, p)
    chars["floors_measured"] = b["floors"].where(b["height_m"].notna())
    chars, imp = impute_heights(chars, p)
    raw = block_descriptors(chars, blocks, s, None, p)
    feats, n_part = neutralise_partition_units(raw, blocks)
    rule["partition_units_neutralised"] = n_part
    log(f"[city {city.id}] {len(blocks)} blocks, {feats.shape[1]} descriptors "
        f"({time.time() - t0:.0f}s)")
    return {"area": area, "boundary": boundary, "blocks": blocks, "buildings": chars,
            "streets": s, "features": feats, "features_raw": raw, "imputation": imp,
            "units": rule, "heights": hdec}


def _write_area(d: Path, cid, r):
    d.mkdir(parents=True, exist_ok=True)
    keep = [c for c in ("block_id", "block_kind", "block_trim", "geometry") if c in r["blocks"]]
    bl = r["blocks"][keep].copy()
    bl["block_key"] = [f"{cid}-{int(i)}" for i in bl["block_id"]]
    bl["area"] = cid
    bl.to_file(d / "blocks.gpkg")
    ch = r["buildings"]
    bb = ch[["block_id", "height_m", "height_measured_m", "height_imputed", "footprint_m2",
             "geometry"]].copy()
    bb["height_imputed"] = bb["height_imputed"].astype(int)
    bb.to_file(d / "buildings.gpkg")
    r["streets"].to_file(d / "streets.gpkg")
    r["area"].to_frame("geometry").to_file(d / "boundary.gpkg")
    (d / "units.json").write_text(json.dumps(r["units"], indent=1, default=str))
    (d / "heights.json").write_text(json.dumps(r["heights"], indent=1, default=str))


def run(set_cfg, cities=None, data_dir=None, output_dir=None, run_stability=True,
        pooled=True):
    """Full Track A run of a set (or of some of its cities)."""
    from blockmorph.pipeline import fit_model
    from blockmorph.profiles import block_stats
    cities = list(cities or set_cfg.cities)
    order = [c for c in set_cfg.cities if c in cities]           # keep the pooling order
    out = Path(output_dir or set_cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    log(f"[run] set {set_cfg.name}: {', '.join(order)}")
    res, F, S, area_of, kinds = {}, [], [], [], []
    for cid in order:
        city = set_cfg.city_configs[cid]
        r = prepare_city(city, set_cfg, data_dir)
        res[cid] = r
        keys = [f"{cid}-{int(i)}" for i in r["features"].index]
        f = as_model_input(r["features"]).copy()
        f.index = keys
        raw = r["features_raw"].copy()
        raw.index = keys
        ch = r["buildings"].copy()
        ch["block_key"] = [f"{cid}-{int(i)}" if pd.notna(i) else None for i in ch["block_id"]]
        st = block_stats(ch, raw, keys)               # physical values, not neutralised
        r["keys"], r["features_k"], r["stats"] = keys, f, st
        F.append(f); S.append(st); area_of += [cid] * len(keys)
        bk = r["blocks"].set_index("block_id")
        kinds += list(bk["block_kind"].reindex(r["features"].index).fillna("street")) \
            if "block_kind" in bk else ["street"] * len(keys)
        _write_area(out / "areas" / cid, cid, r)
    F = pd.concat(F); S = pd.concat(S)
    F.index.name = "block_key"
    F.insert(0, "area", area_of)
    F.to_csv(out / "descriptors.csv")
    F = F.drop(columns="area")
    S.to_csv(out / "block_stats.csv", index_label="block_key")
    asg = pd.DataFrame({"block_key": F.index, "area": area_of, "block_kind": kinds})
    reports = {}
    pc = set_cfg.model.params("city")
    loc_t, loc_n = [], []
    for cid in order:
        r = res[cid]
        lab, nm, rep = fit_model(cid, r["features_k"], [cid] * len(r["keys"]), r["stats"],
                                 pc, {}, out, run_stability)
        loc_t += list(lab); loc_n += [nm[int(x)] for x in lab]
        reports[cid] = rep
    asg["city_type"] = loc_t
    asg["city_name"] = loc_n
    if pooled and len(order) > 1:
        lab, nm, rep = fit_model("pooled", F, area_of, S, set_cfg.model.params("pooled"), {},
                                 out, run_stability)
        asg["pooled_type"] = lab
        asg["pooled_name"] = [nm[int(x)] for x in lab]
        reports["pooled"] = rep
    asg.to_csv(out / "assignments.csv", index=False)
    write_run_json(out, set_cfg, order, reports,
                   {c: {"imputation": res[c]["imputation"], "units": res[c]["units"],
                        "heights": res[c]["heights"]} for c in order})
    log(f"[run] done -> {out}")
    return out


def fit_descriptors(set_cfg, table: pd.DataFrame, output_dir, pooled=True):
    """Track A models from a descriptor table (block_key index, column
    `area`, the 46 descriptors). Writes k_selection.csv and report.json per
    model and assignments.csv (no geometry, no profiles)."""
    from blockmorph.naming import name_clusters, order_clusters

    from .model import fit_track_a
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    order = [c for c in set_cfg.cities if c in set(table["area"])]
    unknown = sorted(set(table["area"]) - set(order))
    if unknown:
        raise ValueError(f"areas not in set {set_cfg.name}: {unknown}")
    reports = {}
    T = pd.concat([table[table["area"] == c] for c in order])    # set order, rows kept in order
    X = as_model_input(T.drop(columns="area"))
    asg = pd.DataFrame({"block_key": T.index, "area": T["area"].values})
    models = [(c, X[T["area"].values == c], set_cfg.model.params("city")) for c in order]
    if pooled and len(order) > 1:
        models.append(("pooled", X, set_cfg.model.params("pooled")))
    for mid, x, p in models:
        fit = fit_track_a(x, p)
        d = out / "models" / mid
        d.mkdir(parents=True, exist_ok=True)
        fit.sweep.to_csv(d / "k_selection.csv", index=False)
        names = name_clusters(x, fit.labels)
        sel = fit.sweep[fit.sweep["selected"]].iloc[0]
        rep = {"model": mid, "blocks": int(len(x)), "descriptors": int(x.shape[1]),
               **fit.status, "k_range": [int(min(p.k_range)), int(max(p.k_range))],
               "pca_components": int(fit.z.shape[1]),
               "pca_variance": float(fit.pca.explained_variance_ratio_.sum()),
               "silhouette": float(sel["silhouette"]),
               "silhouette_gap": float(sel["silhouette_gap"]),
               "calinski": float(sel["calinski"]), "davies": float(sel["davies"]),
               "type_order": [int(t) for t in order_clusters(x, fit.labels)],
               "names": {str(k): v for k, v in names.items()}}
        (d / "report.json").write_text(json.dumps(rep, indent=1))
        col = "pooled_type" if mid == "pooled" else "city_type"
        if mid == "pooled":
            asg[col] = fit.labels
        else:
            asg.loc[asg["area"] == mid, col] = fit.labels
        reports[mid] = rep
        log(f"[model {mid}] K = {fit.k} ({fit.status['status']}), {len(x)} blocks")
    if "city_type" in asg:
        asg["city_type"] = asg["city_type"].astype(int)
    asg.to_csv(out / "assignments.csv", index=False)
    write_run_json(out, set_cfg, order, reports, {})
    return reports


def write_run_json(out, set_cfg, order, reports, per_city):
    import blockmorph
    info = {"package": "urban-block-morphology-morphometric", "version": __version__,
            "core": {"package": "urban-block-morphology", "version": blockmorph.__version__},
            "python": platform.python_version(), "set": set_cfg.name, "title": set_cfg.title,
            "cities": [{"id": c, "name": set_cfg.city_configs[c].name,
                        "crs": set_cfg.city_configs[c].crs} for c in order],
            "descriptor_set": "morphometric46",
            "descriptor_note": "MORPHOMETRIC-ONLY model (46 descriptors), no building-typology input",
            "descriptors": MORPHO_COLUMNS,
            "units_refinement": set_cfg.refine is not None,
            "model": {k: (list(v) if isinstance(v, tuple) else v)
                      for k, v in set_cfg.model.__dict__.items()},
            "per_city": per_city,
            "models": {k: {x: v.get(x) for x in ("selected_k", "status", "reason")}
                       for k, v in reports.items()}}
    try:
        import geopandas
        import momepy
        import sklearn
        info["libraries"] = {"momepy": momepy.__version__, "scikit-learn": sklearn.__version__,
                             "geopandas": geopandas.__version__, "numpy": np.__version__,
                             "pandas": pd.__version__}
    except Exception:                                             # noqa: BLE001
        pass
    (Path(out) / "run.json").write_text(json.dumps(info, indent=1, default=str))
