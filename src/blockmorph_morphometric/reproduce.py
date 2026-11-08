"""Reproduction of the study's adopted Track A partitions of the three-city and
thirteen-city sets from the study pipeline's (private) cache tree.

In that pipeline the two sets are called GLOBAL (three_cities) and UNIVERSAL
(thirteen_cities); its folders and decision record use those names, so every
function here accepts either name and reads the pipeline under its own.

The study pipeline (not distributed) keeps one cache folder per
city and set and one output tree per set:

  cache/<CODE>/block_features.parquet           a city's home set
  cache/<CODE>_<SET>/block_features.parquet     a city analysed in a later set
  output/<SET>/<CODE>/blocks_clustered.geojson  city model (block_id, label_morpho)
  output/<SET>/<CODE>/tables/k_sweep_morpho.csv city model K sweep (chosen_k)
  output/<SET>/SHARED/blocks_clustered.geojson  pooled model (city, block_id, label_morpho)
  output/<SET>/SHARED/tables/k_sweep_morpho.csv pooled K sweep

The cache folder of a city follows the study's rule (`city_cache`): a city
that belongs to several sets keeps its plain folder for the first set it
belongs to (in the order LOCAL, GLOBAL, UNIVERSAL) and a `<CODE>_<SET>`
folder for every later set. Set membership and order are read from the
pipeline's `config.py` by parsing it (never importing it, which would
create folders).

City A of this repository is the study's Israeli reference city: the one
member of a set that also belongs to the LOCAL set.
"""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd

from .config import STUDY_SET

REFERENCE_ALIAS = "A"
SET_ORDER = ("LOCAL", "GLOBAL", "UNIVERSAL")


def study_set(aset: str) -> str:
    """The pipeline's name of a set (three_cities -> GLOBAL, thirteen_cities -> UNIVERSAL)."""
    return STUDY_SET.get(str(aset).lower(), str(aset).upper())


def read_sets(study_root) -> dict:
    """{set name: tuple of city codes} from the pipeline's config.py."""
    src = (Path(study_root) / "config.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    tuples, sets_node = {}, None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if isinstance(node.value, ast.Tuple):
                try:
                    tuples[name] = tuple(ast.literal_eval(node.value))
                except ValueError:
                    pass
            if name == "SETS" and isinstance(node.value, ast.Dict):
                sets_node = node.value
    if sets_node is None:
        raise ValueError("config.py: no SETS dictionary")
    sets = {}
    for k, v in zip(sets_node.keys, sets_node.values):
        key = ast.literal_eval(k)
        sets[key] = tuples[v.id] if isinstance(v, ast.Name) else tuple(ast.literal_eval(v))
    return sets


def member_sets(code: str, sets: dict) -> list[str]:
    return [s for s in sets if code in sets[s]]


def city_cache(study_root, code: str, aset: str, sets: dict) -> Path:
    """The study's cache folder of city `code` analysed in set `aset`."""
    code = code.upper()
    aset = study_set(aset)
    member = member_sets(code, sets)
    root = Path(study_root) / "cache"
    if len(member) > 1 and aset in member and aset != member[0]:
        return root / f"{code}_{aset}"
    return root / code


def study_code(city_id: str, aset: str, sets: dict) -> str:
    """Pipeline code of a city id of this repository."""
    if city_id != REFERENCE_ALIAS:
        return city_id
    aset = study_set(aset)
    ref = [c for c in sets[aset] if c in sets.get("LOCAL", ())]
    if len(ref) != 1:
        raise ValueError(f"set {aset}: expected one LOCAL reference member, found {ref}")
    return ref[0]


def check_order(set_cfg, sets: dict) -> list[str]:
    """Pipeline codes of the set's cities, verifying that this repository's
    pooling order equals the study's."""
    s = study_set(set_cfg.name)
    codes = [study_code(c, s, sets) for c in set_cfg.cities]
    if tuple(codes) != tuple(sets[s]):
        raise ValueError(f"{set_cfg.name}: city order {codes} differs from the study's "
                         f"{list(sets[s])}")
    return codes


def load_features(study_root, code, aset, sets) -> tuple[pd.DataFrame, Path]:
    p = city_cache(study_root, code, aset, sets) / "block_features.parquet"
    return pd.read_parquet(p), p


def _labels(path, columns) -> pd.DataFrame:
    import pyogrio
    return pyogrio.read_dataframe(path, read_geometry=False, columns=columns)


def expected_city(study_root, code, aset):
    d = Path(study_root) / "output" / study_set(aset) / code
    lab = _labels(d / "blocks_clustered.geojson", ["block_id", "label_morpho"])
    sweep = pd.read_csv(d / "tables" / "k_sweep_morpho.csv")
    return lab, int(sweep["chosen_k"].iloc[0]), d / "blocks_clustered.geojson"


def expected_pooled(study_root, aset):
    d = Path(study_root) / "output" / study_set(aset) / "SHARED"
    lab = _labels(d / "blocks_clustered.geojson", ["city", "block_id", "label_morpho"])
    sweep = pd.read_csv(d / "tables" / "k_sweep_morpho.csv")
    return lab, int(sweep["chosen_k"].iloc[0]), d / "blocks_clustered.geojson", \
        d / "tables" / "k_sweep_morpho.csv"


def decision_k(study_root, aset, track="A"):
    """Pooled K recorded in output/pca_rule_decisions.csv (None if absent)."""
    p = Path(study_root) / "output" / "pca_rule_decisions.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p)
    r = d[(d["track"] == track) & (d["set"] == study_set(aset))]
    return int(r["k"].iloc[0]) if len(r) else None


def compare(expected: np.ndarray, got: np.ndarray) -> dict:
    from sklearn.metrics import adjusted_rand_score
    expected = np.asarray(expected)
    got = np.asarray(got)
    ok = ~pd.isna(expected)
    e = expected[ok].astype(int)
    g = got[ok]
    return {"ari": float(adjusted_rand_score(e, g)),
            "identical_ids": bool((e == g).all()),
            "n_compared": int(ok.sum()), "n_missing_reference": int((~ok).sum())}
