import numpy as np
import pytest

from blockmorph_morphometric import reproduce as R
from blockmorph_morphometric.config import load_set

CONFIG = """
REFERENCE_CITIES = ("ISR", "LC2", "LC3")
GLOBAL_CITIES = ("ISR", "MAN", "AMS")
UNIVERSAL_CITIES = ("ISR", "MAN", "AMS", "MTL", "BCN", "RIO", "SAO",
                    "NBO", "CAI", "LOS", "BOM", "TYO", "SYD")
SETS = {"LOCAL": REFERENCE_CITIES, "GLOBAL": GLOBAL_CITIES,
        "UNIVERSAL": UNIVERSAL_CITIES}
"""


@pytest.fixture
def sets(tmp_path):
    (tmp_path / "config.py").write_text(CONFIG)
    return tmp_path, R.read_sets(tmp_path)


def test_read_sets(sets):
    _, s = sets
    assert list(s) == ["LOCAL", "GLOBAL", "UNIVERSAL"]
    assert s["GLOBAL"] == ("ISR", "MAN", "AMS")


def test_cache_rule(sets):
    root, s = sets

    def c(code, st):
        return R.city_cache(root, code, st, s).name
    assert c("ISR", "LOCAL") == "ISR"
    assert c("ISR", "GLOBAL") == "ISR_GLOBAL"
    assert c("ISR", "UNIVERSAL") == "ISR_UNIVERSAL"
    assert c("MAN", "GLOBAL") == "MAN"                 # home set
    assert c("MAN", "UNIVERSAL") == "MAN_UNIVERSAL"
    assert c("RIO", "UNIVERSAL") == "RIO"               # single-set city
    # the public set names read the pipeline under its own names
    assert c("ISR", "three_cities") == "ISR_GLOBAL"
    assert c("MAN", "thirteen_cities") == "MAN_UNIVERSAL"


def test_city_a_alias_and_order(sets):
    _, s = sets
    assert R.study_code("A", "GLOBAL", s) == "ISR"
    assert R.study_code("MAN", "GLOBAL", s) == "MAN"
    assert R.check_order(load_set("three_cities"), s) == ["ISR", "MAN", "AMS"]
    assert R.check_order(load_set("thirteen_cities"), s)[3:] == list(s["UNIVERSAL"][3:])
    bad = dict(s)
    bad["GLOBAL"] = ("MAN", "ISR", "AMS")
    with pytest.raises(ValueError):
        R.check_order(load_set("three_cities"), bad)


def test_compare():
    r = R.compare(np.array([0, 0, 1, 1, np.nan]), np.array([1, 1, 0, 0, 3]))
    assert r["ari"] == 1.0 and not r["identical_ids"] and r["n_missing_reference"] == 1
