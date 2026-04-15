from fastapi import APIRouter, HTTPException
from storage.db import supabase

router = APIRouter()

@router.get("/session/{session_id}")
async def get_session(session_id: str):
    session = supabase.table("sessions").select("*").eq("id", session_id).execute()
    if not session.data:
        raise HTTPException(status_code=404, detail="Session not found")

    entries = supabase.table("entries").select("*").eq("session_id", session_id).execute()
    normality = supabase.table("normality_results").select("*").eq("session_id", session_id).execute()

    return {
        "session": session.data[0],
        "entries": entries.data,
        "normality": normality.data
    }

@router.get("/sessions")
async def list_sessions():
    sessions = supabase.table("sessions").select("id,dataset_name,total_rows,total_columns,created_at,status").eq("status", "complete").order("created_at", desc=True).limit(20).execute()
    return {"sessions": sessions.data}

@router.delete("/sessions")
async def delete_all_sessions():
    supabase.table("normality_results").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    supabase.table("entries").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    supabase.table("sessions").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    return {"status": "cleared"}

@router.get("/session/{session_id}/logs")
async def get_session_logs(session_id: str):
    logs = supabase.table("pipeline_logs").select("*").eq("session_id", session_id).order("created_at").execute()
    return {"logs": logs.data}

@router.post("/session/{session_id}/log")
async def add_log(session_id: str, stage: str, message: str, level: str = "info"):
    supabase.table("pipeline_logs").insert({
        "session_id": session_id,
        "stage": stage,
        "message": message,
        "level": level
    }).execute()
    return {"status": "ok"}
