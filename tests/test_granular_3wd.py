"""Reproduce the worked examples of Luo, Hu, Shi & Yao (2025), Section 4.

Every expected value below is copied from the paper: Table 2 (the set-valued
information table ST), the listed neighborhoods and maximal cliques, the
regions for X = {x2, x3, x4, x5, x10} with alpha = 1 and beta = 0, and the
decisions for the test objects of Tables 3, 5 and 6.
"""

import pytest

from research.granular_3wd import (
    ACCEPT,
    DEFER,
    REJECT,
    Attribute,
    DistanceRelation,
    GranularThreeWayClassifier,
    Indiscernibility,
    InformationTable,
    OrlowskaRelation,
    clique_space,
    granular_regions,
    maximal_cliques,
    neighborhood_space,
    quotient_space,
    relation_matrix,
    tuple_distance,
)

ATTRS = [Attribute(f"a{i}", kind="set") for i in range(1, 5)]

# Table 2: set-valued information table ST.
ST = {
    "x1": ({1, 2}, {2}, {3}, {2}),
    "x2": ({3}, {0}, {1}, {0}),
    "x3": ({0, 3}, {0, 2}, {1}, {0}),
    "x4": ({0, 3}, {0, 2}, {1}, {0}),
    "x5": ({1}, {1}, {1}, {2}),
    "x6": ({0, 1, 2, 3}, {1}, {1}, {0, 3}),
    "x7": ({0, 1, 2, 3}, {1}, {1}, {0, 3}),
    "x8": ({0, 1, 2, 3}, {1, 2}, {1, 3}, {0, 1}),
    "x9": ({0, 1, 2, 3}, {1, 2}, {1, 3}, {0, 1}),
    "x10": ({0, 1, 4}, {0, 1}, {1, 2}, {0, 2}),
    "x11": ({0, 1, 4}, {0, 1}, {1, 2}, {0, 2}),
    "x12": ({2, 3, 4}, {0, 2}, {0, 3}, {1, 2}),
}
X = {"x2", "x3", "x4", "x5", "x10"}

# Tables 3, 4, 5, 6: test objects.
Y = {
    "y1": ({0, 3}, {0}, {1}, {0}),
    "y2": ({0, 1, 2, 3}, {1, 2}, {3}, {1}),
    "y3": ({0, 1, 2, 3}, {1, 2}, {1, 3}, {0, 2, 3}),
    "y4": ({0, 2, 3}, {0, 2}, {1}, {0}),
    "y5": ({1, 2, 3, 4}, {1, 2}, {0, 3}, {1, 2}),
    "y6": ({1, 2, 3}, {0, 2}, {1, 3}, {0, 1}),
    "y7": ({3}, {0}, {1}, {0}),
    "y8": ({0, 1, 2, 3}, {1}, {1}, {0, 3}),
    "y9": ({0, 1, 4}, {0, 1}, {1, 2}, {0, 2}),
    "y10": ({3}, {0}, {0, 1}, {0}),
    "y11": ({2, 3, 4}, {2}, {1, 3}, {1}),
    "y12": ({2, 3}, {0, 2}, {1, 3}, {0, 1}),
}


def _row(values):
    return {f"a{i}": value for i, value in enumerate(values, start=1)}


@pytest.fixture(scope="module")
def table():
    ids = list(ST)
    return InformationTable(ATTRS, [_row(ST[i]) for i in ids], labels=[i in X for i in ids], ids=ids)


def _sets(table, granules):
    return {frozenset(table.ids[m] for m in g.members) for g in granules}


def _names(table, granules):
    return {table.ids[g.origin] for g in granules}


def _y(table, name):
    return table.describe(_row(Y[name]))


# ---- Section 4.2: neighborhood-induced granular spaces -------------------------


def test_backward_inclusion_successor_neighborhoods_match_paper(table):
    granules = neighborhood_space(table, OrlowskaRelation(ATTRS, "backward"), "s")
    got = {table.ids[g.origin]: {table.ids[m] for m in g.members} for g in granules}
    assert got == {
        "x1": {"x1"},
        "x2": {"x2"},
        "x3": {"x2", "x3", "x4"},
        "x4": {"x2", "x3", "x4"},
        "x5": {"x5"},
        "x6": {"x6", "x7"},
        "x7": {"x6", "x7"},
        "x8": {"x8", "x9"},
        "x9": {"x8", "x9"},
        "x10": {"x5", "x10", "x11"},
        "x11": {"x5", "x10", "x11"},
        "x12": {"x12"},
    }


def test_backward_inclusion_regions_match_paper(table):
    clf = GranularThreeWayClassifier("neighborhood", OrlowskaRelation(ATTRS, "backward"), alpha=1.0, beta=0.0).fit(table)
    positive = _sets(table, [g for g, _ in clf.regions.positive])
    negative = _sets(table, [g for g, _ in clf.regions.negative])
    boundary = _sets(table, [g for g, _ in clf.regions.boundary])
    assert positive == {frozenset({"x2"}), frozenset({"x2", "x3", "x4"}), frozenset({"x5"})}
    assert negative == {frozenset({"x1"}), frozenset({"x6", "x7"}), frozenset({"x8", "x9"}), frozenset({"x12"})}
    assert boundary == {frozenset({"x5", "x10", "x11"})}


def test_backward_inclusion_decisions_for_table_3_match_paper(table):
    clf = GranularThreeWayClassifier("neighborhood", OrlowskaRelation(ATTRS, "backward"), alpha=1.0, beta=0.0).fit(table)
    accept = clf.decide(_y(table, "y1"))
    assert accept.outcome == ACCEPT
    # The paper's reason: y1 satisfies GDes(BR(x3)).
    assert "x3" in _names(table, accept.positive)
    reject = clf.decide(_y(table, "y2"))
    assert reject.outcome == REJECT
    assert "x8" in _names(table, reject.negative)
    assert clf.decide(_y(table, "y3")).outcome == DEFER


def test_similarity_decisions_for_table_4_match_paper(table):
    # Table 4 follows the similarity-relation regions in Section 4.2.
    clf = GranularThreeWayClassifier("neighborhood", OrlowskaRelation(ATTRS, "similarity"), alpha=1.0, beta=0.0).fit(table)
    assert clf.decide(_y(table, "y4")).outcome == ACCEPT
    assert clf.decide(_y(table, "y5")).outcome == REJECT
    y6 = clf.decide(_y(table, "y6"))
    # Paper: y6 satisfies a positive-region description and that of SR(x12).
    assert y6.outcome == DEFER
    assert y6.positive and "x12" in _names(table, y6.negative)


def test_similarity_successor_neighborhoods_match_paper(table):
    granules = neighborhood_space(table, OrlowskaRelation(ATTRS, "similarity"), "s")
    got = {table.ids[g.origin]: {table.ids[m] for m in g.members} for g in granules}
    assert got["x1"] == {"x1", "x12"}
    assert got["x2"] == {"x2", "x3", "x4"}
    assert got["x3"] == {"x2", "x3", "x4", "x8", "x9", "x10", "x11"}
    assert got["x5"] == {"x5", "x10", "x11"}
    assert got["x6"] == {"x6", "x7", "x8", "x9", "x10", "x11"}
    assert got["x8"] == {"x3", "x4", "x6", "x7", "x8", "x9", "x10", "x11", "x12"}
    assert got["x10"] == {"x3", "x4", "x5", "x6", "x7", "x8", "x9", "x10", "x11"}
    assert got["x12"] == {"x1", "x8", "x9", "x12"}


def test_similarity_regions_match_paper(table):
    clf = GranularThreeWayClassifier("neighborhood", OrlowskaRelation(ATTRS, "similarity"), alpha=1.0, beta=0.0).fit(table)
    assert _names(table, [g for g, _ in clf.regions.positive]) == {"x2"}
    assert _names(table, [g for g, _ in clf.regions.negative]) == {"x1", "x12"}
    # The paper lists SR(x3), SR(x5), SR(x6), SR(x8), SR(x10); the remaining
    # boundary neighborhoods are equal to those as sets.
    boundary_sets = _sets(table, [g for g, _ in clf.regions.boundary])
    granules = {table.ids[g.origin]: frozenset(table.ids[m] for m in g.members) for g, _ in clf.regions.boundary}
    assert boundary_sets == {granules[name] for name in ("x3", "x5", "x6", "x8", "x10")}


# ---- Section 4.3: maximal-clique-induced granular spaces -----------------------


def test_indiscernibility_maximal_cliques_match_paper(table):
    granules = clique_space(table, OrlowskaRelation(ATTRS, "indiscernibility"))
    assert _sets(table, granules) == {
        frozenset({"x1"}),
        frozenset({"x2"}),
        frozenset({"x3", "x4"}),
        frozenset({"x5"}),
        frozenset({"x6", "x7"}),
        frozenset({"x8", "x9"}),
        frozenset({"x10", "x11"}),
        frozenset({"x12"}),
    }


def test_forward_inclusion_cliques_equal_indiscernibility_cliques(table):
    # Paper: "the maximal FR-induced cliques are exactly the same as the
    # maximal IND-induced cliques".
    forward = _sets(table, clique_space(table, OrlowskaRelation(ATTRS, "forward")))
    ind = _sets(table, clique_space(table, OrlowskaRelation(ATTRS, "indiscernibility")))
    assert forward == ind


def test_indiscernibility_clique_regions_and_table_5_decisions_match_paper(table):
    clf = GranularThreeWayClassifier("clique", OrlowskaRelation(ATTRS, "indiscernibility"), alpha=1.0, beta=0.0).fit(table)
    assert _sets(table, [g for g, _ in clf.regions.positive]) == {frozenset({"x2"}), frozenset({"x3", "x4"}), frozenset({"x5"})}
    assert _sets(table, [g for g, _ in clf.regions.negative]) == {
        frozenset({"x1"}), frozenset({"x6", "x7"}), frozenset({"x8", "x9"}), frozenset({"x12"})
    }
    assert _sets(table, [g for g, _ in clf.regions.boundary]) == {frozenset({"x10", "x11"})}
    assert clf.decide(_y(table, "y7")).outcome == ACCEPT
    assert clf.decide(_y(table, "y8")).outcome == REJECT
    assert clf.decide(_y(table, "y9")).outcome == DEFER


def test_similarity_maximal_cliques_match_paper(table):
    granules = clique_space(table, OrlowskaRelation(ATTRS, "similarity"))
    assert _sets(table, granules) == {
        frozenset({"x1", "x12"}),
        frozenset({"x2", "x3", "x4"}),
        frozenset({"x3", "x4", "x8", "x9", "x10", "x11"}),
        frozenset({"x5", "x10", "x11"}),
        frozenset({"x6", "x7", "x8", "x9", "x10", "x11"}),
        frozenset({"x8", "x9", "x12"}),
    }


def test_similarity_clique_regions_and_table_6_decisions_match_paper(table):
    clf = GranularThreeWayClassifier("clique", OrlowskaRelation(ATTRS, "similarity"), alpha=1.0, beta=0.0).fit(table)
    assert _sets(table, [g for g, _ in clf.regions.positive]) == {frozenset({"x2", "x3", "x4"})}
    # Regions follow Definition 13: MC1 = {x1, x12} has Pr(X | MC1) = 0 <= beta,
    # so it is negative together with MC6.
    assert _sets(table, [g for g, _ in clf.regions.negative]) == {
        frozenset({"x8", "x9", "x12"}),
        frozenset({"x1", "x12"}),
    }
    assert _sets(table, [g for g, _ in clf.regions.boundary]) == {
        frozenset({"x3", "x4", "x8", "x9", "x10", "x11"}),
        frozenset({"x5", "x10", "x11"}),
        frozenset({"x6", "x7", "x8", "x9", "x10", "x11"}),
    }
    assert clf.decide(_y(table, "y10")).outcome == ACCEPT
    assert clf.decide(_y(table, "y11")).outcome == REJECT
    assert clf.decide(_y(table, "y12")).outcome == DEFER


# ---- Section 3.2: quotient spaces and general properties ------------------------


def test_quotient_space_is_partition_into_identical_descriptions(table):
    granules = quotient_space(table)
    assert _sets(table, granules) == _sets(table, clique_space(table, Indiscernibility()))
    members = [m for g in granules for m in g.members]
    assert sorted(members) == list(range(len(table)))


def test_quotient_classifier_accepts_only_exact_descriptions(table):
    clf = GranularThreeWayClassifier("quotient", alpha=1.0, beta=0.0).fit(table)
    assert clf.decide(_y(table, "y7")).outcome == ACCEPT  # identical to x2
    assert clf.decide(_y(table, "y1")).outcome == DEFER  # matches no class


def test_distance_relation_with_theta_zero_gives_the_quotient_space(table):
    relation = DistanceRelation(ATTRS, theta=0.0)
    assert _sets(table, clique_space(table, relation)) == _sets(table, quotient_space(table))
    neighborhoods = neighborhood_space(table, relation)
    assert _sets(table, neighborhoods) == _sets(table, quotient_space(table))


def test_larger_theta_never_shrinks_neighborhoods(table):
    small = neighborhood_space(table, DistanceRelation(ATTRS, theta=0.2))
    large = neighborhood_space(table, DistanceRelation(ATTRS, theta=0.5))
    for a, b in zip(small, large):
        assert a.members <= b.members


def test_mixed_attribute_distance():
    attrs = [Attribute("model", "categorical"), Attribute("tags", "set"), Attribute("duration", "numeric", scale=10.0)]
    t = (attrs[0].normalize("Wan"), attrs[1].normalize(["a", "b"]), attrs[2].normalize(4))
    u = (attrs[0].normalize("Kling"), attrs[1].normalize(["b", "c"]), attrs[2].normalize(9))
    # (1 + (1 - 1/3) + 0.5) / 3
    assert tuple_distance(attrs, t, u) == pytest.approx((1 + 2 / 3 + 0.5) / 3)
    assert tuple_distance(attrs, t, t) == 0.0


def test_predecessor_neighborhood_uses_inverse_relation(table):
    relation = OrlowskaRelation(ATTRS, "backward")
    successors = neighborhood_space(table, relation, "s")
    predecessors = neighborhood_space(table, relation, "p")
    matrix = relation_matrix(table, relation)
    for s, p in zip(successors, predecessors):
        x = s.origin
        assert s.members == {y for y in range(len(table)) if matrix[x][y]}
        assert p.members == {y for y in range(len(table)) if matrix[y][x]}


def test_maximal_cliques_on_small_graph():
    # Square 0-1-2-3-0 with diagonal 0-2: cliques {0,1,2} and {0,2,3}.
    adjacency = [frozenset({1, 2, 3}), frozenset({0, 2}), frozenset({0, 1, 3}), frozenset({0, 2})]
    assert set(maximal_cliques(adjacency)) == {frozenset({0, 1, 2}), frozenset({0, 2, 3})}
    with pytest.raises(RuntimeError):
        maximal_cliques(adjacency, max_cliques=1)


def test_thresholds_are_validated(table):
    with pytest.raises(ValueError):
        granular_regions([], frozenset(), alpha=0.4, beta=0.6)
    with pytest.raises(ValueError):
        GranularThreeWayClassifier("neighborhood")


def test_rules_are_readable(table):
    clf = GranularThreeWayClassifier("neighborhood", OrlowskaRelation(ATTRS, "backward"), alpha=1.0, beta=0.0).fit(table)
    rules = clf.rules()
    accepts = [r for r in rules if r["decision"] == "accept"]
    assert {r["granule"] for r in accepts} >= {"R(x3)", "R(x2)", "R(x5)"}
    assert all(r["probability"] == 1.0 for r in accepts)
