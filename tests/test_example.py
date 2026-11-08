import json
from pathlib import Path

import pandas as pd

from blockmorph_morphometric.config import load_set
from blockmorph_morphometric.pipeline import fit_descriptors

ROOT = Path(__file__).resolve().parents[1]


def test_example_runs(tmp_path):
    t = pd.read_csv(ROOT / "examples" / "data" / "three_cities_sample_MAN_descriptors.csv",
                    index_col="block_key")
    assert t.shape == (400, 47) and set(t["area"]) == {"MAN"}
    rep = fit_descriptors(load_set("three_cities"), t, tmp_path)
    r = json.loads((tmp_path / "models" / "MAN" / "report.json").read_text())
    assert r["descriptors"] == 46 and r["pca_components"] == 5
    assert r["selected_k"] == rep["MAN"]["selected_k"]
    # value of the verification run (requirements-lock.txt versions)
    assert (r["selected_k"], r["status"]) == (8, "rule")
    a = pd.read_csv(tmp_path / "assignments.csv")
    assert len(a) == 400 and a["city_type"].nunique() == 8
