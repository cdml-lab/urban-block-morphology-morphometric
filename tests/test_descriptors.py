import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from blockmorph.descriptors import MORPHO_COLUMNS
from shapely.geometry import box

from blockmorph_morphometric.descriptors import (PARTITION_NEUTRAL, as_model_input,
                                           neutralise_partition_units, neutralised_columns)


def _feats(n=4):
    rng = np.random.default_rng(0)
    return pd.DataFrame(rng.random((n, 46)), columns=MORPHO_COLUMNS,
                        index=pd.Index(range(n), name="block_id"))


def test_neutralised_columns():
    cols = neutralised_columns()
    assert len(cols) == 13
    assert set(cols) == set(PARTITION_NEUTRAL) | {c for c in MORPHO_COLUMNS
                                                  if c.startswith("road_")}
    assert "gsi" not in cols and "ctx_gsi" not in cols and "blg_density_ha" not in cols


def test_neutralise_only_partitions():
    f = _feats()
    blocks = gpd.GeoDataFrame({"block_id": [0, 1, 2, 3],
                               "block_kind": ["street", "partition", "patch", "partition"]},
                              geometry=[box(i, 0, i + 1, 1) for i in range(4)])
    g, n = neutralise_partition_units(f, blocks)
    assert n == 2
    cut = neutralised_columns()
    assert g.loc[[1, 3], cut].isna().all().all()
    assert g.loc[[0, 2]].notna().all().all()
    keep = [c for c in MORPHO_COLUMNS if c not in cut]
    assert np.allclose(g.loc[[1, 3], keep], f.loc[[1, 3], keep])
    same, n0 = neutralise_partition_units(f, blocks.drop(columns="block_kind"))
    assert n0 == 0 and same is f


def test_as_model_input():
    f = _feats()
    f["rcnn_l_shape"] = 0.5
    shuffled = f[list(reversed(f.columns))]
    x = as_model_input(shuffled)
    assert list(x.columns) == MORPHO_COLUMNS
    with pytest.raises(ValueError):
        as_model_input(f.drop(columns="gsi"))
