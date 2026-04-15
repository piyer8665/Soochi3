import pandas as pd
import numpy as np
from config import SUMMARY_TABLE_MAX_CODE_LENGTH


def write_deterministic_entries(df: pd.DataFrame, routing: dict,
                                 metadata_brief: dict, all_locks: dict) -> list:
    entries = []

    for item in routing.get("deterministic", []):
        col = item["column"]
        entry = _write_continuous_entry(df, col, metadata_brief)
        if entry:
            entries.append(entry)

    for item in routing.get("identifier", []):
        col = item["column"]
        entry = _write_identifier_entry(df, col, metadata_brief, all_locks)
        if entry:
            entries.append(entry)

    for item in routing.get("empty", []):
        col = item["column"]
        entry = _write_empty_entry(col)
        if entry:
            entries.append(entry)

    return entries


def _write_continuous_entry(df: pd.DataFrame, col: str, metadata_brief: dict) -> dict:
    try:
        actual_col = col if col in df.columns else _find_col(df, col)
        if not actual_col:
            return _fallback_entry(col, "continuous")

        series = df[actual_col].dropna()
        col_info = metadata_brief.get("columns", {}).get(col, {})

        if len(series) == 0:
            return _fallback_entry(col, "continuous")

        # If column is not numeric, return None — misclassified
        if not pd.api.types.is_numeric_dtype(series):
            return None

        # Handle pure 0/1 binary columns deterministically
        unique_vals = set(float(v) for v in series.dropna().unique())
        if unique_vals <= {0.0, 1.0} and len(unique_vals) == 2:
            col_name_lower = col.lower().strip()
            # Derive positive and negative labels from column name
            pos_label = col.replace("_", " ").title()
            neg_label = f"No {pos_label}"
            return {
                "column": col,
                "variable_type": "Categorical Nominal",
                "description": f"Binary indicator variable. 0 = {neg_label}, 1 = {pos_label}.",
                "coding_table": [
                    {"code": "0", "name": neg_label, "definition": f"Individual does not have {pos_label.lower()} or the condition is absent"},
                    {"code": "1", "name": pos_label, "definition": f"Individual has {pos_label.lower()} or the condition is present"},
                ],
                "range": "0 – 1",
                "data_quality_notes": [],
                "ordering_basis": "binary_zero_one",
            }

        # If column has very few unique integer values, it's discrete
        # Return None so it falls back to needs_reasoning
        n_unique = series.nunique()
        total = len(series)
        try:
            is_integer_like = series.dropna().apply(lambda x: float(x) == int(float(x))).all()
        except Exception:
            is_integer_like = False
        col_info_local = metadata_brief.get('columns', {}).get(col, {})
        if n_unique <= 10 and is_integer_like and col_info_local.get('classification') == 'discrete':
            return None


        mean_val = round(float(series.mean()), 4)
        std_val = round(float(series.std()), 4)
        min_val = round(float(series.min()), 4)
        max_val = round(float(series.max()), 4)
        median_val = round(float(series.median()), 4)

        description = (
            f"Continuous numeric variable. "
            f"Observed range: {min_val} to {max_val}. "
            f"Mean: {mean_val}, Median: {median_val}, SD: {std_val}."
        )

        notes = []
        miss_pct = col_info.get("missing_pct", 0)
        if miss_pct > 0:
            notes.append(f"{miss_pct:.1f}% missing values")
        coded_missing = col_info.get("coded_missing_values", [])
        if coded_missing:
            notes.append(f"Coded missing values detected: {', '.join(coded_missing)}")

        return {
            "column": col,
            "source": "deterministic",
            "variable_type": "Continuous",
            "description": description,
            "coding_table": [],
            "range": f"{min_val} – {max_val}",
            "mean": mean_val,
            "median": median_val,
            "std": std_val,
            "data_quality_notes": notes,
            "confidence": 1.0
        }

    except Exception as e:
        return _fallback_entry(col, "continuous", error=str(e))


def _write_identifier_entry(df: pd.DataFrame, col: str,
                             metadata_brief: dict, all_locks: dict) -> dict:
    try:
        actual_col = col if col in df.columns else _find_col(df, col)
        col_info = metadata_brief.get("columns", {}).get(col, {})
        lock = all_locks.get(col)

        if lock and lock.get("value", {}).get("name"):
            name = lock["value"]["name"]
        else:
            name = col

        lock_source = lock.get("source", "validator") if lock else "validator"

        if lock_source == "nhanes":
            description = f"NHANES survey identifier. {name} — unique respondent sequence number used for data linkage. Not an analytical variable."
        else:
            n_unique = col_info.get("unique_count", 0)
            total = metadata_brief.get("dataset", {}).get("total_rows", 0)
            description = (
                f"Identifier variable. Each value uniquely or near-uniquely identifies a record. "
                f"{n_unique} unique values across {total} rows. Not intended for statistical analysis."
            )

        return {
            "column": col,
            "source": "deterministic",
            "variable_type": "Identifier",
            "description": description,
            "coding_table": [],
            "range": None,
            "data_quality_notes": [],
            "confidence": 1.0
        }

    except Exception as e:
        return _fallback_entry(col, "identifier", error=str(e))


def _write_empty_entry(col: str) -> dict:
    return {
        "column": col,
        "source": "deterministic",
        "variable_type": "Empty",
        "description": (
            "This variable contains no data or a single constant value across all records. "
            "It was not used during data collection or contains only missing values. "
            "Recommended for removal before analysis."
        ),
        "coding_table": [],
        "range": None,
        "data_quality_notes": ["No data recorded — recommend removal"],
        "confidence": 1.0
    }


def _fallback_entry(col: str, var_type: str, error: str = None) -> dict:
    notes = ["Deterministic writer encountered an issue — entry may be incomplete"]
    if error:
        notes.append(f"Error: {error}")
    return {
        "column": col,
        "source": "deterministic",
        "variable_type": var_type.capitalize(),
        "description": f"Variable type: {var_type}. Full documentation unavailable — requires manual review.",
        "coding_table": [],
        "range": None,
        "data_quality_notes": notes,
        "confidence": 0.5
    }


def _find_col(df: pd.DataFrame, col: str):
    if col in df.columns:
        return col
    stripped = col.strip()
    for c in df.columns:
        if c.strip() == stripped:
            return c
    return None