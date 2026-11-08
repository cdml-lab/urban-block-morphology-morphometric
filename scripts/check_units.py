"""Check the sampling units and the 46 descriptors of this package against
the study pipeline's (private) caches (docs/reproduction.md, part B).

    python scripts/check_units.py --study-root <root> --set thirteen_cities [--cities RIO NBO]
    python scripts/check_units.py --study-root <root> --set three_cities --chars

Per city, from the cached inputs of the set's cache folder:

  units        (thirteen-city set) blocks from the cached enclosures and buildings
               (core make_blocks) -> built-envelope trimming -> mega-block
               tiers 2-3 on the cached enclosed tessellation (this package),
               compared with the cached blocks (count, kinds, ids, area) and
               the buildings' block ids; and, where the study applied tier 1,
               the share of buildings in mega-blocks under the default
               cutting classes, recomputed from the cached street network;
  descriptors  core missing-data treatment + core block descriptors (46) +
               partition-unit neutralisation (this package) on the cached
               building characters, compared with the cached descriptors;
  --chars      also recompute the building characters (core, momepy) from
               the cached buildings, tessellation, streets and blocks (slow).

Exit code 0 = every check within tolerance (descriptors: 1e-6 of each
column's range, identical missing-value pattern).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blockmorph.blocks import enclosures, make_blocks                    # noqa: E402
from blockmorph.descriptors import block_descriptors, building_characters  # noqa: E402
from blockmorph.missing import impute_heights                             # noqa: E402

from blockmorph_morphometric import reproduce as R                             # noqa: E402
from blockmorph_morphometric.config import load_set                            # noqa: E402
from blockmorph_morphometric.descriptors import neutralise_partition_units     # noqa: E402
from blockmorph_morphometric.refine import mega_share, split_mega_blocks, trim_open_blocks  # noqa: E402

TOL = 1e-6


def compare_features(mine: pd.DataFrame, ref: pd.DataFrame):
    ref = ref[[c for c in ref.columns if not c.startswith("rcnn_")]]
    mine = mine.reindex(index=ref.index, columns=ref.columns)
    rng = (ref.max() - ref.min()).replace(0, 1)
    d = ((mine - ref).abs() / rng).max()
    nan = int((mine.isna() != ref.isna()).sum().sum())
    return float(d.max()), str(d.idxmax()), nan


def check_city(root, set_cfg, cid, code, sets, chars_too=False):
    cache = R.city_cache(root, code, set_cfg.name, sets)
    city = set_cfg.city_configs[cid]
    p = city.params()
    out = {"set": set_cfg.name, "city": cid}
    t0 = time.time()
    blocks_ref = gpd.read_parquet(cache / "blocks_universe.parquet")
    b_ref = gpd.read_parquet(cache / "buildings.parquet")
    streets = gpd.read_parquet(cache / "streets.parquet")
    feats_ref = pd.read_parquet(cache / "block_features.parquet")
    if set_cfg.refine is not None:
        rp = set_cfg.refine
        enc = gpd.read_parquet(cache / "enclosures.parquet")
        tess = gpd.read_parquet(cache / "tessellation.parquet")
        b0 = b_ref.drop(columns=[c for c in ("eID", "block_id") if c in b_ref.columns])
        blocks, ctx, b = make_blocks(b0, enc, p)
        rule = json.loads((cache / "block_rule.json").read_text())
        if not rule.get("tier1_applied"):
            # the cached enclosures are those of the default cutting rule
            share, _ = mega_share(blocks, b, rp)
            out["tier1_share_default"] = round(share, 3)
            out["tier1_share_ref"] = rule.get("mega_share_default")
            out["tier1_trigger"] = bool(share > rp.share_all_roads and not city.cut_all_roads)
            out["tier1_ref"] = False
        blocks, ctx, n_trim = trim_open_blocks(blocks, ctx, b, rp)
        blocks, b, stats = split_mega_blocks(blocks, b, tess, rp)
        kinds = blocks["block_kind"].value_counts().to_dict()
        same_ids = bool(len(blocks) == len(blocks_ref)
                        and (blocks["eID"].values == blocks_ref["eID"].values).all()
                        and (blocks["block_kind"].values == blocks_ref["block_kind"].values).all())
        a1, a0 = blocks.geometry.area.values, blocks_ref.geometry.area.values
        area_diff = float(np.max(np.abs(a1 - a0) / np.maximum(a0, 1))) if same_ids else np.nan
        bid_same = bool(b["block_id"].fillna(-1).astype(int).equals(
            b_ref["block_id"].fillna(-1).astype(int)))
        out.update({"blocks": len(blocks), "blocks_ref": len(blocks_ref),
                    "kinds_equal": kinds == rule["block_kind"], "trimmed": n_trim,
                    "trimmed_ref": rule.get("trimmed_blocks"),
                    "unit_order_equal": same_ids, "unit_area_maxrel": area_diff,
                    "building_block_ids_equal": bid_same})
        if rule.get("tier1_applied") and (cache / "streets_all.parquet").exists():
            from blockmorph_morphometric.areas import read_boundary
            from shapely.geometry import box
            bpath = Path(root) / "data" / f"{code.lower()}_boundary.json"
            bnd = read_boundary(bpath).to_crs(city.crs)
            clip = city.study_area.get("clip_bbox")
            area = gpd.GeoSeries([bnd.iloc[0].intersection(box(*clip)) if clip else bnd.iloc[0]],
                                 crs=city.crs)
            s_all = gpd.read_parquet(cache / "streets_all.parquet")
            s_def = s_all[s_all["highway"].isin(p.cutting_highways)]
            enc_d = enclosures(s_def, area)
            bl_d, _, bd = make_blocks(b0, enc_d, p)
            share, _ = mega_share(bl_d, bd, rp)
            out["tier1_share_default"] = round(share, 3)
            out["tier1_share_ref"] = rule.get("mega_share_default")
            out["tier1_trigger"] = bool(share > rp.share_all_roads)
            out["tier1_ref"] = True
        blocks_use = blocks_ref
    else:
        blocks_use = blocks_ref
        out.update({"blocks": len(blocks_ref), "blocks_ref": len(feats_ref)})
    chars = gpd.read_parquet(cache / "building_chars.parquet")
    if chars_too:
        tess = gpd.read_parquet(cache / "tessellation.parquet")
        mine_c = building_characters(b_ref, tess, streets, blocks_use, p)
        cols = [c for c in mine_c.columns if c in chars.columns
                and pd.api.types.is_numeric_dtype(chars[c]) and c not in ("eID", "block_id")]
        rng = (chars[cols].max() - chars[cols].min()).replace(0, 1)
        dc = ((mine_c[cols] - chars[cols]).abs() / rng).max()
        out["chars_maxrel"] = float(dc.max())
        out["chars_worst"] = str(dc.idxmax())
    ch, _ = impute_heights(chars, p)
    f = block_descriptors(ch, blocks_use, streets, None, p)
    f, n_part = neutralise_partition_units(f, blocks_use)
    d, worst, nan = compare_features(f, feats_ref)
    out.update({"partition_units": n_part, "descr_maxrel": d, "descr_worst": worst,
                "descr_nan_mismatch": nan, "seconds": round(time.time() - t0)})
    ok = d <= TOL and nan == 0 and out["blocks"] == out["blocks_ref"]
    if set_cfg.refine is not None:
        ok &= out["kinds_equal"] and out["unit_order_equal"] and out["building_block_ids_equal"] \
            and out["unit_area_maxrel"] <= 1e-9
        if "tier1_trigger" in out:
            # the tier-1 DECISION must agree; the recorded share is informative
            # only (see docs/reproduction.md)
            ok &= out["tier1_trigger"] == out["tier1_ref"]
    if chars_too:
        ok &= out["chars_maxrel"] <= TOL
    out["pass"] = bool(ok)
    print(json.dumps(out, default=str), flush=True)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--study-root", required=True,
                    help="root of the study pipeline (config.py, cache/, data/)")
    ap.add_argument("--set", required=True)
    ap.add_argument("--cities", nargs="*")
    ap.add_argument("--chars", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    s = load_set(a.set)
    sets = R.read_sets(a.study_root)
    codes = dict(zip(s.cities, R.check_order(s, sets)))
    rows = [check_city(a.study_root, s, c, codes[c], sets, a.chars)
            for c in (a.cities or s.cities)]
    t = pd.DataFrame(rows)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        t.to_csv(a.out, index=False)
    ok = bool(t["pass"].all())
    print("UNITS_OK" if ok else "UNITS_DIFFER")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
