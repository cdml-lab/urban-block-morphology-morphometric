import numpy as np
import pandas as pd
from blockmorph.descriptors import MORPHO_COLUMNS

from blockmorph_morphometric.config import load_set
from blockmorph_morphometric.model import fit_set, fit_track_a, pool


def _blobs(sizes, seed=0):
    rng = np.random.default_rng(seed)
    centres = rng.normal(0, 6, size=(len(sizes), 46))
    X = np.vstack([rng.normal(centres[i], 1, size=(n, 46)) for i, n in enumerate(sizes)])
    return pd.DataFrame(np.abs(X), columns=MORPHO_COLUMNS,
                        index=pd.Index(range(len(X)), name="block_id"))


def test_fit_track_a_city_rule():
    f = _blobs([40] * 6)
    fit = fit_track_a(f, load_set("three_cities").model.params("city"))
    assert fit.z.shape == (240, 5)
    assert fit.k == len(np.unique(fit.labels)) and 5 <= fit.k <= 15
    assert fit.sweep["k"].tolist() == list(range(5, 16))


def test_pooled_k_range_universal():
    p = load_set("thirteen_cities").model.params("pooled")
    fit = fit_track_a(_blobs([30] * 6, seed=1), p)
    assert fit.sweep["k"].max() == 25


def test_pool_keys_and_order():
    s = load_set("three_cities")
    frames = {"AMS": _blobs([20], 2), "A": _blobs([20], 3), "MAN": _blobs([20], 4)}
    F, area_of = pool(frames, s.cities)
    assert area_of[:20] == ["A"] * 20 and area_of[-1] == "AMS"
    assert F.index[0] == "A-0" and F.index[20] == "MAN-0"
    assert list(F.columns) == MORPHO_COLUMNS


def test_fit_descriptors_pooled(tmp_path):
    import json

    from blockmorph_morphometric.pipeline import fit_descriptors
    s = load_set("three_cities")
    parts = []
    for i, c in enumerate(["MAN", "A"]):              # deliberately not in set order
        f = _blobs([30] * 6, 10 + i)
        f.index = [f"{c}-{j}" for j in f.index]
        f.insert(0, "area", c)
        parts.append(f)
    t = pd.concat(parts)
    t.index.name = "block_key"
    reps = fit_descriptors(s, t, tmp_path)
    assert set(reps) == {"A", "MAN", "pooled"}
    a = pd.read_csv(tmp_path / "assignments.csv")
    assert a["area"].iloc[0] == "A" and a["area"].iloc[-1] == "MAN"   # set order
    assert a["pooled_type"].notna().all() and a["city_type"].notna().all()
    r = json.loads((tmp_path / "models" / "pooled" / "report.json").read_text())
    assert r["blocks"] == 360 and r["k_range"] == [5, 15]


def test_fit_set():
    s = load_set("three_cities")
    frames = {c: _blobs([30] * 6, i) for i, c in enumerate(s.cities)}
    res = fit_set(frames, s, progress=lambda *_: None)
    assert set(res) == {"A", "MAN", "AMS", "pooled"}
    assert len(res["pooled"].labels) == 540
