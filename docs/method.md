# Method (three-city and thirteen-city sets, Track A)

Track A of the international sets is the core's morphometric-only model:
the 46 morphometric and contextual descriptors with no building-typology
shares. It is the core's `descriptors: morphometric46` model, and it is not
the core's 57-descriptor manuscript model. Every step that is not listed as
**added here** is the core v1.0.0 code (`blockmorph`), called unchanged.

## 1. Inputs per city (added here)

| step | rule |
|---|---|
| analysis CRS | one projected CRS **per city** (UTM zone of the city; EPSG:2039 for City A). Descriptors are computed in that CRS. Only the descriptor tables are pooled. |
| study area | city boundary ∩ extent of the study's imagery (`study_area.clip_bbox`) |
| buildings | OSM (osmnx), Overture Maps (release 2026-08-19.0, all conflated sources or the OSM polygons only) or a file. See `buildings.py` and `docs/sets.md`. |
| non-buildings | OSM/Overture classes roof, carport, shed, garage(s), greenhouse, hut, tent, ruins and construction dropped |
| footprint floor | 25 m², or **10 m²** in the informal-fabric cities (Rio, São Paulo, Nairobi, Cairo, Lagos, Mumbai). At 25 m², 39 % of a favela's buildings would be dropped (Rocinha, median footprint 30 m²). |
| height ceiling | 260 m, or 550 m in Manhattan. Heights below 2 m or above the ceiling are discarded. |
| cleaning | make valid → largest part → polygons only → footprint floor → stacked duplicates merged (tallest part wins) |
| heights | source height > **one** enrichment source per city > floors × 3.2 m. Floors = round(height / 3.2) where unknown. |
| height enrichment | `file` (NYC roof height, ft → m, tallest part), `globfp` (3D-GloBFP tiles read together, joined by representative point), `ob25d` (Open Buildings 2.5D, 2023: mean of the positive 2-m pixels in the footprint, else the 5×5 maximum at the representative point). `auto` picks the source by the rule below. |
| automatic height source | Each available candidate is tried **on its own** on 500 randomly drawn buildings (seed 42). The highest-ranked candidate covering ≥ 70 % of the sample wins (rank: file > OSM tags > 3D-GloBFP > Open Buildings 2.5D). Otherwise the best-covering candidate wins. The decision is written to `areas/<id>/heights.json`. |
| restriction | buildings whose representative point lies outside the study area are dropped |
| streets | OSM ways (`graph_from_polygon(network_type="all", retain_all=True, truncate_by_edge=True)`). The default cutting classes are the core's. Every mapped way cuts blocks in Nairobi (`cut_all_roads`), as in the core's City C rule. |

## 2. Blocks and sampling units

Blocks come from the core: `momepy.enclosures` clipped to the study area.
An enclosure is a block when its GSI is ≥ 0.03, its area is ≥ 1,500 m² and it
holds a building. The enclosed tessellation is also the core's.

**The three-city set** keeps these plain street-enclosure blocks.

**Thirteen-city set: sampling-unit refinement (added here, `refine.py`).** A block
is one observation of fabric. In some cities the mapped network leaves
thousands of buildings in one enclosure (informal settlements, untagged
lanes). Such a unit is not comparable with an ordinary street block, so the
following steps are applied in the study's order:

1. **Tier 1, all roads cut.** A mega-block is larger than 8 ha and holds
   more than 150 buildings. If the default cutting classes leave more than
   20 % of the in-block buildings in mega-blocks, every mapped way cuts
   blocks, and the blocks are rebuilt.
2. The enclosed tessellation is computed on the final enclosures.
3. **Built-envelope trimming.** The envelope is the buildings buffered by
   30 m (mitre joins), holes filled. A block whose envelope covers less than
   50 % of it is cut down to the envelope. The remainder becomes open
   context. `block_trim` records the share of area kept.
4. **Tiers 2 and 3 on every mega-block.** Two kinds are exempt:
   - open land with scattered structures (GSI < 0.15);
   - big-shed estates (median footprint ≥ 300 m²).

   The others are split:
   - **Tier 2, alley patches.** Buildings are buffered by d and unioned,
     for d = 3, 2, 1.5, 1 m. The first d that leaves no patch above 150
     buildings is used, and d = 1 m if none does. Patches with fewer than 3
     buildings merge into the nearest larger patch.
   - **Tier 3, partitions.** A patch still above 150 buildings is
     partitioned by k-means on building centroids (`n_init` 4, seed 42).
     Chunks are re-split until none exceeds 150 buildings (at most 8
     rounds).

   A sub-unit's polygon is the union of its buildings' tessellation cells,
   clipped to the parent block. Untouched blocks keep their order, sub-units
   are appended, and ids are renumbered. `block_kind` is `street`, `patch`
   or `partition`.

## 3. Descriptors

The **missing-data treatment** is the core's (`blockmorph.missing`). A
building without a height takes the median known height of its own block,
else the median of its 10 nearest buildings with a known height. Floor area
and volume are then recomputed.

The **46 descriptors** are the core's `block_descriptors` with
`typology=None`, in the core's column order (`MORPHO_COLUMNS`). Building
characters use momepy 1.0 with libpysal graphs: fuzzy contiguity at 0.25 m,
5 nearest neighbours, nearest street within 120 m. Context is the mean over
blocks contiguous within 25 m.

**Partition-unit neutralisation (added here, thirteen-city set).** Tier-3 units have
analytic boundaries. For these units, 13 descriptors are set to missing:
the descriptors that measure the unit itself (`blk_area`, `blk_perimeter`,
`blk_compactness`, `blk_eri`, `blk_orientation`, `n_buildings`,
`volume_sum`, `edge_building_share`, `dist_to_edge_norm_mean`) and the 4
`road_*` street-interface descriptors. The preprocessing imputes them with
the median. The intensive fabric descriptors and the context lag are kept,
and the context lag is computed before the neutralisation.

## 4. Models

The procedure is the core's (`blockmorph.model.pca_space` and `select_k`):
- **preprocessing**, per column: median imputation; log1p for non-negative
  columns with |skew| > 1.5; winsorising at 0.5 / 99.5 %; standardisation;
  equal weights;
- **PCA**: whitened, **5 components** (seed 42);
- **K-means**: `n_init` 10, seed 42, over the K range;
- **K rule**: a K is admissible when every type holds ≥ 12 blocks and K is
  at or above the inertia elbow (kneed). Among admissible K, the best
  combined score wins (mean of the min–max-normalised silhouette and
  Calinski–Harabasz scores and the inverted Davies–Bouldin score). A
  fallback is reported as such.

The **K range** is 5–15 for every city model and for the three-city pooled
model. It is **5–25 for the thirteen-city pooled model** (added here as a
per-model setting). Thirteen cities and ~42,000 units make the three-city
ceiling of 15 too low.

The **city models** are fitted on each city's own blocks. The **pooled
model** is fitted on all blocks of the set. Cities are stacked in the
set's order (three-city: A, MAN, AMS; thirteen-city: A, MAN, AMS, MTL, BCN, RIO,
SAO, NBO, CAI, LOS, BOM, TYO, SYD), with blocks in `block_id` order. Row
order changes the K-means initialisation, so keep it for exact
reproduction.

The PCA dimensionality and the K ranges were fixed by the decision record
summarised in `docs/configuration.md`.

## 5. Outside this repository

- Tracks B (self-supervised imagery embeddings) and C (united model).
- Construction years, land use, prices and every external validation.
- Imagery: Track A does not use it.
