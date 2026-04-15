import json
import time
import anthropic
from config import (
    INTERPRETER_MODEL,
    INTERPRETER_MAX_INPUT_TOKENS,
    INTERPRETER_MAX_OUTPUT_TOKENS,
    API_RETRY_ATTEMPTS,
    API_RETRY_DELAY_SECONDS,
    RATE_LIMIT_DELAY_SECONDS,
    CHUNK_SIZE_SMALL_DATASET,
    CHUNK_SIZE_LARGE_DATASET,
    LARGE_DATASET_COLUMN_THRESHOLD
)


INTERPRETER_SYSTEM_PROMPT = """You are the Interpreter — a statistical domain expert who reasons about what data variables mean.

You receive structured information about variables that require AI interpretation. Your job is to determine:
- What each variable represents
- What each code means (for categorical variables)
- What names and definitions should be assigned

STRICT RULES:
1. Never invent codes, names, or definitions not supported by the data or well-established conventions
2. Derive names strictly from definitions — never go beyond what the definition says
3. For duplicate definitions, label as same structure measured separately — never invent distinctions
4. Apply domain knowledge conservatively — only when strongly supported by context
5. For NHANES: codes 7/77/777 = Refused, 9/99/999 = Don't Know
5b. For DISC personality assessments: the standard form administration order is D (Dominance), I (Influence), C (Conscientiousness), S (Steadiness). When coding Primary_Dominant_Style or equivalent DISC classification variables, always use this ordering: Dominance=1, Influence=2, Conscientiousness=3, Steadiness=4. Any no-dominant or tie category goes last.
6. Report confidence as tier only: high, medium, or low — never a number
7. Always provide a reasoning trace explaining what evidence you used
8. Handle subtypes in order: needs_mapping first, then needs_domain, then needs_naming, then needs_resolution
9. Code numbers in the input are placeholders only — do not treat them as meaningful. Your job is to interpret what each value means and assign it a name and definition. Python will handle final code numbering after you return your interpretations.
9b. Each variable's ordering is completely independent. Never let the ordering of one variable influence another variable in the same batch. Treat each variable as if it were the only one being interpreted.
9b. Each variable's ordering is completely independent. Never let the ordering of one variable influence another variable in the same batch. Treat each variable as if it were the only one being interpreted.
10. If a variable has is_composite_of in its brief, always explicitly state in the description that this variable is derived from or combines those variables
11. If a variable has needs_coding=True and text_values, assign numeric codes starting from 1 in a logical domain-appropriate order. Strip trailing whitespace variants and treat them as the same category. Use domain knowledge to determine the correct ordering. Always consolidate whitespace variants into a single code.
12. For needs_coding variables with text values: the code NAME must be the exact text value from the data, title-cased. NEVER add, combine, or substitute names. If the data says 'pons', the name is 'Pons'. If the data says 'frontal lobe', the name is 'Frontal Lobe'. If the data says 'whole', the name is 'Whole'. Never write invented combinations. The definition field is where domain knowledge goes — never the name field.
13. For needs_mapping variables with a coding_table that has leaf column definitions: the code NAME must be derived conservatively from the leaf definition text. Take the most prominent noun or noun phrase from the definition — do not apply domain reclassification, do not add specificity not present in the text, do not combine structures. If two codes have identical definitions, they are the same structure measured separately — use 'Name (Instance 1)' and 'Name (Instance 2)'. This rule applies ONLY to needs_mapping subtypes. For needs_domain subtypes, apply full domain knowledge freely.
14. For needs_coding variables with text_values: consolidate typo variants and spelling errors into a single code. If two text values are clearly the same word with a spelling error (e.g. 'olfactory' and 'olfractory', 'spinal cord' and 'spinal chord'), treat them as one category. Use the correct spelling as the name. Never create separate codes for typo variants of the same value.
15. For needs_domain variables with small integer unique_values (e.g. [1,2,3,4] or [2,3,4]): always generate a coding table. Name each code directly from its numeric value using plain language (e.g. 2→'2 Doors', 3→'3 Doors', 1→'1 Owner', 2→'2 Owners'). Preserve the natural numeric ordering — code 1 gets the smallest value, code N gets the largest. Never sort these alphabetically.
16. For any binary yes/no, present/absent, true/false, or condition/no-condition variable: ALWAYS use 0=negative condition, 1=positive condition. NEVER use 1/2 for binary variables. If the data contains 0 and 1, preserve those exact values as codes. Examples: 0=No Hypertension, 1=Hypertension. 0=No Stroke, 1=Stroke. 0=No Heart Disease, 1=Heart Disease. 0=No, 1=Yes. This rule is absolute and overrides all other ordering rules.
17. NEVER flag values like 7, 9, 77, 99, 777, 999 as coded missing values unless the dataset has been explicitly confirmed as NHANES in the schema hints. In non-NHANES datasets these are valid measurements — 77 could be an age, a glucose level, a score, or any other legitimate value. Do not apply NHANES conventions to non-NHANES data under any circumstances.

For each variable's codes array, also include an "ordering_basis" field at the interpretation level:
- "alphabetical" — codes are in alphabetical order by name (default)
- "domain_convention" — codes follow established domain conventions (e.g. DISC form order, blood type grouping)
- "user_specified" — codes follow explicit user instructions

Return ONLY valid JSON. No prose. No markdown. Just the JSON object."""


def run_interpreter(client: anthropic.Anthropic, routing: dict,
                    metadata_brief: dict, all_locks: dict,
                    user_context: str = "") -> list:
    needs_reasoning = routing.get("needs_reasoning", [])
    if not needs_reasoning:
        return []

    schema_hints = metadata_brief.get("dataset", {}).get("schema_hints", [])
    is_nhanes = any("NHANES" in str(h) for h in schema_hints)

    chunk_size = (CHUNK_SIZE_LARGE_DATASET
                  if len(needs_reasoning) > LARGE_DATASET_COLUMN_THRESHOLD
                  else CHUNK_SIZE_SMALL_DATASET)

    chunks = [needs_reasoning[i:i+chunk_size]
              for i in range(0, len(needs_reasoning), chunk_size)]

    all_interpretations = []
    for chunk in chunks:
        interpretations = _interpret_chunk(
            client, chunk, all_locks, schema_hints, is_nhanes, user_context
        )
        all_interpretations.extend(interpretations)
        if len(chunks) > 1:
            time.sleep(RATE_LIMIT_DELAY_SECONDS)

    return all_interpretations


def _interpret_chunk(client, chunk, all_locks, schema_hints, is_nhanes, user_context):
    prompt = _build_interpreter_prompt(chunk, all_locks, schema_hints, is_nhanes, user_context)

    for attempt in range(API_RETRY_ATTEMPTS):
        try:
            response = client.messages.create(
                model=INTERPRETER_MODEL,
                max_tokens=INTERPRETER_MAX_OUTPUT_TOKENS,
                system=INTERPRETER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            return _parse_interpreter_response(raw, chunk)

        except anthropic.RateLimitError:
            if attempt < API_RETRY_ATTEMPTS - 1:
                time.sleep(API_RETRY_DELAY_SECONDS * (attempt + 1))
            else:
                return _fallback_interpretations(chunk)

        except Exception:
            if attempt < API_RETRY_ATTEMPTS - 1:
                time.sleep(RATE_LIMIT_DELAY_SECONDS)
            else:
                return _fallback_interpretations(chunk)

    return _fallback_interpretations(chunk)


def _build_interpreter_prompt(chunk, all_locks, schema_hints, is_nhanes, user_context):
    lock_summaries = {}
    for col, lock in all_locks.items():
        if hasattr(lock, '__dict__'):
            lock_summaries[col] = {
                "tier": getattr(lock, 'tier', 'unknown'),
                "mapping_type": getattr(lock, 'mapping_type', 'unknown'),
                "value": getattr(lock, 'value', {}),
                "confidence": getattr(lock, 'confidence', 0)
            }
        elif isinstance(lock, dict):
            lock_summaries[col] = lock

    context_section = f"User context: {user_context}" if user_context else ""
    nhanes_note = "NOTE: This appears to be an NHANES dataset. Apply NHANES coding conventions." if is_nhanes else ""

    variables_section = json.dumps(
        [{
            "column": item["column"],
            "subtypes": item.get("subtypes", []),
            "confidence_tier": item.get("confidence_tier", "medium"),
            "compressed_brief": item.get("compressed_brief", {})
        } for item in chunk],
        indent=2, default=str
    )

    prompt = f"""Interpret the following variables and return structured interpretations.

{context_section}
{nhanes_note}
Schema hints: {json.dumps(schema_hints, default=str)}

Locked mappings (treat as ground truth):
{json.dumps(lock_summaries, indent=2, default=str)}

Variables to interpret:
{variables_section}

Return a JSON object with this exact structure:
{{
  "interpretations": [
    {{
      "column": "column_name",
      "variable_type": "Categorical Nominal|Categorical Ordinal|Continuous|Identifier|Empty",
      "description": "plain English description of what this variable represents",
      "codes": [
        {{
          "code": "1",
          "name": "short name",
          "definition": "full definition",
          "confidence_tier": "high|medium|low",
          "source": "observed|domain|inferred"
        }}
      ],
      "data_quality_notes": [],
      "interpreter_confidence_tier": "high|medium|low",
      "reasoning_trace": "what evidence was used to reach these interpretations"
    }}
  ]
}}

For continuous variables, codes array should be empty.
For categorical variables, include every code found in the data."""

    return prompt


def _parse_interpreter_response(raw, chunk):
    try:
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)
        interpretations = parsed.get("interpretations", [])
        interpreted_cols = {i["column"] for i in interpretations}
        for item in chunk:
            if item["column"] not in interpreted_cols:
                interpretations.append(_fallback_single(item["column"]))
        return interpretations
    except Exception:
        return _fallback_interpretations(chunk)


def _fallback_interpretations(chunk):
    return [_fallback_single(item["column"]) for item in chunk]


def _fallback_single(col):
    return {
        "column": col,
        "variable_type": "Unknown",
        "description": f"Variable '{col}' could not be automatically interpreted. Manual review required.",
        "codes": [],
        "data_quality_notes": ["Interpreter unavailable — manual review required"],
        "interpreter_confidence_tier": "low",
        "reasoning_trace": "Fallback: Interpreter API call failed"
    }