"""Reproduce the study's adopted Track A partitions of the three-city and thirteen-city sets
from the study pipeline's cache tree and compare them with the published
labels (docs/reproduction.md).

    python scripts/check_reproduction.py --study-root <study pipeline root>
    python scripts/check_reproduction.py --study-root <root> --sets three_cities
    python scripts/check_reproduction.py --study-root <root> --wait 120 --out table.csv

Input per city: the 46 treated descriptors (`block_features.parquet`,
`rcnn_*` columns dropped if present) of the city's cache folder for the set.
Models: core preprocessing, whitened PCA (5), K-means K sweep and K rule;
K range 5-15 (city models, three-city pooled) and 5-25 (thirteen-city pooled).

Pass condition per model: identical K and ARI = 1.000 (the integer type ids
are compared too). A pooled reference older than its members' descriptor
files is reported as STALE (the published pooled model was not refitted on
the current descriptors) and fails.

Exit code 0 = every requested model reproduced exactly.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blockmorph_morphometric import __version__, check_core          # noqa: E402
from blockmorph_morphometric import reproduce as R                   # noqa: E402
from blockmorph_morphometric.config import load_set                  # noqa: E402
from blockmorph_morphometric.model import fit_track_a, pool          # noqa: E402


def _mtime(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def pooled_reference_fresh(root, aset, feature_paths) -> tuple[bool, str]:
    shared = Path(root) / "output" / R.study_set(aset) / "SHARED"
    geo, sweep = shared / "blocks_clustered.geojson", shared / "tables" / "k_sweep_morpho.csv"
    newest = max(p.stat().st_mtime for p in feature_paths)
    ok = geo.stat().st_mtime >= newest and sweep.stat().st_mtime >= newest \
        and geo.stat().st_mtime >= sweep.stat().st_mtime
    return ok, (f"labels {_mtime(geo)}, K sweep {_mtime(sweep)}, newest descriptors "
                f"{datetime.fromtimestamp(newest).strftime('%Y-%m-%d %H:%M')}")


def run_set(root, aset, skip_pooled=False, wait_min=0.0, poll_s=60):
    set_cfg = load_set(aset)
    sets = R.read_sets(root)
    codes = R.check_order(set_cfg, sets)
    print(f"\n=== {aset}: {' + '.join(set_cfg.cities)} (pooling order verified against "
          f"the study pipeline) ===", flush=True)
    frames, fpaths, rows = {}, [], []
    pc = set_cfg.model.params("city")
    for cid, code in zip(set_cfg.cities, codes):
        f, path = R.load_features(root, code, aset, sets)
        fpaths.append(path)
        n_rcnn = sum(str(c).startswith("rcnn_") for c in f.columns)
        frames[cid] = f
        t0 = time.time()
        fit = fit_track_a(f, pc)
        lab, ek, geo = R.expected_city(root, code, aset)
        exp = lab.set_index("block_id")["label_morpho"].reindex(f.index.astype(int)).values
        cmp = R.compare(exp, fit.labels)
        good = (fit.k == ek) and cmp["ari"] == 1.0 and cmp["identical_ids"] \
            and cmp["n_missing_reference"] == 0 and len(lab) == len(f)
        rows.append({"set": aset, "model": cid, "blocks": len(f), "descriptors": f.shape[1] - n_rcnn,
                     "k_range": f"{min(pc.k_range)}-{max(pc.k_range)}", "expected_k": ek,
                     "reproduced_k": fit.k, "status": fit.status["status"],
                     "ari": round(cmp["ari"], 6), "identical_ids": cmp["identical_ids"],
                     "reference": "fresh" if geo.stat().st_mtime >= path.stat().st_mtime else "STALE",
                     "pass": bool(good)})
        print(f"{aset:>9} {cid:>6}: n={len(f):5d}  K {fit.k:2d} vs {ek:2d}  "
              f"ARI {cmp['ari']:.4f}  ids identical {cmp['identical_ids']}  "
              f"({time.time() - t0:.0f}s)", flush=True)
    if not skip_pooled:
        waited = 0.0
        while True:
            fresh, info = pooled_reference_fresh(root, aset, fpaths)
            if fresh or waited >= wait_min:
                break
            print(f"[{aset} pooled] reference not yet refreshed ({info}); "
                  f"waiting {poll_s} s", flush=True)
            time.sleep(poll_s)
            waited += poll_s / 60
        pp = set_cfg.model.params("pooled")
        F, area_of = pool(frames, set_cfg.cities)
        t0 = time.time()
        fit = fit_track_a(F, pp)
        lab, ek, geo, _ = R.expected_pooled(root, aset)
        code_of = dict(zip(set_cfg.cities, codes))
        key = [f"{code_of[a]}-{int(str(k).split('-', 1)[1])}" for a, k in zip(area_of, F.index)]
        ref = pd.Series(lab["label_morpho"].values,
                        index=lab["city"].astype(str) + "-" + lab["block_id"].astype(int).astype(str))
        exp = ref.reindex(key).values
        # the published pooled rows are in the same order as the pooled matrix
        same_order = bool(len(lab) == len(F) and (ref.index.values == np.array(key)).all())
        cmp = R.compare(exp, fit.labels)
        dk = R.decision_k(root, aset)
        good = (fit.k == ek) and (dk is None or dk == ek) and cmp["ari"] == 1.0 \
            and cmp["identical_ids"] and cmp["n_missing_reference"] == 0 and fresh
        rows.append({"set": aset, "model": "pooled", "blocks": len(F), "descriptors": F.shape[1],
                     "k_range": f"{min(pp.k_range)}-{max(pp.k_range)}", "expected_k": ek,
                     "reproduced_k": fit.k, "status": fit.status["status"],
                     "ari": round(cmp["ari"], 6), "identical_ids": cmp["identical_ids"],
                     "reference": "fresh" if fresh else "STALE", "pass": bool(good)})
        print(f"{aset:>9} pooled: n={len(F):5d}  K {fit.k:2d} vs {ek:2d} (decision record "
              f"{dk})  ARI {cmp['ari']:.4f}  ids identical {cmp['identical_ids']}  "
              f"row order as published {same_order}  reference {info}  "
              f"({time.time() - t0:.0f}s)", flush=True)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--study-root", required=True, help="root of the study pipeline "
                    "(holds config.py, cache/ and output/)")
    ap.add_argument("--sets", nargs="*", default=["three_cities", "thirteen_cities"])
    ap.add_argument("--skip-pooled", action="store_true")
    ap.add_argument("--wait", type=float, default=0.0,
                    help="minutes to wait for a pooled reference that is older than its "
                         "members' descriptors (polls every 60 s)")
    ap.add_argument("--out", default=None, help="write the table (.csv and .md)")
    a = ap.parse_args(argv)
    core = check_core()
    import sklearn
    print(f"urban-block-morphology-morphometric {__version__}, core {core}, numpy {np.__version__}, "
          f"pandas {pd.__version__}, scikit-learn {sklearn.__version__}, "
          f"Python {sys.version.split()[0]}")
    rows = []
    for s in a.sets:
        rows += run_set(a.study_root, s, a.skip_pooled, a.wait)
    t = pd.DataFrame(rows)
    print("\n" + t.to_string(index=False))
    ok = bool(t["pass"].all())
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        t.to_csv(out.with_suffix(".csv"), index=False)
        hdr = "| " + " | ".join(t.columns) + " |\n|" + "---|" * len(t.columns) + "\n"
        body = "".join("| " + " | ".join(str(v) for v in r) + " |\n" for r in t.values)
        out.with_suffix(".md").write_text(hdr + body, encoding="utf-8")
    print("REPRODUCTION_OK" if ok else "REPRODUCTION_DIFFERS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
