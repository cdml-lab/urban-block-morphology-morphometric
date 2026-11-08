# Configuration: clustering space and K

## Settings

| setting | three-city | thirteen-city | where |
|---|---|---|---|
| descriptors | 46 morphometric (`morphometric46`) | same | core `MORPHO_COLUMNS` |
| missing data | core treatment (heights imputed; NaN → median in preprocessing) | same | core `missing.py`, `model.prepare_matrix` |
| partition-unit neutralisation | not applicable (no partitions) | 13 unit-dependent descriptors → missing | `descriptors.py` |
| PCA | whitened, 5 components, seed 42 | same | `model.pca_components`, `pca_whiten` |
| K-means | `n_init` 10, seed 42 | same | `model.kmeans_n_init`, `random_state` |
| K range, city models | 5–15 | 5–15 | `model.k_range_city` |
| K range, pooled model | 5–15 | **5–25** | `model.k_range_pooled` |
| minimum type size | 12 blocks | 12 blocks | `model.min_type_size` |
| K rule | size condition + inertia-elbow floor + best combined score | same | core `select_k` |
| pooling order | A, MAN, AMS | A, MAN, AMS, MTL, BCN, RIO, SAO, NBO, CAI, LOS, BOM, TYO, SYD | `cities:` |

These are the values in `configs/sets/*.yaml`. Changing any of them gives a
different model from the study's.

## Why 5–25 for the thirteen-city pooled model

The thirteen-city pooled model types about 42,000 units from 13 cities on six
continents. A ceiling of 15 was set for three-city pooling and is too low
for this space. Inside 5–25, the rule chose K = 12:
- the inertia elbow is at 12;
- the smallest type at K = 12 holds 1,598 units;
- K = 12 has the best combined score among the admissible K (12–25).

Every city model keeps 5–15.

## PCA dimensionality: pre-registered decision rule

The rule was fixed on 22 October 2026. There is one decision per model and
set, taken on the set's pooled model. The city models of a set use the same
dimensionality, and their K is chosen by the K rule.

- **Candidates:** whitened PCA with d ∈ {2, 5, 8} components.
- **Exclusion:**
  - **E1, data-gap type:** Cramér's V between type and "block without any
    measured height" exceeds that of PCA(2) by more than 0.10;
  - **E2:** no admissible K.
- **Improvement over PCA(2):** a candidate d > 2 qualifies if all of these
  hold:
  - **C1:** its gap above the matched Gaussian null exceeds PCA(2)'s by at
    least 0.02;
  - **C2:** its subsample stability (median pairwise ARI) is not lower by
    more than 0.05;
  - **C3:** the share of subsamples in which the K rule repeats its K is
    not lower by more than 0.10.
- **Choice:** the smallest qualifying d. If none qualifies, d = 2.
- No external variable enters the rule.

### Track A decisions (from the study's decision record)

| set | d | K | C1 gap Δ vs PCA(2) | C2 stability (d vs 2) | C3 K repeat (d vs 2) | E1 V (d vs 2) | qualifies |
|---|---|---|---|---|---|---|---|
| three-city | **5** | **8** | +0.053 | 0.87 vs 0.88 | 85 % vs 31 % | 0.22 vs 0.19 | **yes, chosen** |
| three-city | 8 | 8 | +0.062 | 0.92 vs 0.88 | 54 % vs 31 % | 0.23 vs 0.19 | yes |
| thirteen-city | **5** | **12** | +0.053 | 0.91 vs 0.81 | 98 % vs 53 % (100 subsamples) | 0.22 vs 0.17 | **yes, chosen** |
| thirteen-city | 8 | 12 | +0.061 | 0.95 vs 0.81 | 100 % vs 60 % | 0.21 vs 0.17 | yes |

So d = 5 in both sets, the smallest qualifying candidate. The pooled K
values are 8 (three-city) and 12 (thirteen-city). Both are reproduced exactly by
`scripts/check_reproduction.py`, which also reads the K of the decision
record and requires agreement.

## Subsample stability

`stability_reps` (default 20) only adds a stability report to
`report.json` in a full run. It never changes K or the labels.
