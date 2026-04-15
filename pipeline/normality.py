import pandas as pd
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
from dataclasses import dataclass, field
from config import (
    SHAPIRO_WILK_MAX_N,
    MIN_OBSERVATIONS_FOR_NORMALITY,
    PARAMETRIC_SIGNIFICANCE_LEVEL
)


@dataclass
class NormalityResult:
    column: str
    n: int
    test: str
    statistic: float
    p_value: float
    passes: bool
    interpretation: str
    mean: float
    std: float
    skewness: float
    kurtosis: float
    recommendation: str


@dataclass
class NormalityReport:
    results: list = field(default_factory=list)
    passed_variables: list = field(default_factory=list)
    failed_variables: list = field(default_factory=list)
    untestable_variables: list = field(default_factory=list)
    overall_recommendation: str = ""
    total_tested: int = 0


def run_normality_analysis(df: pd.DataFrame, classification: dict) -> tuple:
    report = NormalityReport()
    plots = {}

    testable_cols = _get_testable_columns(df, classification)

    for col, actual_col in testable_cols:
        series = df[actual_col].dropna()

        try:
            result = _test_normality(series, col)
            report.results.append(result)

            if result.passes is None:
                report.untestable_variables.append(col)
            elif result.passes:
                report.passed_variables.append(col)
            else:
                report.failed_variables.append(col)

            plots[col] = {
                "histogram": _generate_histogram(series, col),
                "qq_plot": _generate_qq_plot(series, col)
            }
        except Exception as e:
            report.untestable_variables.append(col)

    report.total_tested = len(report.passed_variables) + len(report.failed_variables)
    report.overall_recommendation = _build_overall_recommendation(report)

    return report, plots


def _get_testable_columns(df: pd.DataFrame, classification: dict) -> list:
    testable = []
    for col, info in classification.items():
        if info.classification not in ["continuous", "discrete"]:
            continue
        actual_col = col if col in df.columns else col.strip()
        if actual_col not in df.columns:
            for c in df.columns:
                if c.strip() == col.strip():
                    actual_col = c
                    break
            else:
                continue
        if not pd.api.types.is_numeric_dtype(df[actual_col]):
            continue
        series = df[actual_col].dropna()
        if len(series) < MIN_OBSERVATIONS_FOR_NORMALITY:
            continue
        testable.append((col.strip(), actual_col))
    return testable


def _test_normality(series: pd.Series, col_name: str) -> NormalityResult:
    n = len(series)

    if n < SHAPIRO_WILK_MAX_N:
        stat, p_value = stats.shapiro(series)
        test_name = "Shapiro-Wilk"
    else:
        stat, p_value = stats.kstest(series, 'norm', args=(series.mean(), series.std()))
        test_name = "Kolmogorov-Smirnov"

    passes = bool(p_value > PARAMETRIC_SIGNIFICANCE_LEVEL)

    if passes:
        interpretation = f"Data is consistent with a normal distribution (p={p_value:.4f} > {PARAMETRIC_SIGNIFICANCE_LEVEL})"
        recommendation = "Parametric tests appropriate (e.g. t-test, ANOVA, Pearson correlation)"
    else:
        interpretation = f"Data significantly deviates from normality (p={p_value:.4f} <= {PARAMETRIC_SIGNIFICANCE_LEVEL})"
        recommendation = "Use non-parametric tests (e.g. Mann-Whitney U, Kruskal-Wallis, Spearman correlation)"

    return NormalityResult(
        column=col_name,
        n=n,
        test=test_name,
        statistic=round(float(stat), 4),
        p_value=round(float(p_value), 4),
        passes=passes,
        interpretation=interpretation,
        mean=round(float(series.mean()), 4),
        std=round(float(series.std()), 4),
        skewness=round(float(series.skew()), 4),
        kurtosis=round(float(series.kurtosis()), 4),
        recommendation=recommendation
    )


def _build_overall_recommendation(report: NormalityReport) -> str:
    if report.total_tested == 0:
        return "No numeric variables were testable for normality in this dataset."

    if not report.failed_variables:
        return (
            f"All {report.total_tested} numeric variables pass normality testing. "
            f"Parametric tests are appropriate for this dataset."
        )
    elif not report.passed_variables:
        return (
            f"All {report.total_tested} numeric variables fail normality testing. "
            f"Non-parametric tests are recommended for this dataset."
        )
    else:
        return (
            f"Mixed results: {len(report.passed_variables)} variables pass, "
            f"{len(report.failed_variables)} fail normality testing. "
            f"Review each variable individually. "
            f"Parametric: {', '.join(report.passed_variables)}. "
            f"Non-parametric: {', '.join(report.failed_variables)}."
        )


def _generate_histogram(series: pd.Series, col_name: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')

    ax.hist(series, bins='auto', density=True, color='#4A90D9', alpha=0.7, edgecolor='#2D2D2D')

    mu, sigma = series.mean(), series.std()
    if sigma > 0:
        x = np.linspace(series.min(), series.max(), 200)
        ax.plot(x, stats.norm.pdf(x, mu, sigma), color='#E74C3C', linewidth=2, label='Normal')

    ax.set_title(col_name, color='white', fontsize=12)
    ax.set_xlabel('Value', color='#AAAAAA')
    ax.set_ylabel('Density', color='#AAAAAA')
    ax.tick_params(colors='#AAAAAA')
    for spine in ['bottom', 'left']:
        ax.spines[spine].set_color('#444444')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    if sigma > 0:
        ax.legend(facecolor='#2D2D2D', labelcolor='white', fontsize=9)

    plt.tight_layout()
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', facecolor='#1a1a1a')
    plt.close()
    buffer.seek(0)
    return buffer


def _generate_qq_plot(series: pd.Series, col_name: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor('#1a1a1a')
    ax.set_facecolor('#1a1a1a')

    try:
        (osm, osr), (slope, intercept, r) = stats.probplot(series, dist="norm")
        ax.scatter(osm, osr, color='#4A90D9', alpha=0.6, s=20, zorder=3)
        x_line = np.array([min(osm), max(osm)])
        ax.plot(x_line, slope * x_line + intercept, color='#E74C3C',
                linewidth=2, label=f'R²={r**2:.3f}')
        ax.legend(facecolor='#2D2D2D', labelcolor='white', fontsize=9)
    except Exception:
        ax.text(0.5, 0.5, 'Q-Q plot unavailable', transform=ax.transAxes,
                color='white', ha='center')

    ax.set_title(f'{col_name} — Q-Q Plot', color='white', fontsize=12)
    ax.set_xlabel('Theoretical Quantiles', color='#AAAAAA')
    ax.set_ylabel('Sample Quantiles', color='#AAAAAA')
    ax.tick_params(colors='#AAAAAA')
    for spine in ['bottom', 'left']:
        ax.spines[spine].set_color('#444444')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', facecolor='#1a1a1a')
    plt.close()
    buffer.seek(0)
    return buffer