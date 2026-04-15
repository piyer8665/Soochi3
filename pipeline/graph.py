import pandas as pd
import numpy as np
import itertools
import re
from dataclasses import dataclass, field
from collections import defaultdict
from scipy import stats
from config import (
    MIN_EDGE_SCORE,
    FUNCTIONAL_DEPENDENCY_CONSISTENCY_THRESHOLD,
    SPEARMAN_STRONG_THRESHOLD,
    SPEARMAN_MODERATE_THRESHOLD,
    CROSS_TAB_MIN_ROWS,
    CROSS_TAB_SIGNAL_THRESHOLD,
    GRAPH_OVERRIDE_EDGE_THRESHOLD,
    GRAPH_OVERRIDE_CLASSIFIER_CONFIDENCE,
    MAX_RECOMPUTATIONS_PER_COLUMN,
    GLOBAL_RECOMPUTATION_BUDGET
)


def normalize(v):
    if isinstance(v, str):
        return re.sub(r'\s+', ' ', v.strip().lower().replace('\xa0', ' '))
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


@dataclass
class GraphEdge:
    from_col: str
    to_col: str
    functional_dependency_score: float
    spearman_score: float
    spearman_applicable: bool
    cross_tab_score: float
    combined_score: float
    a_unique: int
    b_unique: int


@dataclass
class GraphResult:
    edges: list = field(default_factory=list)
    graph: dict = field(default_factory=dict)
    explained_by: dict = field(default_factory=dict)
    node_roles: dict = field(default_factory=dict)
    classifier_overrides: list = field(default_factory=list)


def build_graph(df: pd.DataFrame, classification: dict, missingness: dict, recomputation_budget: list) -> GraphResult:
    discrete_cols = [
        col for col, info in classification.items()
        if info.classification == "discrete"
    ]

    edges = []
    graph = defaultdict(list)
    explained_by = defaultdict(list)
    classifier_overrides = []

    for col_a, col_b in itertools.permutations(discrete_cols, 2):
        if col_a not in df.columns or col_b not in df.columns:
            continue

        a_unique = df[col_a].nunique()
        b_unique = df[col_b].nunique()

        if a_unique > b_unique:
            continue

        fd_score = _functional_dependency_score(df, col_a, col_b, missingness)
        spearman_score, spearman_applicable = _spearman_score(df, col_a, col_b)
        cross_tab_score = _cross_tab_score(df, col_a, col_b)

        if spearman_applicable:
            combined = (fd_score * 0.4 + spearman_score * 0.35 + cross_tab_score * 0.25)
        else:
            combined = (fd_score * 0.5 + cross_tab_score * 0.3 + 0.2 * fd_score)

        combined = round(combined, 3)

        if combined >= MIN_EDGE_SCORE:
            edge = GraphEdge(
                from_col=col_a.strip(),
                to_col=col_b.strip(),
                functional_dependency_score=round(fd_score, 3),
                spearman_score=round(spearman_score, 3),
                spearman_applicable=spearman_applicable,
                cross_tab_score=round(cross_tab_score, 3),
                combined_score=combined,
                a_unique=a_unique,
                b_unique=b_unique
            )
            edges.append(edge)
            graph[col_a].append(edge)
            explained_by[col_b].append(col_a)

            if (combined >= GRAPH_OVERRIDE_EDGE_THRESHOLD and
                    classification[col_a].continuous_score < GRAPH_OVERRIDE_CLASSIFIER_CONFIDENCE and
                    sum(recomputation_budget) < GLOBAL_RECOMPUTATION_BUDGET):
                classifier_overrides.append({
                    "column": col_a,
                    "reason": f"Strong graph edge {combined:.3f} contradicts classifier",
                    "suggested_classification": "discrete"
                })
                recomputation_budget[0] += 1

    node_roles = _classify_nodes(discrete_cols, dict(graph), dict(explained_by))

    return GraphResult(
        edges=edges,
        graph=dict(graph),
        explained_by=dict(explained_by),
        node_roles=node_roles,
        classifier_overrides=classifier_overrides
    )


def _functional_dependency_score(df, col_a, col_b, missingness):
    miss_a = missingness.get(col_a)
    miss_b = missingness.get(col_b)
    coded_a = set(miss_a.coded_missing_values) if miss_a else set()
    coded_b = set(miss_b.coded_missing_values) if miss_b else set()

    subset = df[[col_a, col_b]].dropna()
    if len(subset) == 0:
        return 0.0

    a_vals = subset[col_a].apply(normalize)
    b_vals = subset[col_b].apply(normalize)

    mask = ~a_vals.astype(str).isin(coded_a) & ~b_vals.astype(str).isin(coded_b)
    a_vals = a_vals[mask]
    b_vals = b_vals[mask]

    if len(a_vals) == 0:
        return 0.0

    consistent_rows = 0
    n_total = len(a_vals)

    for a_val in a_vals.unique():
        m = a_vals == a_val
        b_counts = b_vals[m].value_counts()
        top_count = b_counts.iloc[0]
        total_for_a = m.sum()
        consistency = top_count / total_for_a
        if consistency >= FUNCTIONAL_DEPENDENCY_CONSISTENCY_THRESHOLD:
            consistent_rows += top_count
        else:
            consistent_rows += top_count * 0.3

    return round(consistent_rows / n_total, 3)


def _spearman_score(df, col_a, col_b):
    if not (pd.api.types.is_numeric_dtype(df[col_a]) and
            pd.api.types.is_numeric_dtype(df[col_b])):
        return 0.5, False

    subset = df[[col_a, col_b]].dropna()
    if len(subset) < 5:
        return 0.5, False

    try:
        corr, p_value = stats.spearmanr(subset[col_a], subset[col_b])
        abs_corr = abs(corr)
        if abs_corr >= SPEARMAN_STRONG_THRESHOLD:
            return round(abs_corr, 3), True
        elif abs_corr >= SPEARMAN_MODERATE_THRESHOLD:
            return round(abs_corr * 0.8, 3), True
        else:
            return round(abs_corr * 0.5, 3), True
    except Exception:
        return 0.5, False


def _cross_tab_score(df, col_a, col_b):
    subset = df[[col_a, col_b]].dropna()
    if len(subset) < CROSS_TAB_MIN_ROWS:
        return 0.0

    try:
        a_vals = subset[col_a].apply(normalize)
        b_vals = subset[col_b].apply(normalize)
        crosstab = pd.crosstab(a_vals, b_vals)
        row_sums = crosstab.sum(axis=1)
        col_sums = crosstab.sum(axis=0)
        total = crosstab.values.sum()
        expected = np.outer(row_sums, col_sums) / total
        with np.errstate(divide='ignore', invalid='ignore'):
            chi = np.where(expected > 0, (crosstab.values - expected)**2 / expected, 0)
        chi_score = chi.sum()
        normalized = min(chi_score / (total + 1), 1.0)
        return round(normalized, 3) if normalized > CROSS_TAB_SIGNAL_THRESHOLD else 0.0
    except Exception:
        return 0.0


def _classify_nodes(discrete_cols, graph, explained_by):
    node_roles = {}
    for col in discrete_cols:
        is_explainer = col in graph and len(graph[col]) > 0
        is_explained = col in explained_by and len(explained_by[col]) > 0
        if is_explainer and not is_explained:
            node_roles[col] = "root"
        elif is_explained and not is_explainer:
            node_roles[col] = "leaf"
        elif is_explainer and is_explained:
            explains_more = any(e.b_unique > e.a_unique for e in graph[col])
            node_roles[col] = "root" if explains_more else "bridge"
        else:
            node_roles[col] = "orphan"
    return node_roles