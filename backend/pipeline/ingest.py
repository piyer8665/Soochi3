import os
import pandas as pd
import pyreadstat
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IngestResult:
    success: bool
    dataframe: object = None
    filename: str = ""
    extension: str = ""
    total_rows: int = 0
    total_columns: int = 0
    column_names: list = field(default_factory=list)
    spss_value_labels: dict = field(default_factory=dict)
    spss_column_labels: dict = field(default_factory=dict)
    error_type: str = ""
    error_message: str = ""


HUMAN_ERRORS = {
    "corrupted": "Soochi couldn t read this file. It may be corrupted. Try saving it as a new Excel file and uploading again.",
    "empty": "This file appears to be empty. Make sure it has column headers and at least one row of data.",
    "unsupported": "Soochi currently supports Excel (.xlsx) and SPSS (.sav) files.",
    "password": "This file is password protected. Please remove the password and upload again.",
    "no_columns": "Soochi couldn t find any columns in this file. Make sure it has column headers.",
    "no_rows": "This file has column headers but no data rows. Please add at least one row of data.",
}


def ingest(file_path: str, filename: str) -> IngestResult:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ["xlsx", "sav"]:
        return IngestResult(success=False, error_type="unsupported", error_message=HUMAN_ERRORS["unsupported"])
    try:
        if ext == "xlsx":
            return _ingest_excel(file_path, filename)
        elif ext == "sav":
            return _ingest_spss(file_path, filename)
    except Exception as e:
        error_str = str(e).lower()
        if "password" in error_str or "encrypted" in error_str:
            return IngestResult(success=False, error_type="password", error_message=HUMAN_ERRORS["password"])
        return IngestResult(success=False, error_type="corrupted", error_message=HUMAN_ERRORS["corrupted"])


def _ingest_excel(file_path: str, filename: str) -> IngestResult:
    try:
        df = pd.read_excel(file_path)
    except Exception:
        return IngestResult(success=False, error_type="corrupted", error_message=HUMAN_ERRORS["corrupted"])
    if len(df.columns) == 0:
        return IngestResult(success=False, error_type="no_columns", error_message=HUMAN_ERRORS["no_columns"])
    if len(df) == 0:
        return IngestResult(success=False, error_type="no_rows", error_message=HUMAN_ERRORS["no_rows"])
    return IngestResult(
        success=True, dataframe=df, filename=filename, extension="xlsx",
        total_rows=len(df), total_columns=len(df.columns),
        column_names=list(df.columns), spss_value_labels={}, spss_column_labels={}
    )


def _ingest_spss(file_path: str, filename: str) -> IngestResult:
    try:
        df, meta = pyreadstat.read_sav(file_path)
    except Exception:
        return IngestResult(success=False, error_type="corrupted", error_message=HUMAN_ERRORS["corrupted"])
    if len(df.columns) == 0:
        return IngestResult(success=False, error_type="no_columns", error_message=HUMAN_ERRORS["no_columns"])
    if len(df) == 0:
        return IngestResult(success=False, error_type="no_rows", error_message=HUMAN_ERRORS["no_rows"])
    for col, labels in meta.variable_value_labels.items():
        if labels and col in df.columns:
            label_col = f"{col}__label"
            df[label_col] = df[col].map({float(k): v for k, v in labels.items()})
    return IngestResult(
        success=True, dataframe=df, filename=filename, extension="sav",
        total_rows=len(df), total_columns=len(df.columns),
        column_names=list(df.columns),
        spss_value_labels=meta.variable_value_labels,
        spss_column_labels=meta.column_names_to_labels
    )
