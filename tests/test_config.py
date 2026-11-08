from pathlib import Path

import pytest
from pyproj import CRS

from blockmorph_morphometric.config import load_set

ROOT = Path(__file__).resolve().parents[1]


def test_sets_and_order():
    g = load_set("three_cities")
    u = load_set("universal")
    assert g.cities == ["A", "MAN", "AMS"]
    assert u.cities == ["A", "MAN", "AMS", "MTL", "BCN", "RIO", "SAO", "NBO", "CAI", "LOS",
                        "BOM", "TYO", "SYD"]
    assert g.refine is None and u.refine is not None


def test_model_settings():
    g, u = load_set("three_cities"), load_set("thirteen_cities")
    for s in (g, u):
        assert s.model.pca_components == 5 and s.model.pca_whiten
        assert s.model.params("city").k_range == tuple(range(5, 16))
        assert s.model.params("city").min_type_size == 12
        assert s.model.params("city").kmeans_n_init == 10
        assert s.model.params("city").random_state == 42
    assert g.model.params("pooled").k_range == tuple(range(5, 16))
    assert u.model.params("pooled").k_range == tuple(range(5, 26))
    with pytest.raises(ValueError):
        g.model.params("other")


def test_refinement_parameters():
    rp = load_set("thirteen_cities").refine
    assert (rp.mega_block_ha, rp.mega_block_bldg, rp.share_all_roads) == (8.0, 150, 0.20)
    assert rp.split_ds == (3.0, 2.0, 1.5, 1.0) and rp.target_bldg == 150
    assert rp.min_patch_bldg == 3
    assert (rp.trim_buffer_m, rp.trim_max_envelope) == (30.0, 0.5)
    assert (rp.split_min_gsi, rp.split_max_footprint_m2, rp.partition_seed) == (0.15, 300.0, 42)


def test_city_configs():
    u = load_set("thirteen_cities")
    for cid, c in u.city_configs.items():
        crs = CRS.from_user_input(c.crs)
        assert crs.is_projected and crs.axis_info[0].unit_name in ("metre", "meter"), cid
        assert c.min_building_area_m2 in (10.0, 25.0)
    cc = u.city_configs
    assert {k for k, c in cc.items() if c.min_building_area_m2 == 10.0} == \
        {"RIO", "SAO", "NBO", "CAI", "LOS", "BOM"}
    assert [k for k, c in cc.items() if c.cut_all_roads] == ["NBO"]
    assert cc["MAN"].max_height_m == 550.0
    assert cc["MAN"].heights["policy"] == "file" and cc["MAN"].heights["unit"] == "ft"
    assert all(cc[k].heights["policy"] == "auto" for k in u.cities[3:])
    assert cc["A"].crs == "EPSG:2039"
    p = cc["RIO"].params()
    assert p.min_building_area_m2 == 10.0 and p.min_block_area_m2 == 1500.0


def test_city_a_is_anonymised():
    a = load_set("three_cities").city_configs["A"]
    assert a.id == "A" and a.name == "City A (Israeli reference city)"
    assert a.boundary["kind"] == "file"            # study area on request, never fetched
    for s in ("three_cities", "thirteen_cities"):
        assert "City A" in load_set(s).title or s == "thirteen_cities"
