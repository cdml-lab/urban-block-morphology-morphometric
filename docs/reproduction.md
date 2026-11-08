# Reproducing the study's three-city and thirteen-city Track A partitions

In the study pipeline the two sets are called GLOBAL (`three_cities`) and UNIVERSAL
(`thirteen_cities`); its folders and decision record, read below, keep those names.

Three levels were verified on 2026-10-28 against the study pipeline (private;
its cache and output trees are needed):

- **A. Partitions.** All 16 city models and both pooled models are refitted
  from the study's descriptor tables and compared with the published labels
  (`scripts/check_reproduction.py`). **Required: identical K and
  ARI = 1.000.**
- **B. Units and descriptors.** The thirteen-city sampling units and the 46
  descriptors are recomputed from the study's cached inputs
  (`scripts/check_units.py`).
- **C. End to end.** `blockmorph-morphometric run` is applied to the raw inputs of
  City A (three-city and thirteen-city sets) and Rio de Janeiro (thirteen-city).

```bash
python scripts/check_reproduction.py --study-root <study pipeline root> --out reproduction_results/table
python scripts/check_units.py --study-root <study pipeline root> --set three_cities
python scripts/check_units.py --study-root <study pipeline root> --set thirteen_cities
```

`<study pipeline root>` holds `config.py`, `cache/` and `output/`.

## Inputs read by `check_reproduction.py`

- **Set membership and order.** `config.py` of the study pipeline is parsed
  (never imported), and this repository's pooling order must equal the
  study's. City A is the one member of a set that also belongs to the
  study's LOCAL set.
- **Descriptors.** `cache/<CODE>/block_features.parquet` for a city's first
  (home) set and `cache/<CODE>_<SET>/block_features.parquet` for a later
  set, by the study's cache rule (`reproduce.city_cache`). These are 46
  columns after the missing-data treatment, and for the thirteen-city set after the
  partition-unit neutralisation; `rcnn_*` columns are dropped if present
  (none are). Rows are in `block_id` order.
- **Published city labels.** `output/<SET>/<CODE>/blocks_clustered.geojson`
  (`block_id`, `label_morpho`) and the city's K from
  `tables/k_sweep_morpho.csv` (`chosen_k`).
- **Published pooled labels.** `output/<SET>/SHARED/blocks_clustered.geojson`
  (`city`, `block_id`, `label_morpho`, rows in pooling order) and
  `tables/k_sweep_morpho.csv`. The pooled K must also equal the decision
  record (`output/pca_rule_decisions.csv`: three-city 8, thirteen-city 12).
- **Freshness.** A reference label file older than the descriptors it
  should come from is reported `STALE` and fails. The study outputs were
  regenerated on 2026-10-28:
  - descriptors at 15:51–15:52;
  - city models at 16:00–16:12;
  - three-city pooled at 16:06;
  - thirteen-city pooled: K sweep at 16:27, labels at 16:50.

  `--wait <minutes>` polls (every 60 s) for a pooled reference that is
  still being written.

## A. Partitions: result

Verification run: Python 3.13.5, numpy 2.4.4, pandas 2.3.3,
scikit-learn 1.7.2, core 1.0.0 (`requirements-lock.txt`), Windows 11. Run
with the study machine's Python and repeated in the clean environment
(`_venvs/global_check`, see the bottom of this page). Both runs gave the
same table.

| set | model | blocks | K range | expected K | reproduced K | status | ARI | identical type ids |
|---|---|---|---|---|---|---|---|---|
| three-city | A | 1,590 | 5–15 | 9 | 9 | rule | 1.000 | yes |
| three-city | MAN | 3,258 | 5–15 | 8 | 8 | rule | 1.000 | yes |
| three-city | AMS | 2,708 | 5–15 | 11 | 11 | rule | 1.000 | yes |
| three-city | **pooled** | 7,556 | 5–15 | 8 | 8 | rule | 1.000 | yes |
| thirteen-city | A | 1,609 | 5–15 | 9 | 9 | rule | 1.000 | yes |
| thirteen-city | MAN | 3,258 | 5–15 | 8 | 8 | rule | 1.000 | yes |
| thirteen-city | AMS | 2,858 | 5–15 | 11 | 11 | rule | 1.000 | yes |
| thirteen-city | MTL | 2,329 | 5–15 | 8 | 8 | rule | 1.000 | yes |
| thirteen-city | BCN | 2,271 | 5–15 | 9 | 9 | rule | 1.000 | yes |
| thirteen-city | RIO | 1,412 | 5–15 | 8 | 8 | rule | 1.000 | yes |
| thirteen-city | SAO | 2,185 | 5–15 | 8 | 8 | rule | 1.000 | yes |
| thirteen-city | NBO | 3,597 | 5–15 | 9 | 9 | rule | 1.000 | yes |
| thirteen-city | CAI | 4,821 | 5–15 | 11 | 11 | rule | 1.000 | yes |
| thirteen-city | LOS | 4,062 | 5–15 | 8 | 8 | rule | 1.000 | yes |
| thirteen-city | BOM | 2,534 | 5–15 | 9 | 9 | rule | 1.000 | yes |
| thirteen-city | TYO | 9,460 | 5–15 | 8 | 8 | rule | 1.000 | yes |
| thirteen-city | SYD | 2,074 | 5–15 | 8 | 8 | rule | 1.000 | yes |
| thirteen-city | **pooled** | 42,470 | 5–25 | 12 | 12 | rule | 1.000 | yes |

`REPRODUCTION_OK`. The labels agree exactly, with the same integer type
ids, not just the same partition up to relabelling.

**Run time.** About 3 minutes for the 16 city models and the three-city pooled
model. About 19–20 minutes for the thirteen-city pooled model, mostly
the core's Gaussian-null silhouette baseline on 42,470 units for 21
values of K.

## B. Sampling units and descriptors (`check_units.py`)

Per city, from the study's cached buildings, enclosures, enclosed
tessellation, streets and building characters:

| set | cities | units: count, kinds, order, ids of every building | unit polygons (largest relative area difference) | 46 descriptors (largest difference / column range; NaN pattern) |
|---|---|---|---|---|
| three-city | A, MAN, AMS | (plain blocks) 1,590 / 3,258 / 2,708 = study | – | 0.0; identical |
| thirteen-city | all 13 | identical in all 13 cities (trimmed blocks, mega-blocks, patch and partition units, renumbering) | 0.0 in 12 cities; 2.2e-12 in Tokyo | 0.0; identical |

`UNITS_OK` for both sets.

**Building characters (spot check).** `--chars` recomputes the building
characters with the core (momepy) from the cached buildings, tessellation,
streets and units. They are identical (largest difference 0.0) for City A
(three-city), Rio and Nairobi (thirteen-city).

**Tier 1 (all roads cut).** The decision is recomputed from the cached
networks and agrees in every city:
- applied in Rio, Lagos, Mumbai and Tokyo;
- not needed in Nairobi, where every way already cuts blocks;
- not triggered in the other 8 cities. Their recomputed shares of
  buildings in mega-blocks equal the study's records (City A 0.014,
  Amsterdam 0.061, São Paulo 0.166, Cairo 0.163, ...).

For the four tier-1 cities, the study's `block_rule.json` records a
"default-roads" share that cannot be recomputed:

| city | recomputed default-roads share | recorded |
|---|---|---|
| RIO | 0.448 | 0.357 |
| LOS | 0.558 | 0.422 |
| BOM | 0.499 | 0.445 |
| TYO | 0.530 | 0.516 |

- **RIO, LOS, BOM.** The record equals the recorded all-roads share. The
  record was written on a re-run whose cached network was already the
  all-roads one. The end-to-end run of Rio (part C) reproduces both
  numbers: 0.448 with the default classes, 0.357 with all roads.
- **TYO.** The small difference is not explained by the caches.
- **Effect.** Every share is far above the 0.20 trigger, so the units,
  descriptors and partitions are unaffected.

## C. End to end from raw inputs (`blockmorph-morphometric run`)

| run | inputs | units | descriptors vs study (largest difference / range) | city-model labels |
|---|---|---|---|---|
| three-city, City A | core archive `inputs/A/` + study area | 1,590 = study | 8.4e-6 (`car_mean`), NaN pattern identical | K 9, ARI 1.000, identical ids |
| thirteen-city, City A | same | 1,609 = study (21 trimmed, 1 mega-block → 20 patches) | 8.2e-6 (`car_mean`) | K 9, ARI 1.000, identical ids |
| thirteen-city, Rio | Overture footprints (2026-08-19.0), automatic heights, the study's street network (file), boundary ∩ clip box | 1,412 = study (733 patches, 20 partitions) | 2.7e-16, identical | K 8, ARI 1.000, identical ids |

- **Rio heights.** The automatic selection reproduces the study's decision
  exactly: sample coverage OSM 0.398, 3D-GloBFP 0.688, Open Buildings 2.5D
  0.960, so Open Buildings 2.5D is chosen.
- **`car_mean`.** It depends on the enclosed tessellation, whose cell
  geometry varies at about 1e-5 between runs (as in the core). That
  variation does not reach the partitions.

## Conditions for exact partitions

- **Column order.** Use the 46 descriptors in the core's `MORPHO_COLUMNS`
  order, which is the study's column order.
- **Row order.**
  - Blocks in `block_id` order.
  - Cities pooled in the set's order:
    - three-city: A, MAN, AMS;
    - thirteen-city: A, MAN, AMS, MTL, BCN, RIO, SAO, NBO, CAI, LOS, BOM, TYO,
      SYD.

  K-means initialisation depends on row order.
- **K range.** 5–15 for city models and the three-city pooled model; 5–25 for
  the thirteen-city pooled model. With 5–15 the thirteen-city pooled model would
  be a different model.
- **Partition units.** Use the descriptors with the partition-unit
  neutralisation applied (the study's cached descriptors already carry it).
- **Model settings.** Whitened PCA with 5 components; K-means `n_init` 10,
  seed 42; minimum type size 12.
- **Library versions.** Exact identity is guaranteed with the locked
  versions (`requirements-lock.txt`), as for the core.

## Clean environment

```bat
C:\Python313\python.exe -m venv C:\...\Release\_venvs\global_check
C:\...\_venvs\global_check\Scripts\python.exe -m pip install --upgrade pip
...\python.exe -m pip install -r ..\urban-block-morphology\requirements-lock.txt
...\python.exe -m pip install -e ..\urban-block-morphology
...\python.exe -m pip install -e .[test,fetch]
...\python.exe -m pytest -q                      -> 28 passed
...\Scripts\blockmorph-morphometric fit three_cities examples\data\three_cities_sample_MAN_descriptors.csv --out <tmp>
                                                 -> K = 8 (rule), admissible K 8 and 9
...\python.exe scripts\check_reproduction.py --study-root <root>   -> REPRODUCTION_OK (18 of 18 models exact)
...\python.exe scripts\check_units.py --study-root <root> --set three_cities      -> UNITS_OK
...\python.exe scripts\check_units.py --study-root <root> --set thirteen_cities   -> UNITS_OK
```

Versions: Python 3.13.5, momepy 1.0.0, libpysal 4.15.0, geopandas 1.1.3,
shapely 2.1.2, pandas 2.3.3, numpy 2.4.4, scipy 1.16.2, scikit-learn 1.7.2,
kneed 0.8.5, osmnx 2.1.0, pyogrio 0.12.1, pyproj 3.7.2, pyarrow 24.0.0. Full
list: `requirements-lock.txt`.
