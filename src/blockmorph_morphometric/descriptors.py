"""The 46 morphometric descriptors of the international sets.

All descriptors are computed by the core (`blockmorph.descriptors`,
momepy 1.0) with `typology=None`, which yields exactly the core's
`MORPHO_COLUMNS` in their order. The international sets add one rule:

Partition-unit neutralisation (thirteen-city set only). For tier-3 partition units
(`block_kind == "partition"`), whose boundaries are analytic rather than the
city's, the descriptors that measure the unit itself - its size, outline,
building count, street frontage and edge/core position - are set to missing
(median-imputed by the model preprocessing). The intensive fabric
characters (density per ha, coverage, intensity, grain, configuration,
heights) and the neighbourhood context are kept. The context lag is
computed before the neutralisation, as in the study.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from blockmorph.descriptors import MORPHO_COLUMNS
from blockmorph.inputs import log

PARTITION_NEUTRAL = ("blk_area", "blk_perimeter", "blk_compactness", "blk_eri",
                     "blk_orientation", "n_buildings", "volume_sum",
                     "edge_building_share", "dist_to_edge_norm_mean")
ROAD_COLUMNS = tuple(c for c in MORPHO_COLUMNS if c.startswith("road_"))


def neutralised_columns(columns=MORPHO_COLUMNS) -> list[str]:
    """Columns set to missing for partition units, in descriptor order."""
    return [c for c in columns if c in PARTITION_NEUTRAL or c.startswith("road_")]


def neutralise_partition_units(feats: pd.DataFrame, blocks) -> tuple[pd.DataFrame, int]:
    """Set the unit-dependent descriptors of partition units to NaN.
    `blocks` needs `block_id` and (optionally) `block_kind`."""
    if "block_kind" not in blocks.columns:
        return feats, 0
    part = blocks.set_index("block_id")["block_kind"].eq("partition")
    part = part.reindex(feats.index).fillna(False).values.astype(bool)
    if not part.any():
        return feats, 0
    feats = feats.copy()
    cut = neutralised_columns(feats.columns)
    feats.loc[part, cut] = np.nan
    log(f"[descriptors] {int(part.sum())} partition units: {len(cut)} unit-dependent "
        "descriptors set to missing")
    return feats, int(part.sum())


def morphometric_descriptors(chars, blocks, streets, p) -> tuple[pd.DataFrame, int]:
    """46 descriptors per block from building characters that already carry
    the core's missing-data treatment (`blockmorph.missing.impute_heights`)."""
    from blockmorph.descriptors import block_descriptors
    f = block_descriptors(chars, blocks, streets, None, p)
    f, n_part = neutralise_partition_units(f, blocks)
    return f.replace([np.inf, -np.inf], np.nan), n_part


def as_model_input(feats: pd.DataFrame) -> pd.DataFrame:
    """The 46 Track A columns in the core order. Any `rcnn_*` column (the
    LOCAL building-form shares) is dropped: the international sets are
    morphometric only."""
    f = feats.drop(columns=[c for c in feats.columns if str(c).startswith("rcnn_")])
    missing = [c for c in MORPHO_COLUMNS if c not in f.columns]
    extra = [c for c in f.columns if c not in MORPHO_COLUMNS]
    if missing or extra:
        raise ValueError(f"descriptor table: missing {missing}, unexpected {extra}")
    return f[MORPHO_COLUMNS]
