"""Track A models of the international sets: one model per city and one
pooled model per set, fitted with the core procedure
(`blockmorph.model.pca_space` + `blockmorph.model.select_k`):

  46 descriptors -> median imputation, log1p (|skew| > 1.5), winsorising
  0.5/99.5 %, standardisation -> whitened PCA (5 components) -> K-means
  (n_init 10, seed 42) over the set's K range -> K rule (minimum type
  size 12, inertia-elbow floor, best combined score).

The only set-specific settings are the PCA dimensionality (5 in both sets,
pre-registered decision rule) and the K range per model: 5-15 for every
city model and for the three-city pooled model, 5-25 for the thirteen-city pooled
model (13 cities, ~42,000 blocks).

Row order matters for K-means initialisation: cities are pooled in the
set's order, blocks in `block_id` order within each city.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from blockmorph.model import pca_space, select_k
from blockmorph.params import Params

from .descriptors import as_model_input


@dataclass
class TrackAFit:
    labels: np.ndarray
    sweep: pd.DataFrame
    status: dict
    z: np.ndarray
    pca: object

    @property
    def k(self) -> int:
        return int(self.status["selected_k"])


def fit_track_a(feats: pd.DataFrame, p: Params) -> TrackAFit:
    """One Track A model on a descriptor table (rows = blocks, in order)."""
    x = as_model_input(feats)
    z, pca = pca_space(x, p)
    labels, sweep, status = select_k(z, p)
    return TrackAFit(labels=np.asarray(labels), sweep=sweep, status=status, z=z, pca=pca)


def pool(frames: dict, order) -> tuple[pd.DataFrame, list]:
    """Pooled descriptor table in the set's city order. Index = block_key
    `<city id>-<block_id>`; returns (table, city of each row)."""
    parts, area_of = [], []
    for c in order:
        f = as_model_input(frames[c]).copy()
        f.index = [f"{c}-{int(i)}" for i in f.index]
        parts.append(f)
        area_of += [c] * len(f)
    out = pd.concat(parts)
    out.index.name = "block_key"
    return out, area_of


def fit_set(frames: dict, set_cfg, cities=None, pooled=True, progress=print):
    """City models and the pooled model of a set from per-city descriptor
    tables ({city id: DataFrame indexed by block_id}). Returns
    {model id: TrackAFit}; the pooled model is keyed 'pooled'."""
    cities = list(cities or set_cfg.cities)
    pc = set_cfg.model.params("city")
    out = {}
    for c in cities:
        out[c] = fit_track_a(frames[c], pc)
        progress(f"[model {c}] K = {out[c].k} ({out[c].status['status']})")
    if pooled and len(cities) > 1:
        F, _ = pool(frames, cities)
        out["pooled"] = fit_track_a(F, set_cfg.model.params("pooled"))
        progress(f"[model pooled] K = {out['pooled'].k} ({out['pooled'].status['status']})")
    return out
