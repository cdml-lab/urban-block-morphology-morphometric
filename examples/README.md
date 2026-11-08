# Example

A tiny, fast run on derived numbers only: 400 Manhattan blocks of the
three-city set (`data/three_cities_sample_MAN_descriptors.csv`). The file holds the 46
descriptors and no geometry. The blocks are a random sample (seed 0) of the
3,258 Manhattan blocks.

```bash
blockmorph-morphometric fit three_cities examples/data/three_cities_sample_MAN_descriptors.csv --out examples/example_output
```

Output (`examples/example_output/`):

| file | content |
|---|---|
| `models/MAN/k_selection.csv` | K sweep 5–15 with silhouette (and its Gaussian-null gap), Calinski–Harabasz, Davies–Bouldin, inertia, smallest type, conditions, `selected` |
| `models/MAN/report.json` | K, rule or fallback with the reason, elbow, admissible K, PCA variance, quality, type order, draft names |
| `assignments.csv` | `block_key`, `area`, `city_type` |
| `run.json` | versions, set settings, descriptor list |

Result of the verification run (`requirements-lock.txt` versions): **K = 8,
rule** (elbow 8; admissible K 8 and 9). This is a sample, so the result is
not the study's Manhattan model (K = 8 on all 3,258 blocks). It only shows
the procedure.

With several cities in the table (column `area`, ids as in
`configs/sets/three_cities.yaml`), `fit` also fits the pooled model in the set's
city order.
