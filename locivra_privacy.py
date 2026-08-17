"""Data-minimization and export safeguards for client-supplied pilot data."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_TEXT_LENGTH = 2_000
SAFE_CLIENT_COLUMNS = {
    "Location ID", "Location Name", "Address", "Location Type",
    "Annual Transactions", "Internal Incidents (12 months)",
    "Loss Amount (12 months)", "Guard Coverage", "CCTV Coverage",
    "Alarm Monitoring", "Client Notes",
}
PROHIBITED_COLUMN_TERMS = {
    "employee", "customer", "victim", "suspect", "witness", "name",
    "email", "phone", "telephone", "birthday", "birth date", "dob",
    "medical", "health", "sin", "social insurance", "credit card",
    "license plate", "licence plate", "case narrative", "incident narrative",
}
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)")
_SIN = re.compile(r"(?<!\d)\d{3}[ -]?\d{3}[ -]?\d{3}(?!\d)")
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def validate_upload_size(size_bytes: int | None) -> list[str]:
    if size_bytes is None:
        return []
    return [f"Upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."] if size_bytes > MAX_UPLOAD_BYTES else []


def inspect_client_frame(frame: pd.DataFrame, allowed_columns: set[str] | None = None) -> dict[str, list[str]]:
    """Flag likely personal/sensitive data without claiming perfect detection."""
    allowed = allowed_columns or SAFE_CLIENT_COLUMNS
    blockers, warnings = [], []
    extra = sorted(set(map(str, frame.columns)) - allowed)
    if extra:
        blockers.append("Unexpected columns are not accepted: " + ", ".join(extra))
    for column in frame.columns:
        normalized = str(column).casefold().replace("_", " ").replace("-", " ")
        if str(column) not in allowed and any(term in normalized for term in PROHIBITED_COLUMN_TERMS):
            blockers.append(f"Column '{column}' may contain personal or sensitive information and is not permitted.")
    text_columns = frame.select_dtypes(include=["object", "string"]).columns
    for column in text_columns:
        values = frame[column].dropna().astype(str)
        for row_index, value in values.items():
            if len(value) > MAX_TEXT_LENGTH:
                blockers.append(f"{column} row {row_index + 2} exceeds the {MAX_TEXT_LENGTH}-character text limit.")
            if _EMAIL.search(value):
                blockers.append(f"{column} row {row_index + 2} appears to contain an email address.")
            if _PHONE.search(value):
                blockers.append(f"{column} row {row_index + 2} appears to contain a phone number.")
            if _SIN.search(value):
                blockers.append(f"{column} row {row_index + 2} appears to contain a government identifier.")
    return {"blocking_issues": sorted(set(blockers)), "warnings": sorted(set(warnings))}


def csv_safe_value(value: Any) -> Any:
    """Prevent spreadsheet programs from executing client text as a formula."""
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    return "'" + value if stripped.startswith(_FORMULA_PREFIXES) else value


def safe_csv_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in result.select_dtypes(include=["object", "string"]).columns:
        result[column] = result[column].map(csv_safe_value)
    return result


def clear_client_session(session_state: Any) -> list[str]:
    """Remove known client-data objects from a Streamlit-like session mapping."""
    prefixes = ("locivra_", "pilot_")
    removed = []
    for key in list(session_state.keys()):
        if str(key).startswith(prefixes):
            removed.append(str(key))
            del session_state[key]
    return removed
