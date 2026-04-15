import json
import time
import anthropic
from config import (
    WRITER_MODEL,
    WRITER_MAX_INPUT_TOKENS,
    WRITER_MAX_OUTPUT_TOKENS,
    API_RETRY_ATTEMPTS,
    API_RETRY_DELAY_SECONDS,
    RATE_LIMIT_DELAY_SECONDS,
    CHUNK_SIZE_SMALL_DATASET,
    CHUNK_SIZE_LARGE_DATASET,
    LARGE_DATASET_COLUMN_THRESHOLD
)


WRITER_SYSTEM_PROMPT = """You are the Writer — a professional technical writer who formats statistical data dictionary entries.

You receive structured interpretations from the Interpreter and format them into clean, authoritative dictionary entries.

STRICT RULES:
1. Never reason about meaning — only format what you are given
2. Never second-guess the Interpreter — if it says code 1 = Cerebellum, you document that
3. Use confidence tiers to calibrate language without exposing uncertainty to the user:
   - high confidence: write authoritatively with no qualification
   - medium confidence: write authoritatively but with slightly conservative phrasing
   - low confidence: write in the most conservative authoritative language possible
4. The user must always see authoritative output — never expose uncertainty directly
5. Every entry must be complete and professionally written
6. Coding tables must list every code clearly

Return ONLY valid JSON. No prose. No markdown. Just the JSON object."""


def run_writer(client: anthropic.Anthropic, interpretations: list) -> list:
    if not interpretations:
        return []

    chunk_size = (CHUNK_SIZE_LARGE_DATASET
                  if len(interpretations) > LARGE_DATASET_COLUMN_THRESHOLD
                  else CHUNK_SIZE_SMALL_DATASET)

    chunks = [interpretations[i:i+chunk_size]
              for i in range(0, len(interpretations), chunk_size)]

    all_entries = []
    for chunk in chunks:
        entries = _write_chunk(client, chunk)
        all_entries.extend(entries)
        if len(chunks) > 1:
            time.sleep(RATE_LIMIT_DELAY_SECONDS)

    return all_entries


def _write_chunk(client: anthropic.Anthropic, chunk: list) -> list:
    prompt = _build_writer_prompt(chunk)

    for attempt in range(API_RETRY_ATTEMPTS):
        try:
            response = client.messages.create(
                model=WRITER_MODEL,
                max_tokens=WRITER_MAX_OUTPUT_TOKENS,
                system=WRITER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = response.content[0].text.strip()
            return _parse_writer_response(raw, chunk)

        except anthropic.RateLimitError:
            if attempt < API_RETRY_ATTEMPTS - 1:
                time.sleep(API_RETRY_DELAY_SECONDS * (attempt + 1))
            else:
                return _fallback_entries(chunk)

        except Exception:
            if attempt < API_RETRY_ATTEMPTS - 1:
                time.sleep(RATE_LIMIT_DELAY_SECONDS)
            else:
                return _fallback_entries(chunk)

    return _fallback_entries(chunk)


def _build_writer_prompt(chunk: list) -> str:
    prompt = """Format the following interpreted variables into professional data dictionary entries.

Return a JSON object with this exact structure:
{
  "entries": [
    {
      "column": "column_name",
      "source": "writer",
      "variable_type": "Categorical Nominal|Categorical Ordinal|Continuous|Identifier|Empty",
      "description": "professional plain-English description",
      "coding_table": [
        {
          "code": "1",
          "name": "short name",
          "definition": "full definition"
        }
      ],
      "range": null,
      "data_quality_notes": [],
      "confidence": 0.9
    }
  ]
}

For continuous variables: coding_table should be empty, range should be a string like "0.0 – 145.2".
For categorical variables: include every code in the coding_table, range should be null.
For identifiers and empty variables: both coding_table and range should be empty/null.

Interpretations to format:
"""
    prompt += json.dumps(chunk, indent=2, default=str)
    return prompt


def _parse_writer_response(raw: str, chunk: list) -> list:
    try:
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)
        entries = parsed.get("entries", [])
        written_cols = {e["column"] for e in entries}
        for item in chunk:
            if item["column"] not in written_cols:
                entries.append(_fallback_single(item))
        # Merge ordering_basis from Interpreter, subtypes from chunk (Scout routing)
        # Subtypes come from the Scout via the chunk — more reliable than Interpreter output
        meta_map = {
            item["column"]: {
                "ordering_basis": item.get("ordering_basis", "alphabetical"),
                "subtypes": item.get("subtypes", [])
            }
            for item in chunk
        }
        for entry in entries:
            meta = meta_map.get(entry["column"], {})
            entry["ordering_basis"] = meta.get("ordering_basis", "alphabetical")
            entry["subtypes"] = meta.get("subtypes", [])
        return entries
    except Exception:
        return _fallback_entries(chunk)


def _fallback_entries(chunk: list) -> list:
    return [_fallback_single(item) for item in chunk]


def _fallback_single(item: dict) -> dict:
    col = item.get("column", "unknown")
    codes = item.get("codes", [])
    coding_table = [
        {"code": c.get("code", ""), "name": c.get("name", ""), "definition": c.get("definition", "")}
        for c in codes
    ]
    return {
        "column": col,
        "source": "writer_fallback",
        "variable_type": item.get("variable_type", "Unknown"),
        "description": item.get("description", f"Variable '{col}' — manual review required."),
        "coding_table": coding_table,
        "range": None,
        "data_quality_notes": item.get("data_quality_notes", []) + ["Writer fallback used"],
        "confidence": 0.5
    }