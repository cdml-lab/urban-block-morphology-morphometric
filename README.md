# urban-block-morphology-morphometric

Morphometric urban-block classifications (Track A) for the two city sets
of the study:

- **three-city set** (`three_cities`): 3 cities (City A, the Israeli reference city; Manhattan;
  Amsterdam), 7,556 blocks;
- **thirteen-city set** (`thirteen_cities`): 13 cities on six continents, 42,470 sampling units.

The model is **morphometric only**: 46 block descriptors, no
building-typology (R-CNN) input. It is fitted once per city (city models)
and once per set on all its cities together (pooled model).

This repository builds on the core package
[`urban-block-morphology`](../urban-block-morphology) **v1.0.0** (import name
`blockmorph`). The core supplies block delineation, the 46 descriptors, the
missing-data treatment, the preprocessing, whitened PCA, K-means and the K
rule. This repository adds only what the international sets need and the
core lacks:

- an analysis CRS per city, with only the descriptor tables pooled;
- building and height sources for cities outside Israel: OSM and Overture
  Maps footprints; NYC roof heights, 3D-GloBFP and Google Open Buildings
  2.5D heights; automatic selection of one height source per city;
- per-city building filters (10 m² footprint floor in informal fabric,
  550 m height ceiling in Manhattan);
- for the thirteen-city set, refinement of blocks into comparable sampling units:
  built-envelope trimming, all-roads cutting, and splitting mega-blocks
  along their alleys or into ~150-building partitions. The unit-dependent
  descriptors of partition units are neutralised;
- set configurations: city order, PCA dimensionality, and the K range per
  model (5–15; 5–25 for the thirteen-city pooled model).

Changes that belong in the core are proposed in `docs/core_changes_needed.md`.
The core itself is not modified.

Command line: `blockmorph-morphometric`; Python import name: `blockmorph_morphometric`.

## Install

```bash
# next to a checkout of the core repository:
python -m venv .venv && .venv\Scripts\activate          # Windows
pip install -r requirements-lock.txt                     # exact versions of the verification run
pip install -e ../urban-block-morphology                 # core v1.0.0
pip install -e .[test]                                    # this package (+ [fetch] for downloads)
pytest -q
```

Or use `conda env create -f environment.yml`. Install editable (`-e`):
the set and city configurations are read from `configs/`.

## Example

```bash
blockmorph-morphometric info three_cities
blockmorph-morphometric fit three_cities examples/data/three_cities_sample_MAN_descriptors.csv --out examples/example_output
```

This fits the city model on 400 Manhattan blocks (46 descriptors, derived
numbers only; `examples/README.md`). The verification run gives K = 8 (rule).

## Reproducing the study's partitions

`scripts/check_reproduction.py` refits every Track A model of both sets (16
city models and two pooled models) from the study pipeline's descriptor
tables and compares the labels with the published ones. All 18 models are
reproduced exactly: identical K, ARI = 1.000 and identical type ids
(`docs/reproduction.md`). `scripts/check_units.py` also recomputes the
thirteen-city sampling units and the 46 descriptors from the study's cached
inputs; both are identical.

| set | model | blocks | K |
|---|---|---|---|
| three-city | pooled (A, MAN, AMS) | 7,556 | 8 |
| thirteen-city | pooled (13 cities) | 42,470 | 12 |

The city-model K values are in `docs/reproduction.md` and `docs/sets.md`.

## Running a set from its inputs

```bash
blockmorph-morphometric fetch boundary  --set thirteen_cities --city RIO   # OSM relations / GADM selection
blockmorph-morphometric fetch buildings --set thirteen_cities --city RIO   # Overture release 2026-08-19.0
blockmorph-morphometric fetch heights   --set universal --city RIO   # 3D-GloBFP tile(s), Open Buildings 2.5D
blockmorph-morphometric run thirteen_cities --cities RIO --data data --out outputs/thirteen_cities
```

Inputs live in `data/<city id>/` (`docs/sets.md`). City A's inputs are those
of the core's results archive v1.0.0 (`inputs/A/`). Its study-area polygon
is available on request, as for the core. Live services change over time
(OSM, Overture), so a new download is not byte-identical to the study's
inputs. Exact reproduction is defined on the study's descriptor tables
(above).

Outputs follow the core's layout: `descriptors.csv`, `assignments.csv`,
`block_stats.csv`, `models/<model>/` (K sweep, report, profiles,
representatives), `areas/<id>/` (blocks with `block_kind`, buildings,
streets, unit and height-source records) and `run.json`.

## What is not here

- Construction years, land use, prices and external-validation results.
  They stay private.
- Imagery. Track A does not use it. Only the extent of the study's imagery
  enters, as a clip box in each city configuration.
- Large data. Building, height and boundary sources are documented with
  their licences in `docs/sources.md`.

## Documentation

`docs/method.md` (procedure) · `docs/sets.md` (cities and inputs) ·
`docs/configuration.md` (PCA and K decisions) · `docs/reproduction.md` ·
`docs/sources.md` (data and licences) · `docs/core_changes_needed.md`.

## Licence and citation

Code: MIT (`LICENSE`). The example data is derived from OpenStreetMap
(© OpenStreetMap contributors, ODbL 1.0) and NYC Open Data
(`examples/data/README.md`). Please cite with `CITATION.cff`.

Author removed for anonymity; will be added after the article is accepted.
