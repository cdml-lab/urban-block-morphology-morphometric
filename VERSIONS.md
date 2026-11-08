# Versions used together

| component | version | note |
|---|---|---|
| urban-block-morphology-morphometric (this repository) | v1.0.0 | Track A of the three-city and thirteen-city sets |
| urban-block-morphology (core, `blockmorph`) | **v1.0.0** (pinned: `urban-block-morphology==1.0.0`) | blocks, 46 descriptors, missing-data treatment, PCA, K-means, K rule |
| results archive of the core | v1.0.0 | City A inputs (`inputs/A/`) |
| descriptor set | `morphometric46` | no building-typology input; building-typology-rcnn is not used |
| momepy | 1.0.0 | descriptors (via the core) |
| scikit-learn | 1.7.2 | PCA, K-means, quality scores; exact partitions are guaranteed with the locked versions |
| Overture Maps buildings | release 2026-08-19.0 | thirteen-city footprints |
| 3D-GloBFP | Zenodo record 11319912 (grid) + figshare tiles | heights |
| Google Open Buildings 2.5D Temporal | year 2023, `building_height` | heights (Rio de Janeiro) |
| GADM | 4.1 | Cairo units, land clip |

Exact library versions of the verification run: `requirements-lock.txt`.
