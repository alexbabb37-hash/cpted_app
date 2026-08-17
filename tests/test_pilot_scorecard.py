import pandas as pd

from locivra_pilot import calculate_pilot_scorecard, empty_review_template, validate_review_frame
from locivra_reports import build_pilot_scorecard_report


def completed_review():
    rows = []
    outcomes = ["Confirmed"] * 7 + ["Partly supported"] * 2 + ["Challenged"]
    for index, outcome in enumerate(outcomes, 1):
        rows.append({
            "Location ID": f"VAL-{index:03}",
            "Evidence outcome": outcome,
            "Priority changed?": "Yes" if index <= 3 else "No",
            "Overlooked site surfaced?": "Yes" if index == 1 else "No",
            "Explanation clear?": "Yes" if index <= 9 else "No",
            "Next action clear?": "Yes" if index <= 9 else "No",
            "Largest sensitivity rank move": 1 if index <= 8 else 2,
        })
    return pd.DataFrame(rows)


def test_scorecard_reconciles_rates_and_time():
    result = calculate_pilot_scorecard(completed_review(), 240, 120)
    assert result.completed_reviews == 10
    assert result.weighted_evidence_support_rate == 0.8
    assert result.explanation_clarity_rate == 0.9
    assert result.actionability_rate == 0.9
    assert result.minutes_returned == 120
    assert result.time_reduction_rate == 0.5
    assert result.recommendation == "EXPANSION CASE"


def test_incomplete_validation_cannot_be_called_expansion_case():
    frame = completed_review().iloc[:5]
    result = calculate_pilot_scorecard(frame)
    assert result.completed_review_status == "NOT YET"
    assert result.recommendation == "CONTINUE VALIDATION"


def test_template_and_validation_are_compatible():
    template = empty_review_template(10)
    assert validate_review_frame(template) == ["No reviewed locations were supplied."]


def test_blank_template_review_dates_can_be_normalized_for_streamlit():
    template = empty_review_template(10)
    template["Review date"] = pd.to_datetime(template["Review date"], errors="coerce")
    assert pd.api.types.is_datetime64_any_dtype(template["Review date"])
    assert template["Review date"].isna().all()


def test_pilot_pdf_generates_from_shared_calculation():
    frame = completed_review()
    scorecard = calculate_pilot_scorecard(frame, 240, 120)
    pdf = build_pilot_scorecard_report(scorecard, frame, {
        "minimum_completed_reviews": 10,
        "weighted_evidence_support_rate": .7,
        "explanation_clarity_rate": .8,
        "actionability_rate": .8,
        "maximum_median_sensitivity_move": 2,
    })
    assert len(pdf.getvalue()) > 10_000
