import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from blockmorph_morphometric.refine import (RefineParams, _partition_ids, mega_share,
                                      split_mega_blocks, trim_open_blocks)


def _grid(x0, y0, nx, ny, step, size):
    return [box(x0 + i * step, y0 + j * step, x0 + i * step + size, y0 + j * step + size)
            for i in range(nx) for j in range(ny)]


def _blocks(geoms, b, eid=0):
    """One block as the core's make_blocks returns it."""
    bl = gpd.GeoDataFrame({"eID": [eid], "block_id": [0],
                           "footprint_m2": [b["footprint_m2"].sum()]},
                          geometry=geoms, crs=32631)
    bl["area_m2"] = bl.geometry.area
    bl["gsi"] = bl["footprint_m2"] / bl["area_m2"]
    return bl


def test_trim_open_block():
    # 400 m x 400 m block, a hamlet of 9 houses in one corner
    blocks = gpd.GeoDataFrame({"eID": [0], "block_id": [0], "footprint_m2": [900.0]},
                              geometry=[box(0, 0, 400, 400)], crs=32631)
    b = gpd.GeoDataFrame({"block_id": [0] * 9}, geometry=_grid(10, 10, 3, 3, 20, 10),
                         crs=32631)
    ctx = gpd.GeoDataFrame({"eID": [], "footprint_m2": [], "area_m2": [], "gsi": []},
                           geometry=[], crs=32631)
    bl, ctx2, n = trim_open_blocks(blocks, ctx, b, RefineParams())
    assert n == 1 and bl["block_trim"].iloc[0] < 0.5
    assert len(ctx2) == 1
    assert abs(bl.geometry.iloc[0].area + ctx2.geometry.iloc[0].area - 160_000) < 1e-6


def test_trim_keeps_built_blocks():
    blocks = gpd.GeoDataFrame({"eID": [0], "block_id": [0], "footprint_m2": [1.0]},
                              geometry=[box(0, 0, 100, 100)], crs=32631)
    b = gpd.GeoDataFrame({"block_id": [0] * 4}, geometry=_grid(10, 10, 2, 2, 60, 20),
                         crs=32631)
    ctx = gpd.GeoDataFrame({"eID": []}, geometry=[], crs=32631)
    bl, _, n = trim_open_blocks(blocks, ctx, b, RefineParams())
    assert n == 0 and bl["block_trim"].iloc[0] == 1.0


def test_mega_share():
    blocks = gpd.GeoDataFrame({"block_id": [0, 1]},
                              geometry=[box(0, 0, 400, 400), box(500, 0, 520, 20)], crs=32631)
    b = pd.DataFrame({"block_id": [0] * 200 + [1] * 50})
    share, n = mega_share(blocks, b, RefineParams())
    assert n == 1 and share == 200 / 250


def test_partition_caps_unit_size():
    rng = np.random.default_rng(0)
    xy = rng.random((700, 2)) * 300
    b = gpd.GeoDataFrame(geometry=[box(x, y, x + 2, y + 2) for x, y in xy], crs=32631)
    lab = _partition_ids(b, RefineParams())
    assert np.bincount(lab).max() <= 150 and len(np.unique(lab)) >= 5


def test_split_mega_block_into_patches():
    # one 9 ha block holding 4 clusters of 64 houses separated by wide alleys
    geoms = []
    for cx, cy in [(0, 0), (150, 0), (0, 150), (150, 150)]:
        geoms += _grid(cx + 5, cy + 5, 8, 8, 15, 12)
    b = gpd.GeoDataFrame({"block_id": [0.0] * len(geoms)}, geometry=geoms, crs=32631)
    b["footprint_m2"] = b.geometry.area
    blocks = _blocks([box(0, 0, 300, 300)], b, eid=7)
    tess = gpd.GeoDataFrame(geometry=b.geometry.buffer(1.4, join_style="mitre"), crs=32631)
    out, b2, stats = split_mega_blocks(blocks, b, tess, RefineParams())
    assert stats["mega_blocks"] == 1 and stats["patch_units"] == 4
    assert stats["d_used"] == {"3.0": 1}
    assert len(out) == 4 and set(out["block_kind"]) == {"patch"}
    assert out["block_id"].tolist() == [0, 1, 2, 3]
    assert sorted(b2["block_id"].value_counts().tolist()) == [64] * 4
    assert (out["eID"] == 7).all()


def test_split_partition_tier():
    # 400 touching houses: no alley at any d -> tier-3 partition units
    geoms = _grid(0, 0, 20, 20, 10, 10)
    b = gpd.GeoDataFrame({"block_id": [0.0] * len(geoms)}, geometry=geoms, crs=32631)
    b["footprint_m2"] = b.geometry.area
    blocks = _blocks([box(-50, -50, 250, 250)], b)
    tess = gpd.GeoDataFrame(geometry=b.geometry, crs=32631)
    out, b2, stats = split_mega_blocks(blocks, b, tess, RefineParams())
    assert stats["partition_units"] >= 3 and set(out["block_kind"]) == {"partition"}
    assert b2["block_id"].value_counts().max() <= 150


def test_exemptions():
    geoms = _grid(5, 5, 16, 16, 18, 6)                  # 256 small huts, GSI ~0.10
    b = gpd.GeoDataFrame({"block_id": [0.0] * len(geoms)}, geometry=geoms, crs=32631)
    b["footprint_m2"] = b.geometry.area
    blocks = _blocks([box(0, 0, 300, 300)], b)
    tess = gpd.GeoDataFrame(geometry=b.geometry.buffer(1), crs=32631)
    out, _, stats = split_mega_blocks(blocks, b, tess, RefineParams())
    assert stats["exempt_open"] == 1 and stats["mega_blocks"] == 0 and len(out) == 1
