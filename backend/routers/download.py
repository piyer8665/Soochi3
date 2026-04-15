import os
import io
import json
import base64
import zipfile
import tempfile
import subprocess
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from storage.db import supabase
from pipeline.ingest import ingest
from output.recoder import build_recoded_dataset
from output.assembler import build_excel_summary

router = APIRouter()

NODE_PATH = "/usr/local/node/bin/node"
if not os.path.exists(NODE_PATH):
    NODE_PATH = "node"

DOCX_BUILDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "docx_builder.js")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")


def get_session_data(session_id: str):
    session = supabase.table("sessions").select("*").eq("id", session_id).execute()
    if not session.data:
        raise HTTPException(status_code=404, detail="Session not found")
    entries = supabase.table("entries").select("*").eq("session_id", session_id).execute()
    normality = supabase.table("normality_results").select("*").eq("session_id", session_id).execute()
    return session.data[0], entries.data, normality.data


def entries_to_dict(entries_data):
    entries = {}
    for e in entries_data:
        entries[e["column_name"]] = {
            "variable_type": e.get("variable_type", ""),
            "description": e.get("description", ""),
            "range": e.get("range", ""),
            "coding_table": e.get("coding_table") or [],
            "data_quality_notes": e.get("data_quality_notes") or [],
        }
    return entries


def build_docx(session, entries_data, normality_data):
    entries_list = []
    for e in entries_data:
        entries_list.append({
            "column": e["column_name"],
            "variable_type": e.get("variable_type", ""),
            "description": e.get("description", ""),
            "range": e.get("range", ""),
            "mean": None,
            "median": None,
            "std": None,
            "coding_table": e.get("coding_table") or [],
            "data_quality_notes": e.get("data_quality_notes") or [],
        })

    normality_payload = None
    if normality_data:
        results = []
        for r in normality_data:
            results.append({
                "column": r["column_name"],
                "test": r.get("test", ""),
                "p_value": r.get("p_value"),
                "passes": r.get("passes"),
                "interpretation": r.get("interpretation", ""),
                "mean": r.get("mean"),
                "std": r.get("std"),
                "skewness": r.get("skewness"),
                "kurtosis": r.get("kurtosis"),
                "recommendation": r.get("recommendation", ""),
                "histogram": r.get("histogram_b64"),
                "qq_plot": r.get("qq_plot_b64"),
            })
        normality_payload = {"results": results, "overall_recommendation": ""}

    payload = {
        "dataset_name": session["dataset_name"].rsplit(".", 1)[0],
        "total_rows": session["total_rows"],
        "total_columns": session["total_columns"],
        "generated_at": datetime.now().strftime("%B %d, %Y %I:%M %p"),
        "entries": entries_list,
        "normality": normality_payload,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        json_path = f.name
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        docx_path = f.name

    try:
        result = subprocess.run(
            [NODE_PATH, DOCX_BUILDER, json_path, docx_path],
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


def build_recoded_excel(session_id: str, session, entries_data):
    # Find the uploaded file
    upload_files = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    # Use the most recently modified file as a fallback
    # In production we'd store file_path in sessions table
    dataset_name = session["dataset_name"]
    
    # Try to find the file by looking for recent uploads
    candidate = None
    for f in sorted(upload_files, key=lambda x: os.path.getmtime(os.path.join(UPLOAD_DIR, x)), reverse=True):
        candidate = os.path.join(UPLOAD_DIR, f)
        break
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Original dataset file not found")

    ingest_result = ingest(candidate, dataset_name)
    if not ingest_result.success:
        raise HTTPException(status_code=400, detail="Could not re-ingest dataset")

    entries = entries_to_dict(entries_data)
    buf = build_recoded_dataset(ingest_result.dataframe, entries)
    buf.seek(0)
    return buf.read()


@router.get("/download/{session_id}/word")
async def download_word(session_id: str):
    session, entries_data, normality_data = get_session_data(session_id)
    docx_bytes = build_docx(session, entries_data, normality_data)
    name = session["dataset_name"].rsplit(".", 1)[0]
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="soochi_{name}_report.docx"'}
    )


@router.get("/download/{session_id}/excel")
async def download_excel(session_id: str):
    session, entries_data, _ = get_session_data(session_id)
    excel_bytes = build_recoded_excel(session_id, session, entries_data)
    name = session["dataset_name"].rsplit(".", 1)[0]
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="soochi_{name}_recoded.xlsx"'}
    )


@router.get("/download/{session_id}/zip")
async def download_zip(session_id: str):
    session, entries_data, normality_data = get_session_data(session_id)
    name = session["dataset_name"].rsplit(".", 1)[0]

    docx_bytes = build_docx(session, entries_data, normality_data)
    excel_bytes = build_recoded_excel(session_id, session, entries_data)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"soochi_{name}_report.docx", docx_bytes)
        zf.writestr(f"soochi_{name}_recoded.xlsx", excel_bytes)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="soochi_{name}_bundle.zip"'}
    )
