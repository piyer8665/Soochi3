import pandas as pd
import numpy as np
import re
from dataclasses import dataclass, field
from config import (
    HARD_LOCK_THRESHOLD,
    SOFT_LOCK_THRESHOLD,
    PROVISIONAL_LOCK_THRESHOLD,
    VALIDATOR_REJECTION_RATE_TRIGGER,
    MAX_USER_CONFIRMATIONS,
    GLOBAL_RECOMPUTATION_BUDGET,
    MAX_RECOMPUTATIONS_PER_COLUMN
)


def normalize(v):
    if isinstance(v, str):
        return re.sub(r'\s+', ' ', v.strip().lower().replace('\xa0', ' '))
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


@dataclass
class LockEntry:
    column: str
    mapping_type: str
    value: dict
    evidence: list
    confidence: float
    tier: str  # hard | soft | provisional
    source: str  # validator | user | nhanes


@dataclass
class ValidationResult:
    hard_locks: dict = field(default_factory=dict)
    soft_locks: dict = field(default_factory=dict)
    provisional_locks: dict = field(default_factory=dict)
    rejected: list = field(default_factory=list)
    ambiguous: list = field(default_factory=list)
    auto_resolved_count: int = 0
    recomputation_flags: list = field(default_factory=list)


def validate_and_lock(df: pd.DataFrame, graph_result, classification: dict,
                      schema_hints: list, recomputation_budget: list) -> ValidationResult:
    result = ValidationResult()
    is_nhanes = any("NHANES" in str(h) for h in schema_hints)

    _apply_nhanes_locks(result, df, is_nhanes)

    _apply_identifier_locks(result, df, classification)

    edges = graph_result.edges
    col_edge_counts = {}
    col_rejection_counts = {}

    for edge in edges:
        col = edge.from_col
        col_edge_counts[col] = col_edge_counts.get(col, 0) + 1

        if col in result.hard_locks or col in result.soft_locks or col in result.provisional_locks:
            continue

        score = edge.combined_score
        evidence = [
            f"functional_dependency={edge.functional_dependency_score:.3f}",
            f"cross_tab={edge.cross_tab_score:.3f}",
        ]
        if edge.spearman_applicable:
            evidence.append(f"spearman={edge.spearman_score:.3f}")

        if score >= HARD_LOCK_THRESHOLD:
            result.hard_locks[col] = LockEntry(
                column=col, mapping_type="categorical",
                value={"explains": edge.to_col},
                evidence=evidence, confidence=score, tier="hard", source="validator"
            )
        elif score >= SOFT_LOCK_THRESHOLD:
            result.soft_locks[col] = LockEntry(
                column=col, mapping_type="categorical",
                value={"explains": edge.to_col},
                evidence=evidence, confidence=score, tier="soft", source="validator"
            )
        elif score >= PROVISIONAL_LOCK_THRESHOLD:
            result.provisional_locks[col] = LockEntry(
                column=col, mapping_type="categorical",
                value={"explains": edge.to_col},
                evidence=evidence, confidence=score, tier="provisional", source="validator"
            )
        else:
            result.rejected.append({
                "column": col, "explains": edge.to_col,
                "confidence": score, "reason": "below provisional threshold"
            })
            col_rejection_counts[col] = col_rejection_counts.get(col, 0) + 1

    for col, rejections in col_rejection_counts.items():
        total = col_edge_counts.get(col, 1)
        if rejections / total >= VALIDATOR_REJECTION_RATE_TRIGGER:
            if sum(recomputation_budget) < GLOBAL_RECOMPUTATION_BUDGET:
                result.recomputation_flags.append({
                    "column": col,
                    "reason": f"{rejections}/{total} edges rejected — recompute with stricter threshold"
                })
                recomputation_budget[0] += 1

    ambiguous_raw = []
    for edge in edges:
        col = edge.from_col
        if (col not in result.hard_locks and col not in result.soft_locks and
                col not in result.provisional_locks and
                PROVISIONAL_LOCK_THRESHOLD * 0.8 <= edge.combined_score < PROVISIONAL_LOCK_THRESHOLD):
            ambiguous_raw.append({
                "column": col,
                "explains": edge.to_col,
                "confidence": edge.combined_score,
                "evidence": [f"combined_score={edge.combined_score:.3f}"]
            })

    ambiguous_sorted = sorted(ambiguous_raw, key=lambda x: -x["confidence"])
    result.ambiguous = ambiguous_sorted[:MAX_USER_CONFIRMATIONS]
    result.auto_resolved_count = max(0, len(ambiguous_sorted) - MAX_USER_CONFIRMATIONS)

    return result


def _apply_nhanes_locks(result: ValidationResult, df: pd.DataFrame, is_nhanes: bool):
    if not is_nhanes:
        return
    nhanes_identifiers = {"SEQN": "Respondent Sequence Number"}
    nhanes_weights = {"WTINT2YR", "WTMEC2YR", "WTPH2YR", "WTPH4YR"}
    nhanes_design = {"SDMVSTRA", "SDMVPSU"}

    for col in df.columns:
        col_upper = col.strip().upper()
        if col_upper in nhanes_identifiers:
            result.hard_locks[col] = LockEntry(
                column=col, mapping_type="identifier",
                value={"name": nhanes_identifiers[col_upper]},
                evidence=["NHANES known identifier"],
                confidence=1.0, tier="hard", source="nhanes"
            )
        elif col_upper in nhanes_weights:
            result.hard_locks[col] = LockEntry(
                column=col, mapping_type="continuous",
                value={"role": "survey_weight"},
                evidence=["NHANES known survey weight"],
                confidence=1.0, tier="hard", source="nhanes"
            )
        elif col_upper in nhanes_design:
            result.hard_locks[col] = LockEntry(
                column=col, mapping_type="categorical",
                value={"role": "survey_design"},
                evidence=["NHANES known survey design variable"],
                confidence=1.0, tier="hard", source="nhanes"
            )


def _apply_identifier_locks(result: ValidationResult, df: pd.DataFrame, classification: dict):
    identifier_patterns = ['id', 'seq', 'key', 'num', 'no', 'number', '#', 'index']
    for col in df.columns:
        if col in result.hard_locks:
            continue
        info = classification.get(col)
        if not info or info.classification != "discrete":
            continue
        series = df[col].dropna()
        n = len(series)
        if n == 0:
            continue
        uniqueness = series.nunique() / n
        name_lower = col.lower().strip()
        name_suggests_id = any(p in name_lower for p in identifier_patterns)
        if uniqueness > 0.95 or (uniqueness > 0.80 and name_suggests_id):
            confidence = min(uniqueness + (0.1 if name_suggests_id else 0), 1.0)
            result.hard_locks[col] = LockEntry(
                column=col, mapping_type="identifier",
                value={"name": col.strip()},
                evidence=[f"uniqueness={uniqueness:.3f}", f"name_suggests_id={name_suggests_id}"],
                confidence=round(confidence, 3), tier="hard", source="validator"
            )


def apply_user_confirmations(result: ValidationResult, confirmed: list):
    for item in confirmed:
        col = item.get("column")
        if col:
            result.soft_locks[col] = LockEntry(
                column=col, mapping_type="categorical",
                value={"explains": item.get("explains", "")},
                evidence=["user confirmed"],
                confidence=1.0, tier="soft", source="user"
            )


def get_all_locks(result: ValidationResult) -> dict:
    all_locks = {}
    for col, lock in result.provisional_locks.items():
        all_locks[col] = lock
    for col, lock in result.soft_locks.items():
        all_locks[col] = lock
    for col, lock in result.hard_locks.items():
        all_locks[col] = lock
    return all_locks