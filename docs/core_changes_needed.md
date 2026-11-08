# Proposed changes to the core (`urban-block-morphology` v1.1.0)

The core v1.0.0 was **not modified**. Everything below is implemented in this
repository (module named in brackets) and proposed for a core v1.1.0, so
that the international sets can run through `blockmorph run`. None of these
changes alters a v1.0.0 result: every default keeps the current behaviour.

The reproduction itself needed **no** core change. The core's
`pca_space` + `select_k`, called with the set's parameters, reproduce all
18 published three-city and thirteen-city Track A partitions exactly
(`docs/reproduction.md`). The core's blocks, tessellation, building
characters, missing-data treatment and descriptors reproduce the study's
46 descriptors (largest difference 0 to 2.7e-16 of a column's range on the
cached characters; 8.4e-6, `car_mean`, end to end from the raw inputs of
City A).

| # | change | why | v1.0.0 behaviour | here |
|---|---|---|---|---|
| 1 | **Analysis CRS per area** (`crs: per_area`, or `crs` inside each area) | Cities on different continents cannot share one projected CRS. v1.0.0 uses one CRS for all areas (configured, or the UTM zone of their union), which distorts lengths and areas far from that zone. | one CRS per run | each city in its own CRS, only descriptor tables pooled (`pipeline.py`) |
| 2 | **K range per model** (`parameters.k_range_pooled`) | The thirteen-city pooled model uses K 5–25, while its city models use 5–15. | `Params.k_range` applies to local and pooled models alike | `ModelSettings.k_range_city` / `k_range_pooled` (`config.py`) |
| 3 | **Building filters per area** (`min_building_area_m2`, `max_height_m` inside an area) | 10 m² footprint floor in informal fabric; 550 m height ceiling in Manhattan | run-wide `Params` | per-city `Params` copy (`CityConfig.params`) |
| 4 | **Non-building classes for file inputs** | Overture footprints carry `class`/`subtype`; the study drops the same classes as for OSM | `OSM_DROP_TYPES` applied only to OSM downloads | `buildings.standardise_tags` |
| 5 | **Height sources** | (a) a footprint file with a height column in feet, tallest part wins; (b) a height raster (Open Buildings 2.5D: footprint mean of positive pixels, else 5×5 max); (c) several 3D-GloBFP tiles read together and joined once (v1.0.0 fills tile by tile, which can differ where a building matches polygons of two tiles); (d) automatic selection of one source per city on a 500-building sample, with the decision recorded | polygon layers only, filled in sequence | `heights.py` |
| 6 | **Sampling-unit refinement** (`units: refinement`) | thirteen-city: tier-1 all-roads rule, built-envelope trimming, mega-block tiers 2–3, `block_kind`, `block_trim` | plain street-enclosure blocks | `refine.py`, `pipeline.prepare_city` |
| 7 | **Partition-unit neutralisation** in `block_descriptors` (when `block_kind` is present) | The analytic boundaries of tier-3 units must not drive the type | not available | `descriptors.neutralise_partition_units` |
| 8 | **Public file reader** | This package imports the private `blockmorph.inputs._file_buildings`. Pinning v1.0.0 keeps that safe, but it should become public. | private | `buildings.load_file` |
| 9 | **Model fit from a descriptor table** without building statistics | Fitting on published descriptor tables (reproduction, examples) | `fit_model` requires block statistics for profiles | `pipeline.fit_descriptors` |
| 10 | **Optional null-silhouette baseline** in `select_k` | The Gaussian-null silhouette (3 extra K-means + silhouettes per K) dominates the run time of the 42,470-unit thirteen-city pooled model (about 20 minutes). It does not affect K. A switch would speed up reproduction checks. | always computed | not changed (computed, as in the study) |
| 11 | **Dashboard with per-area CRS** | `blockmorph dashboard` assumes one CRS for all areas | single CRS | not provided here; outputs keep the core layout so a v1.1.0 dashboard can read them |
| 12 | **Overture road segments as a street source** | Fallback the study used for Tokyo when no Overpass instance answered | OSM download or file | `acquire.fetch_overture_streets` writes a file read by the core |
