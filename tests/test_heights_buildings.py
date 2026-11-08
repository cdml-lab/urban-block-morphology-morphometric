import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from blockmorph_morphometric import heights as H
from blockmorph_morphometric.buildings import clean_footprints, derive_3d, standardise_tags


def _frame(n=600, known=0.0, crs=32631):
    g = gpd.GeoDataFrame(geometry=[box(i * 20, 0, i * 20 + 10, 10) for i in range(n)], crs=crs)
    h = np.full(n, np.nan)
    h[: int(known * n)] = 9.0
    g["height_m"] = h
    return g


def _filler(cov):
    def f(g):
        g = g.copy()
        k = int(round(cov * len(g)))
        g.iloc[:k, g.columns.get_loc("height_m")] = 12.0
        return g
    return f


def test_select_height_source_rank_and_threshold():
    g = _frame(known=0.2)
    chosen, table = H.select_height_source(g, {"osm": None, "globfp": _filler(0.8),
                                               "ob25d": _filler(0.95)})
    assert chosen == "globfp"                      # highest-ranked source >= 70 %
    assert [r["source"] for r in table] == ["osm", "globfp", "ob25d"]
    chosen, _ = H.select_height_source(g, {"osm": None, "globfp": _filler(0.6),
                                           "ob25d": _filler(0.9)})
    assert chosen == "ob25d"
    chosen, _ = H.select_height_source(g, {"osm": None, "globfp": _filler(0.5),
                                           "ob25d": _filler(0.4)})
    assert chosen == "globfp"                      # none reaches 70 %: best covering
    chosen, _ = H.select_height_source(_frame(known=0.9), {"osm": None, "globfp": _filler(1)})
    assert chosen == "osm"


def test_heights_from_globfp_and_file(tmp_path):
    g = _frame(5)
    tile = gpd.GeoDataFrame({"Height": [15.0, 1.0, 300.0]},
                            geometry=[box(-1, -1, 11, 11), box(19, -1, 31, 11),
                                      box(39, -1, 51, 11)], crs=32631).to_crs(4326)
    p = tmp_path / "tile.gpkg"
    tile.to_file(p)
    out = H.heights_from_globfp(g.copy(), [p], 32631, 260.0)
    assert abs(out["height_m"].iloc[0] - 15.0) < 1e-9
    assert out["height_m"].iloc[1:].isna().all()          # 1 m and 300 m are discarded
    src = gpd.GeoDataFrame({"height_roof": [100.0, 50.0]},
                           geometry=[box(1, 1, 3, 3), box(5, 5, 7, 7)], crs=32631)
    f = tmp_path / "nyc.geojson"
    src.to_file(f, driver="GeoJSON")
    out = H.heights_from_file(g.copy(), f, "height_roof", 32631, 550.0, unit="ft")
    assert abs(out["height_m"].iloc[0] - 30.48) < 1e-9     # tallest part, feet -> metres


def test_standardise_and_clean():
    g = gpd.GeoDataFrame({"btype": ["yes", "shed", None, "house"],
                          "levels": ["3", "1", "0", None],
                          "height_tag": ["12 m", None, "1", "400"]},
                         geometry=[box(0, 0, 10, 10), box(20, 0, 30, 10), box(40, 0, 50, 10),
                                   box(60, 0, 70, 10)], crs=32631)
    for c in ("btype", "levels", "height_tag"):
        g[c] = g[c].astype("string")
    s = standardise_tags(g, 260.0)
    assert len(s) == 3                                     # the shed is dropped
    assert s["height_m"].iloc[0] == 12.0 and s["height_m"].isna().sum() == 2
    assert pd.isna(s["floors"].iloc[1])                    # 0 floors = unknown
    dup = pd.concat([s.iloc[[0]].assign(height_m=20.0), s,
                     gpd.GeoDataFrame({"btype": ["yes"], "floors": [1.0], "height_m": [3.0]},
                                      geometry=[box(80, 0, 83, 3)], crs=32631)])
    dup = dup.reset_index(drop=True)                      # one row per footprint, unique index
    c = clean_footprints(gpd.GeoDataFrame(dup, crs=32631), 10.0, 32631)
    assert len(c) == 3 and c["height_m"].max() == 20.0    # stacked duplicate: tallest; 9 m2 dropped
    d = derive_3d(c.copy())
    assert np.allclose(d["footprint_m2"], 100.0)
    assert d.loc[d["height_m"] == 20.0, "floors"].iloc[0] == 3.0   # tagged floors kept
    assert d.loc[d["height_m"].isna(), "floors"].isna().all()
