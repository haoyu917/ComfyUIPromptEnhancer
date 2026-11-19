# Granular rough set three-way decision for skill selection

Offline analysis code, not loaded by the ComfyUI node. It implements the three-step framework of

> J. Luo, M. Hu, C. Shi, Y. Yao. *Three-way decision with granular rough sets.* Applied Soft Computing 180 (2025) 113344.

and applies it to the plugin's research run logs: does a given request plus module (skill) configuration produce an acceptable raw model response?

## Files

- `granular_3wd.py`: the framework, in pure Python with no dependencies.
  - Information tables with categorical, set-valued, and numeric attributes.
  - Value-oriented relations: indiscernibility, Orłowska's forward inclusion, backward inclusion, and similarity (Table 1), and the distance relation R^θ (Eq. 3).
  - Granular spaces: quotient, neighborhood-induced (successor, predecessor, both, or either), and maximal-clique-induced (Bron–Kerbosch with pivoting).
  - Granule descriptions (Def 4) and α/β regions (Def 5).
  - Accept/reject/non-commitment rules (Def 7) and the GRS3WDC classifier (Algorithm 1).
- `dataset.py`: turns run records into an information table. It uses 21 module-state attributes and 17 request attributes. Two of the request attributes are set-valued: the benchmark `tags` and the `filled_guidance` fields. The decision class X is the set of runs labelled `acceptable` by `quality_metrics.py`.
- `evaluate.py`: cross-validation grouped by prompt, comparing 3WD-Q, 3WD-N, and 3WD-MC against the paper's baselines (linear SVM, Gini decision tree, 5-NN, Gaussian naive Bayes) and a majority-class baseline.

## Faithfulness to the paper

Granule descriptions are sets of tuples in the Cartesian product TP_A, which is too large to enumerate. They are therefore tested intensionally: y ⊨ GDes(G) exactly when Des(y) is related to the description of every descriptor object of G. That is the same membership test as Def 4 and Def 6.

`tests/test_granular_3wd.py` reproduces the paper's worked examples in Section 4 from Table 2. It checks:

- the backward-inclusion and similarity neighborhoods, and their regions;
- the decisions for the test objects in Tables 3 and 4;
- the maximal cliques under indiscernibility, forward inclusion (identical to indiscernibility, as the paper states), and similarity;
- the clique regions, and the decisions for Tables 5 and 6.

Regions are computed exactly as Definition 13 states: a granule with Pr(X | G) ≥ α is positive, one with Pr(X | G) ≤ β is negative, and the rest are boundary. The region tests assert the regions that this rule produces for each example.

## Distance for mixed attributes

The paper's experiments use Euclidean distance on numeric data (Eq. 31). Run records mix attribute types, so `tuple_distance` instead takes a weighted mean of per-attribute distances in [0, 1]:

- 0 or 1 for categorical values;
- Jaccard distance for set-valued attributes;
- absolute difference divided by the observed range for numeric values.

The distance is 0 only for identical tuples, so θ = 0 yields the quotient space.

By default the module group and the request group each carry half the total weight. A single module switched on or off therefore moves the distance by only 1/42 ≈ 0.024. The θ values that distinguish individual skills are on that scale, while larger θ values mainly bridge differences between requests. `--module-weight` and `--request-weight` change the split.

## Usage

```bash
python -m research.evaluate --log research_logs/runs.jsonl --out-dir research_reports/pilot1
```

Synthetic `--dry-run` records are excluded unless `--allow-synthetic` is given; a report built from them is labelled "SYNTHETIC DATA" and is for pipeline testing only. The baselines need `pip install -r research/requirements.txt`.

## Early observation (pipeline behaviour, not a result)

Grouped cross-validation means that every test request is new. On simulated data, coverage (the fraction of committed decisions) is low and does not rise steadily with θ. Larger neighborhoods mix acceptable and unacceptable runs, so a new request often satisfies descriptions from both the positive and the negative region, and Definition 7 then defers. This is the high non-commitment rate that the paper names as its main limitation, and it shows up directly here. Decision rules that resolve such conflicts while keeping three-way semantics are a candidate research contribution; they need to be tested on real data.
