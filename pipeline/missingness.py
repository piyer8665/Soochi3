import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from config import (
    NHANES_REFUSED_CODES,
    NHANES_DONT_KNOW_CODES,
    HIGH_MISSINGNESS_THRESHOLD,
    CODED_MISSING_MAX_PCT
)


@dataclass
class MissingnessResult:
    column: str
    missing_count: int
    missing_pct: float
    missingness_type: str
    coded_missing_values: list = field(default_factory=list)
    high_missingness: bool = False


def detect_missingness(df: pd.DataFrame, schema_hints: list = None) -> dict:
    is_nhanes = any("NHANES" in str(h) for h in (schema_hints or []))
    results = {}
    for col in df.columns:
        results[col] = _analyze_column(df, col, is_nhanes)
    return results


def _analyze_column(df: pd.DataFrame, col: str, is_nhanes: bool) -> MissingnessResult:
    total = len(df)
    missing_count = int(df[col].isna().sum())
    missing_pct = round(missing_count / total * 100, 2) if total > 0 else 0.0
    high_missingness = missing_pct >= HIGH_MISSINGNESS_THRESHOLD * 100

    if missing_count == total:
        return MissingnessResult(
            column=col, missing_count=missing_count,
            missing_pct=missing_pct, missingness_type="structural",
            high_missingness=True
        )

    if missing_count == 0:
        coded = _detect_coded_missing(df[col], is_nhanes)
        if coded:
            return MissingnessResult(
                column=col, missing_count=0, missing_pct=0.0,
                missingness_type="coded_missing",
                coded_missing_values=coded, high_missingness=False
            )
        return MissingnessResult(
            column=col, missing_count=0, missing_pct=0.0,
            missingness_type="none", high_missingness=False
        )

    coded = _detect_coded_missing(df[col], is_nhanes)
    missingness_type = "coded_missing" if coded else "true_missing"

    return MissingnessResult(
        column=col, missing_count=missing_count,
        missing_pct=missing_pct, missingness_type=missingness_type,
        coded_missing_values=coded, high_missingness=high_missingness
    )


def _detect_coded_missing(series: pd.Series, is_nhanes: bool) -> list:
    coded = []
    series_clean = series.dropna()
    if len(series_clean) == 0 or not pd.api.types.is_numeric_dtype(series_clean):
        return coded

    total = len(series_clean)
    value_counts = series_clean.value_counts()
    all_known_codes = set(NHANES_REFUSED_CODES + NHANES_DONT_KNOW_CODES)

    for val, count in value_counts.items():
        pct = count / total
        try:
            int_val = int(val)
            if is_nhanes and int_val in all_known_codes:
                coded.append(str(int_val))
            # Only apply coded missing detection to non-NHANES datasets
            # if the value appears in fewer than 1% of rows AND is a known missing code
            # This prevents legitimate measurement values (7, 9) being flagged
            elif not is_nhanes and pct <= 0.01 and int_val in all_known_codes:
                coded.append(str(int_val))
        except (ValueError, TypeError):
            pass

    return coded