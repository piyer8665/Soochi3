import os
from config import SESSIONS_DIR


def save_dictionary_text(session_id: str, text: str) -> str:
    path = os.path.join(SESSIONS_DIR, session_id, "dictionary.txt")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def save_excel_summary(session_id: str, buffer) -> str:
    path = os.path.join(SESSIONS_DIR, session_id, "summary.xlsx")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(buffer.read())
    return path


def load_dictionary_text(session_id: str) -> str:
    path = os.path.join(SESSIONS_DIR, session_id, "dictionary.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def load_excel_summary(session_id: str):
    import io
    path = os.path.join(SESSIONS_DIR, session_id, "summary.xlsx")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return io.BytesIO(f.read())
    return None

import subprocess
import tempfile
import json
import base64
import zipfile
from datetime import datetime


def build_docx_report(entries: dict, dataset_name: str, total_rows: int,
                      total_columns: int, normality_data=None) -> bytes:
    """Build a professional Word document report using Node.js docx builder."""

    # Serialize entries
    entries_list = []
    for col, entry in entries.items():
        e = {
            "column": col,
            "variable_type": entry.get("variable_type", ""),
            "description": entry.get("description", ""),
            "range": entry.get("range", ""),
            "mean": entry.get("mean"),
            "median": entry.get("median"),
            "std": entry.get("std"),
            "coding_table": entry.get("coding_table", []),
            "data_quality_notes": entry.get("data_quality_notes", []),
        }
        entries_list.append(e)

    # Serialize normality data
    normality_payload = None
    if normality_data:
        try:
            report = normality_data.get("report")
            plots = normality_data.get("plots", {})
            if report:
                results = []
                for result in report.results:
                    r = {
                        "column": result.column,
                        "test": result.test,
                        "p_value": float(result.p_value),
                        "passes": result.passes,
                        "interpretation": result.interpretation,
                        "mean": float(result.mean) if result.mean is not None else None,
                        "std": float(result.std) if result.std is not None else None,
                        "skewness": float(result.skewness) if result.skewness is not None else None,
                        "kurtosis": float(result.kurtosis) if result.kurtosis is not None else None,
                        "recommendation": result.recommendation,
                        "histogram": None,
                        "qq_plot": None,
                    }
                    # Add plot images as base64
                    if result.column in plots:
                        col_plots = plots[result.column]
                        if "histogram" in col_plots and col_plots["histogram"]:
                            try:
                                buf = col_plots["histogram"]
                                buf.seek(0)
                                r["histogram"] = base64.b64encode(buf.read()).decode()
                            except Exception:
                                pass
                        if "qq_plot" in col_plots and col_plots["qq_plot"]:
                            try:
                                buf = col_plots["qq_plot"]
                                buf.seek(0)
                                r["qq_plot"] = base64.b64encode(buf.read()).decode()
                            except Exception:
                                pass
                    results.append(r)

                normality_payload = {
                    "results": results,
                    "overall_recommendation": report.overall_recommendation,
                }
        except Exception:
            pass

    payload = {
        "dataset_name": dataset_name,
        "total_rows": total_rows,
        "total_columns": total_columns,
        "generated_at": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "entries": entries_list,
        "normality": normality_payload,
    }

    # Write payload to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        json_path = f.name

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        docx_path = f.name

    try:
        node_path = "/usr/local/node/bin/node"
        import os
        if not os.path.exists(node_path):
            node_path = "node"
        script_path = os.path.join(os.path.dirname(__file__), "docx_builder.js")
        result = subprocess.run(
            [node_path, script_path, json_path, docx_path],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            raise RuntimeError(f"docx_builder failed: {result.stderr}")
        with open(docx_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(json_path)
        try:
            os.unlink(docx_path)
        except Exception:
            pass


def build_zip_export(docx_bytes: bytes, excel_bytes: bytes,
                     recoded_bytes: bytes, dataset_name: str) -> bytes:
    """Bundle docx + excel summary + recoded Excel into a ZIP file."""
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"soochi_{dataset_name}_report.docx", docx_bytes)
        zf.writestr(f"soochi_{dataset_name}_summary.xlsx", excel_bytes)
        zf.writestr(f"soochi_{dataset_name}_recoded.xlsx", recoded_bytes)
    buf.seek(0)
    return buf.read()
