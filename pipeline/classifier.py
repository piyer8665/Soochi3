import math
import numpy as np
import pandas as pd
from dataclasses import dataclass
from config import (
    CONTINUOUS_CONFIDENCE_THRESHOLD,
    CLASSIFICATION_AMBIGUITY_THRESHOLD,
    SINGLE_VALUE_COLUMN_THRESHOLD
)


@dataclass
class ColumnClassification:
    column: str
    classification: str
    continuous_score: float
    discrete_score: float
    unique_count: int
    total_rows: int
    is_numeric: bool
    is_text: bool
    rationale: str
    flagged_for_scout: bool = False


def classify_all_columns(df):
    results = {}
    for col in df.columns:
        results[col] = _classify_column(df, col)
    return results


def _classify_column(df, col):
    series = df[col].dropna()
    total_rows = len(df)
    unique_count = series.nunique()
    is_numeric = pd.api.types.is_numeric_dtype(series)
    is_text = not is_numeric

    if len(series) == 0 or unique_count <= SINGLE_VALUE_COLUMN_THRESHOLD:
        return ColumnClassification(
            column=col, classification="empty",
            continuous_score=0.0, discrete_score=0.0,
            unique_count=unique_count, total_rows=total_rows,
            is_numeric=is_numeric, is_text=is_text,
            rationale="Empty or single-value column"
        )

    if is_text:
        return ColumnClassification(
            column=col, classification="discrete",
            continuous_score=0.0, discrete_score=1.0,
            unique_count=unique_count, total_rows=total_rows,
            is_numeric=False, is_text=True,
            rationale="Text column — always discrete"
        )

    cont_score = _score_continuous(series, unique_count)
    disc_score = 1.0 - cont_score
    classification = "continuous" if cont_score >= CONTINUOUS_CONFIDENCE_THRESHOLD else "discrete"
    flagged = abs(cont_score - disc_score) < (1 - CLASSIFICATION_AMBIGUITY_THRESHOLD)

    return ColumnClassification(
        column=col, classification=classification,
        continuous_score=round(cont_score, 3),
        discrete_score=round(disc_score, 3),
        unique_count=unique_count, total_rows=total_rows,
        is_numeric=is_numeric, is_text=is_text,
        rationale=f"unique={unique_count}, n={total_rows}, cont_score={cont_score:.3f}",
        flagged_for_scout=flagged
    )


def _score_continuous(series, unique_count):
    scores = []
    n = series.count()
    sqrt_ratio = unique_count / math.sqrt(n) if n > 0 else 0
    scores.append(min(sqrt_ratio / 3, 1.0))
    scores.append(0.0 if unique_count <= 20 else 0.8)
    if unique_count > 5:
        vals = sorted(series.dropna().unique())
        gaps = [vals[i+1] - vals[i] for i in range(len(vals)-1)]
        if gaps:
            mean_gap = float(np.mean(gaps))
            std_gap = float(np.std(gaps))
            cv = std_gap / mean_gap if mean_gap > 0 else 0
            scores.append(min(cv / 2, 1.0))
        else:
            scores.append(0.0)
    else:
        scores.append(0.0)
    return float(np.mean(scores))