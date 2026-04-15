import pandas as pd
import numpy as np
import re
from dataclasses import dataclass, field
from config import MAX_CODING_VALUES_IN_PROMPT, MAX_DEFINITION_CHARS


def normalize(v):
    if isinstance(v, str):
        return re.sub(r'\s+', ' ', v.strip().lower().replace('\xa0', ' '))
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def build_metadata_brief(df: pd.DataFrame, classification: dict, missingness: dict,
                          graph_result, validation_result, schema_hints: list,
                          anomalies: list) -> dict:
    columns = {}

    all_locks = {}
    for col, lock in validation_result.provisional_locks.items():
        all_locks[col] = lock
    for col, lock in validation_result.soft_locks.items():
        all_locks[col] = lock
    for col, lock in validation_result.hard_locks.items():
        all_locks[col] = lock

    edge_map = {}
    for edge in graph_result.edges:
        edge_map.setdefault(edge.from_col, []).append(edge)

    for col in df.columns:
        col_clean = col.strip()
        info = classification.get(col)
        miss = missingness.get(col)
        series = df[col].dropna()

        col_meta = {
            "dtype": str(df[col].dtype),
            "classification": info.classification if info else "unknown",
            "classification_confidence": info.continuous_score if info and info.classification == "continuous" else (info.discrete_score if info else 0.0),
            "unique_count": int(series.nunique()),
            "missing_count": int(miss.missing_count) if miss else 0,
            "missing_pct": float(miss.missing_pct) if miss else 0.0,
            "missingness_type": miss.missingness_type if miss else "unknown",
            "coded_missing_values": miss.coded_missing_values if miss else [],
            "high_missingness": miss.high_missingness if miss else False,
            "flagged_for_scout": info.flagged_for_scout if info else False,
            "node_role": graph_result.node_roles.get(col, "orphan"),
            "distribution": {
                "mean": round(float(series.mean()), 4) if pd.api.types.is_numeric_dtype(series) and len(series) > 0 else None,
                "min": round(float(series.min()), 4) if pd.api.types.is_numeric_dtype(series) and len(series) > 0 else None,
                "max": round(float(series.max()), 4) if pd.api.types.is_numeric_dtype(series) and len(series) > 0 else None,
                "median": round(float(series.median()), 4) if pd.api.types.is_numeric_dtype(series) and len(series) > 0 else None,
            } if pd.api.types.is_numeric_dtype(series) else None,
        }

        if info and info.classification == "continuous":
            col_meta["distribution"] = {
                "min": float(series.min()) if len(series) > 0 else None,
                "max": float(series.max()) if len(series) > 0 else None,
                "mean": round(float(series.mean()), 4) if len(series) > 0 else None,
                "std": round(float(series.std()), 4) if len(series) > 0 else None,
                "median": float(series.median()) if len(series) > 0 else None,
            }

        elif info and info.classification == "discrete":
            # Deduplicate whitespace variants before building unique value list
            # Preserve first-appearance order from the data — do not sort
            seen_normalized = {}
            ordered_vals = []
            for v in series:
                if pd.isna(v):
                    continue
                v_str = str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
                v_norm = v_str.strip().lower()
                if v_norm not in seen_normalized:
                    seen_normalized[v_norm] = v_str.strip()
                    ordered_vals.append(v_str.strip())

            # Sort alphabetically for deterministic reproducible ordering
            # Summary/aggregate values go last within alphabetical sort
            SUMMARY_SIGNALS = {"whole", "total", "overall", "all", "other",
                               "unknown", "none", "missing", "combined"}

            def sort_key(v):
                v_lower = v.lower().strip()
                words = set(v_lower.split())
                is_summary = bool(words & SUMMARY_SIGNALS)
                return (1 if is_summary else 0, v_lower)

            unique_vals = sorted(ordered_vals, key=sort_key)

            col_meta["unique_values"] = unique_vals[:MAX_CODING_VALUES_IN_PROMPT]
            col_meta["unique_values_truncated"] = len(unique_vals) > MAX_CODING_VALUES_IN_PROMPT

        if col in edge_map:
            col_meta["dependency_edges"] = [
                {
                    "to": e.to_col,
                    "combined_score": e.combined_score,
                    "functional_dependency": e.functional_dependency_score,
                    "spearman": e.spearman_score,
                    "spearman_applicable": e.spearman_applicable,
                    "cross_tab": e.cross_tab_score
                }
                for e in edge_map[col]
            ]

        if col_clean in all_locks:
            lock = all_locks[col_clean]
            col_meta["lock_status"] = lock.tier
            col_meta["lock_confidence"] = lock.confidence
            col_meta["lock_mapping_type"] = lock.mapping_type
            col_meta["lock_value"] = lock.value
            col_meta["lock_evidence"] = lock.evidence

        columns[col_clean] = col_meta

    coding_tables = _build_coding_tables(df, graph_result, validation_result)

    brief = {
        "dataset": {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "column_names": [c.strip() for c in df.columns],
            "schema_hints": schema_hints,
        },
        "columns": columns,
        "coding_tables": coding_tables,
        "anomalies": anomalies,
        "dependency_edges": [
            {
                "from": e.from_col,
                "to": e.to_col,
                "combined_score": e.combined_score
            }
            for e in sorted(graph_result.edges, key=lambda x: -x.combined_score)
        ]
    }

    return brief


def _build_coding_tables(df: pd.DataFrame, graph_result, validation_result) -> dict:
    coding_tables = {}
    all_locks = {}
    for col, lock in validation_result.provisional_locks.items():
        all_locks[col] = lock
    for col, lock in validation_result.soft_locks.items():
        all_locks[col] = lock
    for col, lock in validation_result.hard_locks.items():
        all_locks[col] = lock

    edge_map = {}
    for edge in graph_result.edges:
        edge_map.setdefault(edge.from_col, []).append(edge)

    # Build edge map using stripped column names for consistent lookup
    edge_map_stripped = {}
    for edge in graph_result.edges:
        edge_map_stripped.setdefault(edge.from_col.strip(), []).append(edge)

    root_cols = []
    for col, role in graph_result.node_roles.items():
        if role in ["root", "bridge"]:
            actual = col if col in df.columns else next(
                (c for c in df.columns if c.strip() == col.strip()), None
            )
            if actual:
                root_cols.append((col.strip(), actual))

    for col_stripped, actual_col in root_cols:
        leaf_cols = [e.to_col for e in edge_map_stripped.get(col_stripped, [])]
        series = df[actual_col].dropna()

        try:
            # Always sort by numeric value — preserves actual coding order from data
            unique_codes = sorted(
                series.unique(),
                key=lambda x: (float(x), 0) if pd.api.types.is_number(x) else (float('inf'), str(x))
            )
        except Exception:
            unique_codes = sorted(series.unique(), key=str)

        truncated = len(unique_codes) > MAX_CODING_VALUES_IN_PROMPT
        unique_codes = unique_codes[:MAX_CODING_VALUES_IN_PROMPT]

        codes = []
        for code in unique_codes:
            norm_code = normalize(code)
            mask = df[actual_col].apply(normalize) == norm_code
            code_str = str(int(code)) if isinstance(code, float) and code.is_integer() else str(code)
            entry = {"code": code_str, "frequency": int(mask.sum())}

            for leaf in leaf_cols:
                actual_leaf = leaf if leaf in df.columns else next(
                    (c for c in df.columns if c.strip() == leaf.strip()), None
                )
                if not actual_leaf or actual_leaf not in df.columns:
                    continue
                vals = df.loc[mask, actual_leaf].dropna()
                if len(vals) > 0:
                    most_common_norm = vals.apply(normalize).value_counts().index[0]
                    original = vals[vals.apply(normalize) == most_common_norm]
                    raw_val = str(original.iloc[0]).strip()
                    if len(raw_val) > MAX_DEFINITION_CHARS:
                        raw_val = raw_val[:MAX_DEFINITION_CHARS] + "..."
                    entry[leaf.strip()] = raw_val

            codes.append(entry)

        # Sort coding table to ensure consistent ordering across coded and uncoded versions
        # Sort by definition text alphabetically, summary/aggregate values last
        # This produces the same ordering regardless of input format
        if codes:
            first_leaf = leaf_cols[0].strip() if leaf_cols else None
            SUMMARY_SIGNALS = {"whole", "total", "overall", "all", "other",
                               "unknown", "none", "missing", "combined"}

            def code_sort_key(c):
                # Use leaf definition if available, otherwise use code value
                if first_leaf and first_leaf in c:
                    val = str(c[first_leaf]).lower().strip()
                else:
                    val = str(c.get("code", "")).lower().strip()
                words = set(val.split())
                is_summary = bool(words & SUMMARY_SIGNALS)
                return (1 if is_summary else 0, val)

            codes = sorted(codes, key=code_sort_key)
            # Reassign codes 1-N after sorting
            for idx, c in enumerate(codes, 1):
                c["code"] = str(idx)

        coding_tables[col_stripped] = {
            "codes": codes,
            "leaf_columns": [l.strip() for l in leaf_cols],
            "truncated": truncated
        }

    return coding_tables


def detect_schema_family(df: pd.DataFrame) -> list:
    col_names_lower = [c.lower().strip() for c in df.columns]
    hints = []

    nhanes_signals = ['seqn', 'wtint', 'wtmec', 'sdmv', 'ridage', 'riagendr']
    if any(s in col_names_lower for s in nhanes_signals):
        hints.append({"family": "NHANES", "confidence": "high",
                       "detail": "Column names match NHANES survey conventions"})

    neuro_signals = ['hemisphere', 'brain', 'cortex', 'neuron', 'lobe', 'cerebr', 'spinal']
    if sum(1 for s in neuro_signals if any(s in c for c in col_names_lower)) >= 2:
        hints.append({"family": "neuroscience", "confidence": "high",
                       "detail": "Column names suggest neuroscience dataset"})

    clinical_signals = ['patient', 'diagnosis', 'icd', 'bmi', 'blood', 'pressure', 'glucose']
    if sum(1 for s in clinical_signals if any(s in c for c in col_names_lower)) >= 2:
        hints.append({"family": "clinical", "confidence": "medium",
                       "detail": "Column names suggest clinical dataset"})

    survey_signals = ['response', 'likert', 'agree', 'disagree', 'frequency']
    if sum(1 for s in survey_signals if any(s in c for c in col_names_lower)) >= 2:
        hints.append({"family": "survey", "confidence": "medium",
                       "detail": "Column names suggest survey dataset"})

    return hints


def detect_anomalies(df: pd.DataFrame, classification: dict) -> list:
    anomalies = []
    for col in df.columns:
        info = classification.get(col)
        if not info:
            continue
        series = df[col].dropna()
        if info.classification == "discrete" and not pd.api.types.is_numeric_dtype(series):
            text_vals = series.unique()
            stripped = [str(v).strip() for v in text_vals]
            if len(set(stripped)) < len(text_vals):
                anomalies.append({
                    "column": col.strip(),
                    "type": "whitespace_variants",
                    "detail": "Column contains values that differ only by whitespace"
                })
        if info.classification == "continuous" and pd.api.types.is_numeric_dtype(series):
            if len(series) > 4:
                q1 = series.quantile(0.25)
                q3 = series.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    outliers = series[(series < q1 - 3 * iqr) | (series > q3 + 3 * iqr)]
                    if len(outliers) > 0:
                        anomalies.append({
                            "column": col.strip(),
                            "type": "numeric_outliers",
                            "detail": f"{len(outliers)} extreme outlier(s) detected beyond 3x IQR"
                        })
    return anomalies