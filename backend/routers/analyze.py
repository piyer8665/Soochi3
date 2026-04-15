import os
import uuid
import base64
import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from storage.db import supabase
from pipeline.ingest import ingest
from pipeline.classifier import classify_all_columns
from pipeline.missingness import detect_missingness
from pipeline.graph import build_graph
from pipeline.validator import validate_and_lock, get_all_locks
from pipeline.metadata import build_metadata_brief, detect_schema_family, detect_anomalies
from pipeline.normality import run_normality_analysis
from reasoning.scout import run_scout
from reasoning.deterministic_writer import write_deterministic_entries
from reasoning.interpreter import run_interpreter
from reasoning.writer import run_writer
from output.assembler import assemble_dictionary
from output.recoder import build_recoded_dataset
from output.validator import validate_output

load_dotenv()

router = APIRouter()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def log(session_id, stage, message, level="info"):
    try:
        supabase.table("pipeline_logs").insert({
            "session_id": session_id,
            "stage": stage,
            "message": message,
            "level": level
        }).execute()
    except Exception:
        pass

def to_b64(buf):
    if buf is None:
        return ""
    if isinstance(buf, str):
        return buf
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

class AnalyzeRequest(BaseModel):
    session_id: str
    file_path: str
    filename: str
    user_context: str = ""

@router.post("/analyze")
async def analyze_dataset(req: AnalyzeRequest):
    log(req.session_id, "ingest", f"Loading {req.filename}")
    ingest_result = ingest(req.file_path, req.filename)
    if not ingest_result.success:
        raise HTTPException(status_code=400, detail=ingest_result.error_message)

    df = ingest_result.dataframe
    recomputation_budget = [0]

    log(req.session_id, "classify", f"Classifying {len(df.columns)} columns")
    classification = classify_all_columns(df)
    log(req.session_id, "schema", "Detecting schema family and missingness")
    schema_hints_raw = detect_schema_family(df)
    schema_hints = [h.get('family', '') for h in schema_hints_raw]
    missingness = detect_missingness(df, schema_hints)
    log(req.session_id, "graph", "Building variable relationship graph")
    graph_result = build_graph(df, classification, missingness, recomputation_budget)
    log(req.session_id, "validate", "Validating and locking column mappings")
    validation_result = validate_and_lock(df, graph_result, classification, schema_hints, recomputation_budget)
    anomalies = detect_anomalies(df, classification)
    log(req.session_id, "metadata", "Assembling metadata brief")
    metadata_brief = build_metadata_brief(df, classification, missingness, graph_result, validation_result, schema_hints_raw, anomalies)
    log(req.session_id, "scout", "Scout routing — triaging variables")
    routing = run_scout(client, metadata_brief, classification)

    all_locks_obj = get_all_locks(validation_result)
    all_locks = {
        col: {
            "tier": lock.tier,
            "mapping_type": lock.mapping_type,
            "value": lock.value,
            "confidence": lock.confidence,
            "source": lock.source
        }
        for col, lock in all_locks_obj.items()
    }

    log(req.session_id, "deterministic", "Writing deterministic entries (numeric, binary, identifiers)")
    deterministic_entries = write_deterministic_entries(df, routing, metadata_brief, all_locks)
    log(req.session_id, "interpreter", "Interpreter — domain reasoning per variable")
    interpretations = run_interpreter(client, routing, metadata_brief, all_locks_obj, req.user_context)
    log(req.session_id, "writer", "Writer — formatting dictionary entries")
    writer_entries = run_writer(client, interpretations)

    log(req.session_id, "normality", "Running normality tests on numeric variables")
    try:
        normality_report, normality_plots = run_normality_analysis(df, classification)
    except Exception:
        normality_report = None
        normality_plots = {}

    log(req.session_id, "assemble", "Assembling final data dictionary")
    entries = assemble_dictionary(deterministic_entries, writer_entries, normality_report)
    validation_check = validate_output(entries, [c.strip() for c in df.columns])

    # Save entries to Supabase
    entries_rows = []
    for col_name, entry in entries.items():
        entries_rows.append({
            "id": str(uuid.uuid4()),
            "session_id": req.session_id,
            "column_name": col_name,
            "variable_type": entry.get("variable_type", ""),
            "description": entry.get("description", ""),
            "coding_table": entry.get("coding_table"),
            "data_quality_notes": entry.get("data_quality_notes"),
            "ordering_basis": entry.get("ordering_basis", ""),
            "range": str(entry.get("range", ""))
        })
    if entries_rows:
        supabase.table("entries").insert(entries_rows).execute()

    # Save normality results to Supabase
    if normality_report and hasattr(normality_report, 'results'):
        norm_rows = []
        for result in normality_report.results:
            col_name = result.column if hasattr(result, 'column') else result.get('column', '')
            plots_for_col = normality_plots.get(col_name, {})
            norm_rows.append({
                "id": str(uuid.uuid4()),
                "session_id": req.session_id,
                "column_name": col_name,
                "test": result.test if hasattr(result, 'test') else result.get('test', ''),
                "p_value": result.p_value if hasattr(result, 'p_value') else result.get('p_value'),
                "passes": result.passes if hasattr(result, 'passes') else result.get('passes'),
                "mean": result.mean if hasattr(result, 'mean') else result.get('mean'),
                "std": result.std if hasattr(result, 'std') else result.get('std'),
                "skewness": result.skewness if hasattr(result, 'skewness') else result.get('skewness'),
                "kurtosis": result.kurtosis if hasattr(result, 'kurtosis') else result.get('kurtosis'),
                "interpretation": result.interpretation if hasattr(result, 'interpretation') else result.get('interpretation', ''),
                "recommendation": result.recommendation if hasattr(result, 'recommendation') else result.get('recommendation', ''),
                "histogram_b64": to_b64(plots_for_col.get("histogram")),
                "qq_plot_b64": to_b64(plots_for_col.get("qq_plot"))
            })
        if norm_rows:
            supabase.table("normality_results").insert(norm_rows).execute()

    log(req.session_id, "complete", f"Analysis complete — {len(entries)} variables processed", "success")
    supabase.table("sessions").update({"status": "complete"}).eq("id", req.session_id).execute()

    return {
        "session_id": req.session_id,
        "status": "complete",
        "total_variables": len(entries),
        "missing_columns": validation_check.get("missing_columns", [])
    }
