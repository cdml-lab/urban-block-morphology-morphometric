# The three-city and thirteen-city sets

| set | cities (pooling order) | units | blocks | pooled K |
|---|---|---|---|---|
| three-city | A, MAN, AMS | street-enclosure blocks | 7,556 | 8 (K range 5–15) |
| thirteen-city | A, MAN, AMS, MTL, BCN, RIO, SAO, NBO, CAI, LOS, BOM, TYO, SYD | refined sampling units | 42,470 | 12 (K range 5–25) |

The two sets are independent analyses. A city that belongs to both
(A, MAN, AMS) is analysed separately in each. Its thirteen-city units carry
the trimming and mega-block refinement, so its thirteen-city descriptors and
labels differ from its three-city ones.

**City A** is the study's Israeli reference city. It is anonymised as in
the core repository: id `A`, block keys `A-<block_id>`, analysis CRS
EPSG:2039. Its inputs are the core's results archive v1.0.0 (`inputs/A/`:
buildings with heights, streets). The study-area polygon is available on
request. The three-city descriptors of City A are identical to the core's City A
morphometric 46 (largest difference 3.5e-16 of a column's range).

Configurations: `configs/sets/{three_cities,thirteen_cities}.yaml` and
`configs/cities/<id>.yaml`. Inputs of a run are read from
`<data_dir>/<id>/` (`blockmorph-morphometric fetch ...`, `docs/sources.md`).

## Cities

| id | name | CRS | buildings | footprint floor | heights (study choice) | streets cutting blocks | boundary |
|---|---|---|---|---|---|---|---|
| A | City A (Israeli reference city) | EPSG:2039 | core archive (OSM) | 25 m² | in the file: OSM tag, else 3D-GloBFP | default classes | core archive study area (on request) |
| MAN | Manhattan (New York) | EPSG:32618 | OSM | 25 m² (ceiling 550 m) | NYC Open Data roof height (`file`) | default classes | NYC DCP borough 1, largest polygon |
| AMS | Amsterdam (centre) | EPSG:32631 | OSM | 25 m² | OSM tags only | default classes | districts Centrum, West, Zuid, Oost, largest polygon |
| MTL | Montreal (Plateau · Ville-Marie · Rosemont · Sud-Ouest) | EPSG:32618 | Overture, OSM polygons | 25 m² | auto → 3D-GloBFP | default classes | 4 OSM relations |
| BCN | Barcelona (Eixample · Ciutat Vella · Sant Martí · Sants) | EPSG:32631 | Overture, OSM polygons | 25 m² | auto → 3D-GloBFP | default classes | 4 OSM relations |
| RIO | Rio de Janeiro (Zona Sul) | EPSG:32723 | Overture, conflated | 10 m² | auto → Open Buildings 2.5D | default classes; tier 1: all ways | 10 OSM relations |
| SAO | São Paulo (Morumbi · Vila Andrade · Butantã · Campo Limpo) | EPSG:32723 | Overture, conflated | 10 m² | auto → 3D-GloBFP | default classes | 4 OSM relations |
| NBO | Nairobi (Kibra · Dagoretti North · Starehe) | EPSG:32737 | Overture, conflated | 10 m² | auto → 3D-GloBFP | **all mapped ways** (`cut_all_roads`) | 3 OSM relations |
| CAI | Cairo (historic core · Khedival city · Manshiyat Naser) | EPSG:32636 | Overture, conflated | 10 m² | auto → 3D-GloBFP | default classes | 16 GADM 4.1 level-2 units |
| LOS | Lagos (Lagos Island · Lagos Mainland · Surulere) | EPSG:32631 | Overture, conflated | 10 m² | auto → 3D-GloBFP | default classes; tier 1: all ways | 2 OSM relations + 1 Nominatim query |
| BOM | Mumbai (wards G/North · H/East · H/West · F/North) | EPSG:32643 | Overture, conflated | 10 m² | auto → 3D-GloBFP | default classes; tier 1: all ways | 4 OSM relations |
| TYO | Tokyo (Shinjuku · Shibuya · Toshima · Nakano) | EPSG:32654 | Overture, OSM polygons | 25 m² | auto → 3D-GloBFP | default classes; tier 1: all ways (OSM ways served as Overture segments) | 4 OSM relations |
| SYD | Sydney (City of Sydney · Randwick) | EPSG:32756 | Overture, conflated (OSM + Microsoft) | 25 m² | auto → 3D-GloBFP | default classes | 2 OSM relations |

- "Overture, conflated": Google Open Buildings + OSM + Microsoft
  footprints. "OSM polygons": Overture rows whose source is OpenStreetMap.
  Overpass timed out on 60-km² cities, and Overture serves the same OSM
  polygons.
- The boundaries of the ten thirteen-city-only cities are unions of real
  administrative units, never boxes. They are closed by 20 m, clipped to
  the country's GADM land polygon, and only parts ≥ 0.25 km² within 2 km
  of the largest part are kept.
- The default cutting classes are those of the core: motorway, trunk,
  primary, secondary, tertiary (and links), residential, living_street,
  pedestrian and footway.
- **Nairobi** cuts with every mapped way: OSM tags its ordinary streets
  (Kibera's lanes, estate roads) as `service`, 35 % of the network length
  against 9–16 % elsewhere. This is the same per-city rule as the core's
  City C.

### Automatic height source (sample coverage of each candidate on its own)

| city | OSM tags | 3D-GloBFP | Open Buildings 2.5D | chosen |
|---|---|---|---|---|
| MTL | 0.176 | 0.912 | – | 3D-GloBFP |
| BCN | 0.194 | 0.964 | – | 3D-GloBFP |
| RIO | 0.398 | 0.688 | 0.960 | Open Buildings 2.5D |
| SAO | 0.310 | 0.886 | 0.958 | 3D-GloBFP |
| NBO | 0.000 | 0.798 | 0.836 | 3D-GloBFP |
| CAI | 0.004 | 0.856 | 0.820 | 3D-GloBFP |
| LOS | 0.002 | 0.856 | 0.800 | 3D-GloBFP |
| BOM | 0.000 | 0.806 | 0.878 | 3D-GloBFP |
| TYO | 0.144 | 0.758 | – | 3D-GloBFP |
| SYD | 0.058 | 0.960 | – | 3D-GloBFP |

"–" means no Open Buildings 2.5D tile exists for the city (coverage is
the Global South). The rank is file > OSM tags > 3D-GloBFP > Open Buildings
2.5D, and the first source with ≥ 70 % coverage wins.

## Units and models per city

| id | three-city blocks | three-city K | thirteen-city units | street / patch / partition | tier 1 | trimmed | mega-blocks split | thirteen-city K |
|---|---|---|---|---|---|---|---|---|
| A | 1,590 | 9 | 1,609 | 1,589 / 20 / 0 | no | 21 | 1 | 9 |
| MAN | 3,258 | 8 | 3,258 | 3,258 / 0 / 0 | no | 45 | 0 | 8 |
| AMS | 2,708 | 11 | 2,858 | 2,698 / 160 / 0 | no | 55 | 10 | 11 |
| MTL | – | – | 2,329 | 2,329 / 0 / 0 | no | 51 | 0 | 8 |
| BCN | – | – | 2,271 | 2,224 / 47 / 0 | no | 45 | 1 | 9 |
| RIO | – | – | 1,412 | 659 / 733 / 20 | yes | 17 | 13 | 8 |
| SAO | – | – | 2,185 | 1,628 / 531 / 26 | no | 16 | 36 | 8 |
| NBO | – | – | 3,597 | 1,375 / 2,213 / 9 | all roads already | 11 | 86 | 9 |
| CAI | – | – | 4,821 | 4,320 / 499 / 2 | no | 18 | 15 | 11 |
| LOS | – | – | 4,062 | 1,450 / 2,546 / 66 | yes | 10 | 61 | 8 |
| BOM | – | – | 2,534 | 1,707 / 670 / 157 | yes | 25 | 46 | 9 |
| TYO | – | – | 9,460 | 9,450 / 10 / 0 | yes | 33 | 2 | 8 |
| SYD | – | – | 2,074 | 2,033 / 41 / 0 | no | 34 | 2 | 8 |
| **total** | **7,556** | pooled **8** | **42,470** | | | | | pooled **12** |

Every city model and both pooled models meet the K rule (status `rule`;
none is a fallback).
