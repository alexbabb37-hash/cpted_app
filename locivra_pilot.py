"""Shared formulas and decision rules for Locivra pilot validation results."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any

import pandas as pd

EVIDENCE_OUTCOMES = ("Confirmed", "Partly supported", "Challenged", "Unresolved")
YES_NO_ASSESSED = ("Yes", "No", "Not assessed")
CONTROL_OUTCOMES = ("Yes", "Partly", "No", "Unknown")
REQUIRED_REVIEW_COLUMNS = {
    "Location ID",
    "Evidence outcome",
    "Priority changed?",
    "Overlooked site surfaced?",
    "Explanation clear?",
    "Next action clear?",
}
DEFAULT_TARGETS = {
    "minimum_completed_reviews": 10,
    "weighted_evidence_support_rate": 0.70,
    "explanation_clarity_rate": 0.80,
    "actionability_rate": 0.80,
    "maximum_median_sensitivity_move": 2.0,
}


@dataclass(frozen=True)
class PilotScorecard:
    completed_reviews: int
    confirmed: int
    partly_supported: int
    challenged: int
    unresolved: int
    weighted_evidence_support_rate: float
    priorities_changed: int
    overlooked_sites_surfaced: int
    explanation_clarity_rate: float
    actionability_rate: float
    baseline_triage_minutes: float | None
    locivra_triage_minutes: float | None
    minutes_returned: float | None
    time_reduction_rate: float | None
    median_sensitivity_move: float | None
    completed_review_status: str
    evidence_support_status: str
    explanation_clarity_status: str
    actionability_status: str
    sensitivity_status: str
    recommendation: str
    recommendation_reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def empty_review_template(rows: int = 10) -> pd.DataFrame:
    columns = [
        "Location ID", "Location name", "Pre rank", "Locivra rank",
        "Evidence outcome", "Evidence reviewed", "Why confirmed / challenged",
        "Known controls explain difference?", "Priority changed?",
        "Overlooked site surfaced?", "Explanation clear?", "Next action clear?",
        "Largest sensitivity rank move", "Reviewer", "Review date",
        "Action / validation question",
    ]
    return pd.DataFrame([{column: "" for column in columns} for _ in range(rows)])


def validate_review_frame(frame: pd.DataFrame) -> list[str]:
    issues = []
    missing = sorted(REQUIRED_REVIEW_COLUMNS - set(frame.columns))
    if missing:
        issues.append("Missing required columns: " + ", ".join(missing))
        return issues
    used = frame[frame["Location ID"].fillna("").astype(str).str.strip().ne("")].copy()
    if used.empty:
        issues.append("No reviewed locations were supplied.")
        return issues
    invalid_evidence = sorted(set(used["Evidence outcome"].dropna().astype(str).str.strip()) - set(EVIDENCE_OUTCOMES) - {""})
    if invalid_evidence:
        issues.append("Invalid evidence outcomes: " + ", ".join(invalid_evidence))
    for column in ("Priority changed?", "Overlooked site surfaced?", "Explanation clear?", "Next action clear?"):
        invalid = sorted(set(used[column].dropna().astype(str).str.strip()) - set(YES_NO_ASSESSED) - {""})
        if invalid:
            issues.append(f"Invalid values in {column}: " + ", ".join(invalid))
    if "Largest sensitivity rank move" in used:
        numeric = pd.to_numeric(used["Largest sensitivity rank move"], errors="coerce")
        negative = numeric.dropna().lt(0)
        if negative.any():
            issues.append("Sensitivity rank movement cannot be negative.")
    return issues


def _rate(frame: pd.DataFrame, column: str) -> float:
    values = frame[column].fillna("").astype(str).str.strip()
    assessed = values.isin(("Yes", "No"))
    return 0.0 if not assessed.any() else float((values[assessed] == "Yes").mean())


def calculate_pilot_scorecard(
    review_frame: pd.DataFrame,
    baseline_triage_minutes: float | None = None,
    locivra_triage_minutes: float | None = None,
    targets: dict[str, float] | None = None,
) -> PilotScorecard:
    issues = validate_review_frame(review_frame)
    if issues and issues != ["No reviewed locations were supplied."]:
        raise ValueError("; ".join(issues))
    targets = {**DEFAULT_TARGETS, **(targets or {})}
    frame = review_frame[review_frame.get("Location ID", pd.Series(dtype=object)).fillna("").astype(str).str.strip().ne("")].copy()
    outcomes = frame.get("Evidence outcome", pd.Series(dtype=object)).fillna("").astype(str).str.strip()
    completed = int(outcomes.isin(EVIDENCE_OUTCOMES).sum())
    confirmed = int((outcomes == "Confirmed").sum())
    partly = int((outcomes == "Partly supported").sum())
    challenged = int((outcomes == "Challenged").sum())
    unresolved = int((outcomes == "Unresolved").sum())
    support = 0.0 if completed == 0 else (confirmed + 0.5 * partly) / completed
    priorities_changed = int((frame.get("Priority changed?", pd.Series(dtype=object)).fillna("").astype(str).str.strip() == "Yes").sum())
    overlooked = int((frame.get("Overlooked site surfaced?", pd.Series(dtype=object)).fillna("").astype(str).str.strip() == "Yes").sum())
    clarity = _rate(frame, "Explanation clear?") if not frame.empty else 0.0
    actionability = _rate(frame, "Next action clear?") if not frame.empty else 0.0
    sensitivity = pd.to_numeric(frame.get("Largest sensitivity rank move", pd.Series(dtype=float)), errors="coerce").dropna()
    median_sensitivity = None if sensitivity.empty else float(sensitivity.median())

    baseline = None if baseline_triage_minutes in (None, 0) else float(baseline_triage_minutes)
    assisted = None if locivra_triage_minutes is None else float(locivra_triage_minutes)
    if baseline is not None and assisted is not None:
        minutes_returned = baseline - assisted
        reduction = minutes_returned / baseline
    else:
        minutes_returned = reduction = None

    complete_status = "PASS" if completed >= targets["minimum_completed_reviews"] else "NOT YET"
    support_status = "PASS" if support >= targets["weighted_evidence_support_rate"] else "REFINE"
    clarity_status = "PASS" if clarity >= targets["explanation_clarity_rate"] else "REFINE"
    action_status = "PASS" if actionability >= targets["actionability_rate"] else "REFINE"
    sensitivity_status = "NOT ASSESSED" if median_sensitivity is None else ("PASS" if median_sensitivity <= targets["maximum_median_sensitivity_move"] else "REVIEW")

    if complete_status != "PASS":
        recommendation = "CONTINUE VALIDATION"
        reason = "Fewer than the agreed minimum locations have documented evidence outcomes."
    elif support_status == clarity_status == action_status == "PASS" and sensitivity_status in ("PASS", "NOT ASSESSED"):
        recommendation = "EXPANSION CASE"
        reason = "Evidence support, explanation clarity and actionability meet the agreed targets. Review challenged cases and any unassessed sensitivity before expansion."
    else:
        recommendation = "REFINE BEFORE EXPANSION"
        failed = [name for name, status in (("evidence support", support_status), ("explanation clarity", clarity_status), ("actionability", action_status), ("assumption sensitivity", sensitivity_status)) if status in ("REFINE", "REVIEW")]
        reason = "One or more agreed usefulness tests require attention: " + ", ".join(failed) + "."

    return PilotScorecard(
        completed, confirmed, partly, challenged, unresolved, round(support, 4),
        priorities_changed, overlooked, round(clarity, 4), round(actionability, 4),
        baseline, assisted, None if minutes_returned is None else round(minutes_returned, 1),
        None if reduction is None else round(reduction, 4), median_sensitivity,
        complete_status, support_status, clarity_status, action_status,
        sensitivity_status, recommendation, reason,
    )
