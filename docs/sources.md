# Data sources and licences

This repository ships **no input data**. Inputs are downloaded by
`blockmorph-morphometric fetch ...` or supplied by the user. City A's inputs come
from the core's results archive. The only data file in the repository is
the example sample described at the end.

| content | used for | source | licence / terms |
|---|---|---|---|
| building footprints, OSM | MAN, AMS (osmnx download); City A (core archive) | © OpenStreetMap contributors | ODbL 1.0, attribution and share-alike for derived databases |
| building footprints, Overture Maps | MTL, BCN, TYO (OSM rows only); RIO, SAO, NBO, CAI, LOS, BOM, SYD (conflated) | Overture Maps Foundation, buildings theme, release **2026-08-19.0** (S3 GeoParquet via DuckDB) | ODbL 1.0 for the theme. Its components keep their own terms: OpenStreetMap (ODbL 1.0), Google Open Buildings (CC BY 4.0 / ODbL 1.0), Microsoft building footprints (ODbL 1.0). Attribute "© OpenStreetMap contributors, Overture Maps Foundation" and the conflated sources. |
| streets | every city | © OpenStreetMap contributors (osmnx, Overpass). Tokyo's study network is the same OSM ways served as Overture transportation segments (the Overture release current on 2026-09-14), fetched when no Overpass instance answered. | ODbL 1.0 |
| per-building heights, 3D-GloBFP | City A (in the archive's heights), and 9 thirteen-city cities by automatic selection | Che et al. (2024), 3D-GloBFP: the first global three-dimensional building footprint dataset, *Earth System Science Data*; Zenodo record 11319912 (grid) and figshare (tiles) | CC BY 4.0 |
| building heights, Open Buildings 2.5D Temporal (2023, `building_height`) | Rio de Janeiro (selected); candidate in SAO, NBO, CAI, LOS, BOM | Google Research, Open Buildings 2.5D Temporal dataset (storage.googleapis.com/open-buildings-temporal-data) | CC BY 4.0 and ODbL 1.0, per the dataset page; check the current terms |
| roof heights, Manhattan | MAN (`height_roof`, ft) | NYC Open Data, Building Footprints (data.cityofnewyork.us, 5zhs-2jue) | NYC Open Data terms of use (free use; attribution requested) |
| boundary, Manhattan | MAN | NYC Department of City Planning, borough boundaries (NYC Open Data / ArcGIS FeatureServer) | NYC Open Data terms of use |
| boundary, Amsterdam | AMS | City of Amsterdam, `gebieden/stadsdelen` API (api.data.amsterdam.nl) | City of Amsterdam open data terms (see the portal) |
| boundaries, OSM relations / Nominatim | MTL, BCN, RIO, SAO, NBO, LOS, BOM, TYO, SYD | © OpenStreetMap contributors, Nominatim lookup (osmnx `geocode_to_gdf`) | ODbL 1.0. Follow the Nominatim usage policy. |
| boundary units, GADM 4.1 | CAI (level-2 units); land clip of the 10 thirteen-city-only cities (level 0) | GADM 4.1 (gadm.org) | Free for academic and other non-commercial use. **Redistribution and commercial use are not allowed without permission**, so GADM-derived boundaries are rebuilt locally and never distributed. |
| City A inputs | A | core results archive v1.0.0, `inputs/A/` (buildings with heights, streets) | as stated in that archive (OSM ODbL 1.0; 3D-GloBFP CC BY 4.0). The study-area polygon is available on request. |
| imagery extent | study-area clip (`clip_bbox`) | extents of the study's aerial imagery: Esri World Imagery (thirteen-city-only cities), NYS orthoimagery (MAN), PDOK Luchtfoto (AMS); for City A, see the core | Only four coordinates per city are used. **No imagery is used by Track A or distributed.** |

Not used or distributed here: construction years, land use, prices, the
Track B/C embeddings, the R-CNN building-form predictions and every
external validation layer.

## Example data (`examples/data/`)

`three_cities_sample_MAN_descriptors.csv` holds 400 Manhattan blocks of the
three-city set: the 46 block descriptors only, with no geometry. These numbers
are derived from OpenStreetMap buildings and streets (© OpenStreetMap
contributors, ODbL 1.0) and NYC Open Data roof heights. As a derived
database of OpenStreetMap it is made available under ODbL 1.0.

## Reproducibility of the downloads

OSM, Overture and the online height services change over time. Overture
keeps only recent releases online, and the pinned release 2026-08-19.0 will
eventually be removed. A new download is therefore not byte-identical to
the study's inputs. The exact reproduction (`docs/reproduction.md`) is
defined on the study's descriptor tables and cached inputs.
