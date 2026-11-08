"""Command line.

  blockmorph-morphometric run   <set> [--cities ...] [--data DIR] [--out DIR] [--no-pooled]
  blockmorph-morphometric fit   <set> <descriptors.csv> --out DIR [--no-pooled]
  blockmorph-morphometric fetch boundary|buildings|heights|streets --set <set> --city ID [--data DIR]
  blockmorph-morphometric info  <set>

<set> is three_cities, thirteen_cities or a path to a set YAML file.
"""
from __future__ import annotations

import argparse
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="blockmorph-morphometric")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="full Track A run of a set from its inputs")
    r.add_argument("set")
    r.add_argument("--cities", nargs="*")
    r.add_argument("--data", default=None, help="input folder (<data>/<city id>/...)")
    r.add_argument("--out", default=None)
    r.add_argument("--no-pooled", action="store_true")
    r.add_argument("--no-stability", action="store_true")
    f = sub.add_parser("fit", help="Track A models from a descriptor table")
    f.add_argument("set")
    f.add_argument("descriptors", help="CSV with block_key, area and the 46 descriptors")
    f.add_argument("--out", required=True)
    f.add_argument("--no-pooled", action="store_true")
    g = sub.add_parser("fetch", help="download the open inputs of a city")
    g.add_argument("step", choices=["boundary", "buildings", "heights", "streets"])
    g.add_argument("--set", required=True)
    g.add_argument("--city", required=True)
    g.add_argument("--data", default=None)
    i = sub.add_parser("info", help="show a set configuration")
    i.add_argument("set")
    a = ap.parse_args(argv)

    from . import check_core
    from .config import load_set
    check_core()
    if a.cmd == "run":
        from .pipeline import run
        s = load_set(a.set, data_dir=a.data, output_dir=a.out)
        print("output:", run(s, a.cities, run_stability=not a.no_stability,
                             pooled=not a.no_pooled))
    elif a.cmd == "fit":
        import pandas as pd

        from .pipeline import fit_descriptors
        s = load_set(a.set)
        t = pd.read_csv(a.descriptors, index_col="block_key")
        fit_descriptors(s, t, a.out, pooled=not a.no_pooled)
        print("output:", a.out)
    elif a.cmd == "fetch":
        from .acquire import fetch
        s = load_set(a.set, data_dir=a.data)
        fetch(s.city_configs[a.city], s.data_dir, [a.step])
    else:
        s = load_set(a.set)
        print(f"{s.name}: {s.title}")
        print(f"  cities (pooling order): {', '.join(s.cities)}")
        print(f"  sampling units: {'refined (trim + mega-block tiers)' if s.refine else 'street-enclosure blocks'}")
        m = s.model
        print(f"  whitened PCA {m.pca_components}; K city {min(m.k_range_city)}-{max(m.k_range_city)}, "
              f"pooled {min(m.k_range_pooled)}-{max(m.k_range_pooled)}; min type size {m.min_type_size}")
        for c in s.cities:
            cc = s.city_configs[c]
            print(f"  {c:>4}  {cc.name}  [{cc.crs}; buildings {cc.buildings.get('source')}, "
                  f"heights {cc.heights.get('policy')}, min area {cc.min_building_area_m2:g} m2"
                  + (", all roads cut" if cc.cut_all_roads else "") + "]")


if __name__ == "__main__":
    sys.exit(main())
