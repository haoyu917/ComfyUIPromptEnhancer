"""Three-way decision with granular rough sets.

Implements the three-step framework of J. Luo, M. Hu, C. Shi, Y. Yao,
"Three-way decision with granular rough sets", Applied Soft Computing 180
(2025) 113344:

  Step 1  information table -> granular space
          (quotient space, neighborhood-induced space, maximal-clique-induced space)
  Step 2  granular space -> probabilistic granular three-way approximations
  Step 3  approximations -> acceptance / rejection / non-commitment rules

Equation and definition numbers in comments refer to that paper.

Granule descriptions are sets of k-tuples in the Cartesian product TP_A of the
attribute domains (Defs 2-4). TP_A is far too large to enumerate, so
descriptions are kept intensionally: an object y satisfies GDes(G) (Def 6)
exactly when its original description Des_A(y) is related, through the
value-oriented relation, to the description of every object in the descriptor
set D(G). That is the same set membership test without building the set.

Pure Python; no third-party dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple

ACCEPT = "accept"
REJECT = "reject"
DEFER = "defer"

ATTRIBUTE_KINDS = ("categorical", "set", "numeric")
NEIGHBORHOOD_KINDS = ("s", "p", "s&p", "s|p")
SPACES = ("quotient", "neighborhood", "clique")

Description = Tuple[Any, ...]


# ---- Step 0: information table ------------------------------------------------


@dataclass(frozen=True)
class Attribute:
    """One attribute a in AT with its domain type.

    ``categorical`` values are compared for equality, ``set`` values are
    set-valued (as in the paper's set-valued information tables), ``numeric``
    values are real numbers normalized by ``scale`` in distance functions.
    """

    name: str
    kind: str = "categorical"
    weight: float = 1.0
    scale: float = 1.0

    def __post_init__(self) -> None:
        if self.kind not in ATTRIBUTE_KINDS:
            raise ValueError(f"Unknown attribute kind {self.kind!r}; use one of {ATTRIBUTE_KINDS}.")
        if self.weight < 0:
            raise ValueError("Attribute weight must be non-negative.")
        if self.scale <= 0:
            raise ValueError("Attribute scale must be positive.")

    def normalize(self, value: Any) -> Any:
        if self.kind == "set":
            if value is None:
                return frozenset()
            if isinstance(value, (str, bytes)):
                return frozenset({value})
            return frozenset(value)
        if self.kind == "numeric":
            return float(value)
        return value

    def as_set(self, value: Any) -> FrozenSet[Any]:
        """View any value as a set so Orlowska's set relations apply to all kinds."""

        return value if self.kind == "set" else frozenset({value})


class InformationTable:
    """T = (OB, AT, V, F): objects described by attribute values (Section 3.1)."""

    def __init__(
        self,
        attributes: Sequence[Attribute],
        rows: Sequence[Mapping[str, Any]],
        labels: Optional[Sequence[Any]] = None,
        ids: Optional[Sequence[Any]] = None,
    ):
        self.attributes: Tuple[Attribute, ...] = tuple(attributes)
        names = [attribute.name for attribute in self.attributes]
        if len(set(names)) != len(names):
            raise ValueError("Attribute names must be unique.")
        self.rows: List[Description] = [self.describe(row) for row in rows]
        if labels is not None and len(labels) != len(self.rows):
            raise ValueError("labels must have one entry per row.")
        self.labels: Optional[List[Any]] = list(labels) if labels is not None else None
        self.ids: List[Any] = list(ids) if ids is not None else [f"x{i + 1}" for i in range(len(self.rows))]
        if len(self.ids) != len(self.rows):
            raise ValueError("ids must have one entry per row.")

    def __len__(self) -> int:
        return len(self.rows)

    def describe(self, row: Mapping[str, Any]) -> Description:
        """Des_A(x) (Eq. 4): the k-tuple of an object's values on A."""

        missing = [attribute.name for attribute in self.attributes if attribute.name not in row]
        if missing:
            raise KeyError(f"Row is missing attributes: {missing}")
        return tuple(attribute.normalize(row[attribute.name]) for attribute in self.attributes)

    def des(self, index: int) -> Description:
        return self.rows[index]

    def members_with_label(self, label: Any = True) -> FrozenSet[int]:
        """The decision class X as a set of object indices."""

        if self.labels is None:
            raise ValueError("This table has no labels.")
        return frozenset(i for i, value in enumerate(self.labels) if value == label)

    def subset(self, indices: Sequence[int]) -> "InformationTable":
        table = InformationTable.__new__(InformationTable)
        table.attributes = self.attributes
        table.rows = [self.rows[i] for i in indices]
        table.labels = [self.labels[i] for i in indices] if self.labels is not None else None
        table.ids = [self.ids[i] for i in indices]
        return table


# ---- Value-oriented relations (Section 3.1, Eqs. 2-3; Table 1) ----------------


class ValueRelation:
    """A binary relation VR_A on TP_A, the space of attribute-value tuples."""

    symmetric = False

    def __call__(self, t: Description, u: Description) -> bool:
        raise NotImplementedError


class Indiscernibility(ValueRelation):
    """VE_A: t and t' are equal on every attribute (Eqs. 10-11)."""

    symmetric = True

    def __call__(self, t: Description, u: Description) -> bool:
        return t == u


class OrlowskaRelation(ValueRelation):
    """Orlowska's relations for set-valued tables (Table 1), value-oriented form.

    ``indiscernibility``:  t(a) = t'(a)          for all a
    ``forward``:           t(a) ⊆ t'(a)          for all a  (forward inclusion)
    ``backward``:          t(a) ⊇ t'(a)          for all a  (backward inclusion)
    ``similarity``:        t(a) ∩ t'(a) ≠ ∅      for all a

    Categorical and numeric values are treated as singleton sets.
    """

    KINDS = ("indiscernibility", "forward", "backward", "similarity")

    def __init__(self, attributes: Sequence[Attribute], kind: str):
        if kind not in self.KINDS:
            raise ValueError(f"Unknown Orlowska relation {kind!r}; use one of {self.KINDS}.")
        self.attributes = tuple(attributes)
        self.kind = kind
        self.symmetric = kind in {"indiscernibility", "similarity"}

    def __call__(self, t: Description, u: Description) -> bool:
        for attribute, a, b in zip(self.attributes, t, u):
            x, y = attribute.as_set(a), attribute.as_set(b)
            if self.kind == "indiscernibility" and x != y:
                return False
            if self.kind == "forward" and not x <= y:
                return False
            if self.kind == "backward" and not x >= y:
                return False
            if self.kind == "similarity" and not (x & y):
                return False
        return True


def attribute_distance(attribute: Attribute, a: Any, b: Any) -> float:
    """Per-attribute distance in [0, 1]."""

    if attribute.kind == "numeric":
        return min(1.0, abs(float(a) - float(b)) / attribute.scale)
    if attribute.kind == "set":
        union = a | b
        if not union:
            return 0.0
        return 1.0 - len(a & b) / len(union)  # Jaccard distance
    return 0.0 if a == b else 1.0


def tuple_distance(attributes: Sequence[Attribute], t: Description, u: Description) -> float:
    """Weighted mean of per-attribute distances, in [0, 1].

    The paper's experiments use Euclidean distance on numeric data (Eq. 31).
    Run records mix categorical, set-valued and numeric attributes, so each
    attribute contributes a distance normalized to [0, 1] (0/1 for categories,
    Jaccard distance for sets, scaled absolute difference for numbers). It is
    zero exactly when the tuples are equal, so theta = 0 gives the quotient
    space.
    """

    total = sum(attribute.weight for attribute in attributes)
    if total == 0:
        return 0.0
    return sum(attribute.weight * attribute_distance(attribute, a, b) for attribute, a, b in zip(attributes, t, u)) / total


class DistanceRelation(ValueRelation):
    """VR^d_A = {(t, t') | d(t, t') <= theta} (Eq. 3). Reflexive and symmetric."""

    symmetric = True

    def __init__(self, attributes: Sequence[Attribute], theta: float):
        if theta < 0:
            raise ValueError("theta must be non-negative.")
        self.attributes = tuple(attributes)
        self.theta = float(theta)

    def __call__(self, t: Description, u: Description) -> bool:
        # Small epsilon so that theta equal to a computed distance is inclusive.
        return tuple_distance(self.attributes, t, u) <= self.theta + 1e-12


# ---- Step 1: granular spaces ------------------------------------------------------


@dataclass(frozen=True)
class Granule:
    """A granule G with its descriptor set D(G) (Def 3), as object indices.

    ``check`` names how an object description is tested against each
    descriptor's description; see ``_satisfies_descriptor``.
    """

    members: FrozenSet[int]
    descriptors: Tuple[int, ...]
    space: str
    check: str
    origin: Optional[int] = None  # the object that induced it, when there is one

    def name(self, ids: Sequence[Any]) -> str:
        if self.space == "quotient":
            return f"[{ids[self.descriptors[0]]}]"
        if self.space == "neighborhood":
            return f"R({ids[self.origin]})"
        return "MC{" + ",".join(str(ids[i]) for i in sorted(self.members)) + "}"


def relation_matrix(table: InformationTable, relation: ValueRelation) -> List[List[bool]]:
    """Object-oriented relation R_A from VR_A (Eq. 18): R[x][y] iff (Des(x), Des(y)) in VR."""

    n = len(table)
    matrix = [[False] * n for _ in range(n)]
    for x in range(n):
        tx = table.des(x)
        start = x if relation.symmetric else 0
        for y in range(start, n):
            holds = relation(tx, table.des(y))
            matrix[x][y] = holds
            if relation.symmetric:
                matrix[y][x] = holds
    return matrix


def quotient_space(table: InformationTable) -> List[Granule]:
    """OB/E_A: equivalence classes of identical descriptions (Defs 8-10)."""

    classes: Dict[Description, List[int]] = {}
    for index, description in enumerate(table.rows):
        classes.setdefault(description, []).append(index)
    return [
        Granule(members=frozenset(indices), descriptors=(indices[0],), space="quotient", check="equal", origin=indices[0])
        for indices in classes.values()
    ]


def neighborhood_space(
    table: InformationTable,
    relation: ValueRelation,
    kind: str = "s",
    matrix: Optional[List[List[bool]]] = None,
) -> List[Granule]:
    """G_N(R*_A) = {R*_A(x) | x in OB} (Eqs. 19-21, Def 12).

    ``kind``: ``s`` successor, ``p`` predecessor, ``s&p`` both, ``s|p`` either.
    Each neighborhood is described by its central object, D_N(R(x)) = {x}
    (Def 14). One granule is kept per object, because neighborhoods that are
    equal as sets can still have different centers and so different
    descriptions.
    """

    if kind not in NEIGHBORHOOD_KINDS:
        raise ValueError(f"Unknown neighborhood kind {kind!r}; use one of {NEIGHBORHOOD_KINDS}.")
    rel = matrix if matrix is not None else relation_matrix(table, relation)
    n = len(table)
    granules = []
    for x in range(n):
        if kind == "s":
            members = {y for y in range(n) if rel[x][y]}
        elif kind == "p":
            members = {y for y in range(n) if rel[y][x]}
        elif kind == "s&p":
            members = {y for y in range(n) if rel[x][y] and rel[y][x]}
        else:
            members = {y for y in range(n) if rel[x][y] or rel[y][x]}
        members.add(x)  # Reflexive relations; guard against non-reflexive input.
        granules.append(Granule(frozenset(members), (x,), "neighborhood", kind, origin=x))
    return granules


def maximal_cliques(adjacency: Sequence[FrozenSet[int]], max_cliques: int = 200_000) -> List[FrozenSet[int]]:
    """All maximal cliques of an undirected graph (Bron-Kerbosch with pivoting).

    Iterative, so deep graphs do not hit Python's recursion limit. Clique
    enumeration is exponential in the worst case (the scalability limit noted
    in the paper's conclusion); ``max_cliques`` stops runaway enumeration.
    """

    cliques: List[FrozenSet[int]] = []
    stack: List[Tuple[FrozenSet[int], FrozenSet[int], FrozenSet[int]]] = [
        (frozenset(), frozenset(range(len(adjacency))), frozenset())
    ]
    while stack:
        r, p, x = stack.pop()
        if not p and not x:
            cliques.append(r)
            if len(cliques) > max_cliques:
                raise RuntimeError(
                    f"More than {max_cliques} maximal cliques; lower theta or raise max_cliques."
                )
            continue
        pivot = max(p | x, key=lambda v: len(adjacency[v] & p))
        for v in sorted(p - adjacency[pivot]):
            stack.append((r | {v}, p & adjacency[v], x & adjacency[v]))
            p = p - {v}
            x = x | {v}
    return cliques


def clique_space(
    table: InformationTable,
    relation: ValueRelation,
    matrix: Optional[List[List[bool]]] = None,
    max_cliques: int = 200_000,
) -> List[Granule]:
    """G_M(R_A): maximal cliques of R_A ∩ R_A^-1 (Section 3.4).

    Every object of a maximal clique is equally representative, so the
    descriptor set is the whole clique, D_M(MC) = MC (Def 19).
    """

    rel = matrix if matrix is not None else relation_matrix(table, relation)
    n = len(table)
    adjacency = [frozenset(y for y in range(n) if y != x and rel[x][y] and rel[y][x]) for x in range(n)]
    return [
        Granule(members=clique, descriptors=tuple(sorted(clique)), space="clique", check="s&p")
        for clique in maximal_cliques(adjacency, max_cliques=max_cliques)
    ]


# ---- Step 2: granular three-way approximations (Def 5) ---------------------------


@dataclass
class Regions:
    positive: List[Tuple[Granule, float]] = field(default_factory=list)
    boundary: List[Tuple[Granule, float]] = field(default_factory=list)
    negative: List[Tuple[Granule, float]] = field(default_factory=list)


def conditional_probability(granule: Granule, target: FrozenSet[int]) -> float:
    """Pr(X | G) = |G ∩ X| / |G|."""

    return len(granule.members & target) / len(granule.members)


def granular_regions(granules: Iterable[Granule], target: FrozenSet[int], alpha: float, beta: float) -> Regions:
    """GPOS, GBND, GNEG of class X (Eq. 8), with 0 <= beta < alpha <= 1."""

    if not 0.0 <= beta < alpha <= 1.0:
        raise ValueError("Thresholds must satisfy 0 <= beta < alpha <= 1.")
    regions = Regions()
    for granule in granules:
        probability = conditional_probability(granule, target)
        if probability >= alpha:
            regions.positive.append((granule, probability))
        elif probability <= beta:
            regions.negative.append((granule, probability))
        else:
            regions.boundary.append((granule, probability))
    return regions


# ---- Step 3: three-way decision rules (Defs 6-7, 11, 15, 20; Algorithm 1) --------


def _satisfies_descriptor(check: str, relation: ValueRelation, descriptor: Description, y: Description) -> bool:
    """Is Des(y) in the extended description of one descriptor object x?

    equal:  Des(y) = Des(x)                                  (Eq. 16)
    s:      (Des(x), Des(y)) in VR                           (Eq. 23)
    p:      (Des(x), Des(y)) in VR^-1                        (Table 7)
    s&p:    in VR ∩ VR^-1                                    (Table 7, cliques)
    s|p:    in VR ∪ VR^-1                                    (Table 7)
    """

    if check == "equal":
        return descriptor == y
    if check == "s":
        return relation(descriptor, y)
    if check == "p":
        return relation(y, descriptor)
    if check == "s&p":
        return relation(descriptor, y) and relation(y, descriptor)
    if check == "s|p":
        return relation(descriptor, y) or relation(y, descriptor)
    raise ValueError(f"Unknown check {check!r}")


def satisfies(table: InformationTable, granule: Granule, relation: ValueRelation, y: Description) -> bool:
    """y ⊨ GDes(G) (Def 6): Des(y) lies in the intersection of EDes(x), x in D(G) (Def 4)."""

    return all(_satisfies_descriptor(granule.check, relation, table.des(x), y) for x in granule.descriptors)


@dataclass
class Decision:
    outcome: str
    positive: List[Granule]
    negative: List[Granule]


class GranularThreeWayClassifier:
    """GRS3WDC (Algorithm 1) generalized to the decision rules of Def 7.

    Accept y if it satisfies the description of at least one granule in the
    positive region and of none in the negative region; reject in the mirror
    case; otherwise make the non-commitment (defer) decision.
    """

    def __init__(
        self,
        space: str = "neighborhood",
        relation: Optional[ValueRelation] = None,
        *,
        alpha: float = 1.0,
        beta: float = 0.0,
        neighborhood: str = "s",
        max_cliques: int = 200_000,
    ):
        if space not in SPACES:
            raise ValueError(f"Unknown space {space!r}; use one of {SPACES}.")
        if space != "quotient" and relation is None:
            raise ValueError(f"The {space} space needs a value-oriented relation.")
        if not 0.0 <= beta < alpha <= 1.0:
            raise ValueError("Thresholds must satisfy 0 <= beta < alpha <= 1.")
        self.space = space
        self.relation = relation if relation is not None else Indiscernibility()
        self.alpha = alpha
        self.beta = beta
        self.neighborhood = neighborhood
        self.max_cliques = max_cliques
        self.table: Optional[InformationTable] = None
        self.granules: List[Granule] = []
        self.regions: Optional[Regions] = None

    def fit(self, table: InformationTable, positive_label: Any = True) -> "GranularThreeWayClassifier":
        if len(table) == 0:
            raise ValueError("Cannot fit on an empty table.")
        self.table = table
        if self.space == "quotient":
            self.granules = quotient_space(table)
        else:
            matrix = relation_matrix(table, self.relation)
            if self.space == "neighborhood":
                self.granules = neighborhood_space(table, self.relation, self.neighborhood, matrix)
            else:
                self.granules = clique_space(table, self.relation, matrix, self.max_cliques)
        target = table.members_with_label(positive_label)
        self.regions = granular_regions(self.granules, target, self.alpha, self.beta)
        return self

    def _require_fit(self) -> Tuple[InformationTable, Regions]:
        if self.table is None or self.regions is None:
            raise RuntimeError("Call fit() first.")
        return self.table, self.regions

    def decide(self, y: Description) -> Decision:
        table, regions = self._require_fit()
        positive = [g for g, _ in regions.positive if satisfies(table, g, self.relation, y)]
        negative = [g for g, _ in regions.negative if satisfies(table, g, self.relation, y)]
        if positive and not negative:
            outcome = ACCEPT
        elif negative and not positive:
            outcome = REJECT
        else:
            outcome = DEFER
        return Decision(outcome, positive, negative)

    def decide_row(self, row: Mapping[str, Any]) -> Decision:
        table, _ = self._require_fit()
        return self.decide(table.describe(row))

    def predict(self, descriptions: Iterable[Description]) -> List[str]:
        return [self.decide(y).outcome for y in descriptions]

    def rules(self) -> List[Dict[str, Any]]:
        """Readable rules: one per positive or negative granule."""

        table, regions = self._require_fit()
        out = []
        for region, entries in (("accept", regions.positive), ("reject", regions.negative)):
            for granule, probability in entries:
                out.append(
                    {
                        "decision": region,
                        "granule": granule.name(table.ids),
                        "probability": round(probability, 4),
                        "support": len(granule.members),
                        "descriptors": [table.ids[i] for i in granule.descriptors],
                        "check": granule.check,
                    }
                )
        return out


def describe_space(granules: Sequence[Granule]) -> Dict[str, float]:
    """Summary statistics of a granular space, for reports."""

    if not granules:
        return {"granules": 0, "mean_size": 0.0, "max_size": 0}
    sizes = [len(g.members) for g in granules]
    return {
        "granules": len(granules),
        "distinct_member_sets": len({g.members for g in granules}),
        "mean_size": round(sum(sizes) / len(sizes), 3),
        "max_size": max(sizes),
    }

