import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from datetime import datetime, timedelta
from storage.db import supabase
from pipeline.ingest import ingest

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter()

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    user_context: str = Form(default="")
):
    ext = os.path.splitext(file.filename)[1]
    saved_filename = f"{uuid.uuid4()}{ext}"
    saved_path = os.path.abspath(os.path.join(UPLOAD_DIR, saved_filename))

    contents = await file.read()
    with open(saved_path, "wb") as f:
        f.write(contents)

    result = ingest(saved_path, file.filename)
    if not result.success:
        os.unlink(saved_path)
        raise HTTPException(status_code=400, detail=result.error_message)

    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "dataset_name": file.filename,
        "total_rows": result.total_rows,
        "total_columns": result.total_columns,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
        "status": "uploaded",
        "file_path": saved_path
    }
    supabase.table("sessions").insert(session).execute()

    return {
        "session_id": session_id,
        "dataset_name": file.filename,
        "total_rows": result.total_rows,
        "total_columns": result.total_columns,
        "columns": result.column_names,
        "file_path": saved_path,
        "status": "uploaded"
    }
