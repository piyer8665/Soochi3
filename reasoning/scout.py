import json
import time
import anthropic
from config import (
    SCOUT_MODEL,
    SCOUT_MAX_INPUT_TOKENS,
    SCOUT_MAX_OUTPUT_TOKENS,
    API_RETRY_ATTEMPTS,
    API_RETRY_DELAY_SECONDS,
    RATE_LIMIT_DELAY_SECONDS,
    SCOUT_DETERMINISTIC_THRESHOLD,
    SCOUT_IDENTIFIER_THRESHOLD,
    SCOUT_ESCALATION_THRESHOLD,
    SCOUT_OVERRIDE_CLASSIFIER_THRESHOLD,
    SCOUT_MISSINGNESS_MAX
)


SCOUT_SYSTEM_PROMPT = """You are the Scout — a precise triage classifier for statistical datasets.

Your job is to classify every variable in a dataset into one of four buckets:
- deterministic: can be fully documented by Python alone, no AI reasoning needed
- identifier: a label, ID, or sequence number — not an analytical variable
- empty: no meaningful data, should be flagged for removal
- needs_reasoning: requires AI interpretation to document correctly

For needs_reasoning variables, also assign subtypes:
- needs_mapping: has numeric codes with a related text/definition column
- needs_domain: requires domain knowledge (NHANES, clinical, anatomical, etc.)
- needs_naming: has definitions but needs short names derived from them
- needs_resolution: has duplicate definitions or conflicting relationships

RULES:
- Report confidence as a tier only: high, medium, or low
- Never report a numeric confidence score
- Always provide a reasoning explanation for your classification
- When in doubt, classify as needs_reasoning — cost of unnecessary reasoning is always lower than silent error
- A variable can have multiple needs_reasoning subtypes

Return ONLY valid JSON. No prose. No markdown. Just the JSON object."""


def run_scout(client: anthropic.Anthropic, metadata_brief: dict, classification: dict) -> dict:
    prompt = _build_scout_prompt(metadata_brief)

    for attempt in range(API_RETRY_ATTEMPTS):
        try:
            response = client.messages.create(
                model=SCOUT_MODEL,
                max_tokens=SCOUT_MAX_OUTPUT_TOKENS,
                system=SCOUT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            scout_output = _parse_scout_response(raw)
            final_routing = _apply_python_routing_rules(scout_output, metadata_brief, classification)
            return final_routing

        except anthropic.RateLimitError:
            if attempt < API_RETRY_ATTEMPTS - 1:
                time.sleep(API_RETRY_DELAY_SECONDS * (attempt + 1))
            else:
                return _fallback_routing(metadata_brief, classification)

        except Exception as e:
            if attempt < API_RETRY_ATTEMPTS - 1:
                time.sleep(RATE_LIMIT_DELAY_SECONDS)
            else:
                return _fallback_routing(metadata_brief, classification)

    return _fallback_routing(metadata_brief, classification)


def _build_scout_prompt(metadata_brief: dict) -> str:
    dataset_info = metadata_brief.get("dataset", {})
    columns = metadata_brief.get("columns", {})
    coding_tables = metadata_brief.get("coding_tables", {})
    schema_hints = dataset_info.get("schema_hints", [])

    col_summaries = {}
    for col, info in columns.items():
        summary = {
            "dtype": info.get("dtype"),
            "classification": info.get("classification"),
            "classification_confidence": info.get("classification_confidence"),
            "unique_count": info.get("unique_count"),
            "missing_pct": info.get("missing_pct"),
            "missingness_type": info.get("missingness_type"),
            "high_missingness": info.get("high_missingness"),
            "node_role": info.get("node_role"),
            "flagged_for_scout": info.get("flagged_for_scout"),
            "lock_status": info.get("lock_status"),
        }
        if info.get("unique_values"):
            summary["unique_values"] = info["unique_values"][:10]
        if col in coding_tables:
            summary["has_coding_table"] = True
            summary["leaf_columns"] = coding_tables[col].get("leaf_columns", [])
        if info.get("dependency_edges"):
            summary["dependency_edges"] = info["dependency_edges"][:3]
        col_summaries[col] = summary

    prompt = f"""Dataset: {dataset_info.get('total_rows')} rows, {dataset_info.get('total_columns')} columns
Schema hints: {json.dumps(schema_hints)}

Classify every variable below. Return a JSON object with this exact structure:
{{
  "classifications": {{
    "column_name": {{
      "bucket": "deterministic|identifier|empty|needs_reasoning",
      "subtypes": [],
      "confidence_tier": "high|medium|low",
      "reasoning": "brief explanation",
      "compressed_brief": {{}}
    }}
  }}
}}

For needs_reasoning variables, populate compressed_brief with only the signals the Interpreter needs.
For other buckets, compressed_brief can be empty.

Variables to classify:
{json.dumps(col_summaries, indent=2, default=str)}"""

    return prompt


def _parse_scout_response(raw: str) -> dict:
    try:
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception:
        return {"classifications": {}}


def _apply_python_routing_rules(scout_output: dict, metadata_brief: dict, classification: dict) -> dict:
    classifications = scout_output.get("classifications", {})
    columns = metadata_brief.get("columns", {})
    coding_tables = metadata_brief.get("coding_tables", {})

    routing = {
        "deterministic": [],
        "identifier": [],
        "empty": [],
        "needs_reasoning": [],
        "scout_overrides": [],
        "scout_bypassed": False
    }

    for col, col_info in columns.items():
        col_clean = col.strip()
        scout_cls = classifications.get(col_clean, classifications.get(col, {}))

        bucket = scout_cls.get("bucket", "needs_reasoning")
        confidence_tier = scout_cls.get("confidence_tier", "low")
        subtypes = scout_cls.get("subtypes", [])
        reasoning = scout_cls.get("reasoning", "")
        compressed_brief = scout_cls.get("compressed_brief", {})

        python_classification = col_info.get("classification", "unknown")
        python_confidence = col_info.get("classification_confidence", 0.0)
        node_role = col_info.get("node_role", "orphan")
        has_edges = bool(col_info.get("dependency_edges"))
        missingness_pct = col_info.get("missing_pct", 0) / 100
        lock_status = col_info.get("lock_status")

        # Python routing override rules
        if python_classification == "empty" or col_info.get("high_missingness"):
            routing["empty"].append({"column": col_clean, "reasoning": "Empty or high missingness detected by Python"})
            continue

        if lock_status == "hard" and col_info.get("lock_mapping_type") == "identifier":
            routing["identifier"].append({"column": col_clean, "reasoning": "Hard locked as identifier"})
            continue

        if confidence_tier == "medium" or confidence_tier == "low":
            subtypes = subtypes or _infer_subtypes(col_clean, col_info, coding_tables)
            routing["needs_reasoning"].append({
                "column": col_clean,
                "subtypes": subtypes,
                "confidence_tier": confidence_tier,
                "reasoning": reasoning,
                "compressed_brief": _build_compressed_brief(col_clean, col_info, coding_tables, metadata_brief)
            })
            continue

        if bucket == "deterministic" and confidence_tier == "high":
            # Text categorical columns can never be deterministic — they need code assignment
            is_text = col_info.get("dtype", "").startswith("object") or not col_info.get("distribution")
            unique_count = col_info.get("unique_count", 999)
            # Exclude pure 0/1 binary columns from needs_reasoning — handle deterministically
            unique_vals = set(str(v) for v in col_info.get("unique_values", []))
            is_binary_zero_one = unique_vals <= {"0", "1", "0.0", "1.0"}
            is_low_unique_int = (unique_count <= 10 and python_classification == "discrete" and not is_text and not is_binary_zero_one)
            if (is_text or is_low_unique_int) and python_classification == "discrete":
                subtypes = _infer_subtypes(col_clean, col_info, coding_tables)
                routing["needs_reasoning"].append({
                    "column": col_clean,
                    "subtypes": subtypes,
                    "confidence_tier": "medium",
                    "reasoning": "Text categorical variable — needs code assignment, cannot be deterministic",
                    "compressed_brief": _build_compressed_brief(col_clean, col_info, coding_tables, metadata_brief)
                })
                routing["scout_overrides"].append({
                    "column": col_clean,
                    "scout_said": "deterministic",
                    "python_overrode_to": "needs_reasoning",
                    "reason": "Text categorical — deterministic writer cannot handle text columns"
                })
            elif python_confidence >= SCOUT_DETERMINISTIC_THRESHOLD and not has_edges:
                routing["deterministic"].append({"column": col_clean, "reasoning": reasoning})
            else:
                subtypes = _infer_subtypes(col_clean, col_info, coding_tables)
                routing["needs_reasoning"].append({
                    "column": col_clean,
                    "subtypes": subtypes,
                    "confidence_tier": "medium",
                    "reasoning": f"Scout said deterministic but Python evidence contradicts: edges={has_edges}, confidence={python_confidence:.2f}",
                    "compressed_brief": _build_compressed_brief(col_clean, col_info, coding_tables, metadata_brief)
                })
                routing["scout_overrides"].append({
                    "column": col_clean,
                    "scout_said": "deterministic",
                    "python_overrode_to": "needs_reasoning",
                    "reason": f"Python confidence {python_confidence:.2f} below threshold or strong edges found"
                })
            continue

        if bucket == "identifier" and confidence_tier == "high":
            # Python override: only accept identifier if uniqueness is actually high
            actual_col = col if col in col_info else col_clean
            unique_count = col_info.get("unique_count", 0)
            total_rows = metadata_brief.get("dataset", {}).get("total_rows", 1)
            uniqueness = unique_count / total_rows if total_rows > 0 else 0
            if uniqueness > 0.80:
                routing["identifier"].append({"column": col_clean, "reasoning": reasoning})
            else:
                subtypes = _infer_subtypes(col_clean, col_info, coding_tables)
                routing["needs_reasoning"].append({
                    "column": col_clean,
                    "subtypes": subtypes,
                    "confidence_tier": "medium",
                    "reasoning": f"Scout said identifier but uniqueness={uniqueness:.2f} is too low — treating as categorical",
                    "compressed_brief": _build_compressed_brief(col_clean, col_info, coding_tables, metadata_brief)
                })
                routing["scout_overrides"].append({
                    "column": col_clean,
                    "scout_said": "identifier",
                    "python_overrode_to": "needs_reasoning",
                    "reason": f"Uniqueness {uniqueness:.2f} below 0.80 threshold"
                })
            continue

        if bucket == "empty":
            routing["empty"].append({"column": col_clean, "reasoning": reasoning})
            continue

        subtypes = subtypes or _infer_subtypes(col_clean, col_info, coding_tables)
        routing["needs_reasoning"].append({
            "column": col_clean,
            "subtypes": subtypes,
            "confidence_tier": confidence_tier,
            "reasoning": reasoning,
            "compressed_brief": _build_compressed_brief(col_clean, col_info, coding_tables, metadata_brief)
        })

    return routing


def _infer_subtypes(col: str, col_info: dict, coding_tables: dict) -> list:
    subtypes = []
    if col in coding_tables and coding_tables[col].get("leaf_columns"):
        subtypes.append("needs_mapping")
    elif col_info.get("dependency_edges"):
        subtypes.append("needs_mapping")
    else:
        subtypes.append("needs_domain")
    if col_info.get("unique_count", 0) > 0 and col not in coding_tables:
        subtypes.append("needs_naming")
    return list(set(subtypes))


def _build_compressed_brief(col: str, col_info: dict, coding_tables: dict, metadata_brief: dict) -> dict:
    brief = {
        "dtype": col_info.get("dtype"),
        "unique_count": col_info.get("unique_count"),
        "missingness_type": col_info.get("missingness_type"),
        "coded_missing_values": col_info.get("coded_missing_values", []),
        "node_role": col_info.get("node_role"),
        "lock_status": col_info.get("lock_status"),
        "lock_value": col_info.get("lock_value"),
    }
    if col_info.get("unique_values"):
        brief["unique_values"] = col_info["unique_values"]
    if col_info.get("distribution"):
        brief["distribution"] = col_info["distribution"]
    if col in coding_tables:
        brief["coding_table"] = coding_tables[col]
    if col_info.get("dependency_edges"):
        brief["dependency_edges"] = col_info["dependency_edges"]

    # Add sibling column context for columns with related numeric siblings
    # This allows the Interpreter to cross-reference ordering from data
    col_lower = col.lower()
    all_columns = metadata_brief.get("columns", {})
    sibling_context = {}

    # Extract meaningful prefix from column name (e.g. "DISC" from "DISC_D_Score_True")
    col_parts = col.split('_')
    col_prefix = col_parts[0].lower() if col_parts else ""

    for other_col, other_info in all_columns.items():
        if other_col == col:
            continue
        other_lower = other_col.lower()
        other_parts = other_col.split('_')
        other_prefix = other_parts[0].lower() if other_parts else ""

        # Match by shared prefix OR shared meaningful keyword overlap
        col_words = set(col_lower.replace('_', ' ').split())
        other_words = set(other_lower.replace('_', ' ').split())
        STOP_WORDS = {'score', 'type', 'id', 'code', 'var', 'the', 'a', 'true', 'expected', 'no', 'num'}
        shared_words = (col_words & other_words) - STOP_WORDS
        shared_prefix = col_prefix and other_prefix and col_prefix == other_prefix and len(col_prefix) > 2

        if (shared_words or shared_prefix) and other_info.get("distribution"):
            dist = other_info["distribution"]
            sibling_context[other_col] = {
                "mean": dist.get("mean"),
                "min": dist.get("min"),
                "max": dist.get("max")
            }
    if sibling_context:
        brief["sibling_columns"] = sibling_context
        brief["sibling_hint"] = "These related continuous columns may help infer the ordering or meaning of codes in this variable. Use their mean scores to determine which category should receive lower vs higher codes."



    # Flag whether text labels are available for this column
    has_text_labels = False
    if col in coding_tables:
        for code_entry in coding_tables[col].get("codes", []):
            for k, v in code_entry.items():
                if k not in ["code", "frequency"] and isinstance(v, str) and not v.replace(".", "").isdigit():
                    has_text_labels = True
                    break
    brief["has_text_labels"] = has_text_labels

    # Detect uncoded text categorical variables — text values that need numeric codes assigned
    # Only flag as needs_coding if there is NO coding table from the dependency graph
    col_info_dtype = col_info.get("dtype", "")
    unique_vals = col_info.get("unique_values", [])
    has_coding_table = bool(brief.get("coding_table", {}).get("codes"))
    is_text_categorical = (
        col_info.get("is_text", False) or
        "object" in str(col_info_dtype) or
        (unique_vals and all(not str(v).replace(".", "").replace("-", "").isdigit() for v in unique_vals))
    )

    if is_text_categorical and unique_vals:
        brief["needs_coding"] = True
        brief["text_values"] = unique_vals
        brief["hint"] = (
            f"This variable contains uncoded text categories: {unique_vals}. "
            f"Assign numeric codes starting from 1 in a logical order using domain knowledge from the column name '{col}'. "
            f"Strip trailing whitespace variants and treat them as the same category. "
            f"Document each code with a clear name and definition."
        )
    elif not has_text_labels and not has_coding_table:
        brief["domain_knowledge_required"] = True
        brief["hint"] = f"No text labels available. Use domain knowledge from column name '{col}' and unique values to interpret codes."

    # Explicitly flag composite variables based on graph edges
    # Python detected these relationships — Interpreter just needs to document them
    all_columns = metadata_brief.get("columns", {})
    explained_by = []
    for other_col, other_info in all_columns.items():
        for edge in other_info.get("dependency_edges", []):
            if edge.get("to") == col:
                explained_by.append(other_col)
    if explained_by:
        brief["is_composite_of"] = explained_by
        brief["composite_note"] = f"This variable is derived from or composed of: {', '.join(explained_by)}. Document this relationship explicitly in the description."

    return brief


def _fallback_routing(metadata_brief: dict, classification: dict) -> dict:
    routing = {
        "deterministic": [],
        "identifier": [],
        "empty": [],
        "needs_reasoning": [],
        "scout_overrides": [],
        "scout_bypassed": True
    }
    columns = metadata_brief.get("columns", {})
    coding_tables = metadata_brief.get("coding_tables", {})
    identifier_patterns = ['id', 'seq', 'key', 'num', '#', 'index']

    for col, col_info in columns.items():
        col_clean = col.strip()
        python_cls = col_info.get("classification", "unknown")

        if python_cls == "empty" or col_info.get("high_missingness"):
            routing["empty"].append({"column": col_clean, "reasoning": "Fallback: empty or high missingness"})
        elif python_cls == "continuous":
            routing["deterministic"].append({"column": col_clean, "reasoning": "Fallback: continuous variable"})
        elif any(p in col_clean.lower() for p in identifier_patterns) and col_info.get("unique_count", 0) > len(columns) * 0.8:
            routing["identifier"].append({"column": col_clean, "reasoning": "Fallback: name suggests identifier"})
        else:
            subtypes = _infer_subtypes(col_clean, col_info, coding_tables)
            routing["needs_reasoning"].append({
                "column": col_clean,
                "subtypes": subtypes,
                "confidence_tier": "low",
                "reasoning": "Fallback: Scout unavailable, treating as needs_reasoning",
                "compressed_brief": _build_compressed_brief(col_clean, col_info, coding_tables, metadata_brief)
            })

    return routing