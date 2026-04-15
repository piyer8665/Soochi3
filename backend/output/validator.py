def validate_output(entries: dict, expected_columns: list) -> dict:
    issues = []
    warnings = []

    entry_cols = set(entries.keys())
    expected_set = set(c.strip() for c in expected_columns)

    missing = expected_set - entry_cols
    for col in missing:
        issues.append(f"Missing entry for column: {col}")

    for col, entry in entries.items():
        if not entry.get("variable_type"):
            warnings.append(f"{col}: missing variable_type")
        if not entry.get("description"):
            warnings.append(f"{col}: missing description")
        coding_table = entry.get("coding_table", [])
        for row in coding_table:
            if not row.get("code"):
                warnings.append(f"{col}: coding table row missing code")
            if not row.get("name"):
                warnings.append(f"{col}: coding table row missing name")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "missing_columns": list(missing),
        "total_entries": len(entries)
    }