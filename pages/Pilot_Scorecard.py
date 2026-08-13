from pathlib import Path
import sys

import pandas as pd
import streamlit as st

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from locivra_core import data_provenance
from locivra_pilot import DEFAULT_TARGETS, EVIDENCE_OUTCOMES, YES_NO_ASSESSED, CONTROL_OUTCOMES, calculate_pilot_scorecard, empty_review_template, validate_review_frame
from locivra_privacy import clear_client_session, inspect_client_frame, safe_csv_frame, validate_upload_size
from locivra_reports import build_pilot_scorecard_report

st.title("📋 Pilot Results Scorecard")
st.caption("Measure whether Locivra improved a real portfolio decision—without inventing savings or claiming crime reduction.")

with st.expander("How to use this scorecard", expanded=True):
    st.markdown("""
1. Lock the organization's priority order before showing Locivra results.
2. Review each location against internal incidents, losses, practitioner knowledge and known controls.
3. Record evidence outcomes honestly: **Confirmed, Partly supported, Challenged or Unresolved**.
4. Agree on the success targets before closing the pilot.

Agreement is not predictive accuracy. A challenged result can still be useful when it exposes missing data, a model assumption or operating context that changes the decision.
""")

template = empty_review_template(10)
st.download_button("Download evidence-review CSV template", template.to_csv(index=False), "Locivra_Pilot_Evidence_Review.csv", "text/csv")
authorized = st.checkbox("I am authorized to use this validation data and confirm it contains no personal information, credentials or detailed incident narratives.")
uploaded = st.file_uploader("Upload completed evidence-review CSV (optional)", type=["csv"], disabled=not authorized)
if uploaded is not None:
    size_issues = validate_upload_size(getattr(uploaded, "size", None))
    if size_issues:
        st.error(size_issues[0])
        st.stop()
    try:
        starting = pd.read_csv(uploaded).fillna("")
    except Exception:
        st.error("The uploaded file could not be read as a CSV.")
        st.stop()
    privacy = inspect_client_frame(starting, set(template.columns))
    if privacy["blocking_issues"]:
        st.error("The upload was blocked by the client-data safeguard.")
        for issue in privacy["blocking_issues"]:
            st.warning(issue)
        st.stop()
else:
    starting = st.session_state.get("pilot_review_frame", template)

# Streamlit's DateColumn requires datetime-compatible values. Blank templates and
# CSV imports otherwise arrive as strings, which makes the editor reject them.
starting = starting.copy()
if "Review date" in starting.columns:
    starting["Review date"] = pd.to_datetime(starting["Review date"], errors="coerce")

st.subheader("Evidence review")
column_config = {
    "Evidence outcome": st.column_config.SelectboxColumn(options=list(EVIDENCE_OUTCOMES)),
    "Known controls explain difference?": st.column_config.SelectboxColumn(options=list(CONTROL_OUTCOMES)),
    "Priority changed?": st.column_config.SelectboxColumn(options=list(YES_NO_ASSESSED)),
    "Overlooked site surfaced?": st.column_config.SelectboxColumn(options=list(YES_NO_ASSESSED)),
    "Explanation clear?": st.column_config.SelectboxColumn(options=list(YES_NO_ASSESSED)),
    "Next action clear?": st.column_config.SelectboxColumn(options=list(YES_NO_ASSESSED)),
    "Largest sensitivity rank move": st.column_config.NumberColumn(min_value=0, step=1),
    "Review date": st.column_config.DateColumn(format="YYYY-MM-DD"),
}
review = st.data_editor(starting, num_rows="dynamic", hide_index=True, use_container_width=True, column_config=column_config, key="pilot_editor")
st.session_state["pilot_review_frame"] = review

st.subheader("Measured effort and agreed targets")
a, b = st.columns(2)
baseline_minutes = a.number_input("Current-process portfolio triage minutes", min_value=0.0, value=0.0, step=15.0, help="Actual time required to create the initial review sequence without Locivra.")
assisted_minutes = b.number_input("Locivra-assisted portfolio triage minutes", min_value=0.0, value=0.0, step=15.0, help="Actual time using Locivra, including review of its outputs.")

with st.expander("Jointly agreed success targets"):
    c1, c2, c3, c4, c5 = st.columns(5)
    minimum = c1.number_input("Minimum reviews", min_value=1, max_value=20, value=int(DEFAULT_TARGETS["minimum_completed_reviews"]))
    support_target = c2.number_input("Evidence support (%)", min_value=0, max_value=100, value=int(DEFAULT_TARGETS["weighted_evidence_support_rate"] * 100)) / 100
    clarity_target = c3.number_input("Explanation clarity (%)", min_value=0, max_value=100, value=int(DEFAULT_TARGETS["explanation_clarity_rate"] * 100)) / 100
    action_target = c4.number_input("Actionability (%)", min_value=0, max_value=100, value=int(DEFAULT_TARGETS["actionability_rate"] * 100)) / 100
    sensitivity_target = c5.number_input("Median rank move max", min_value=0.0, max_value=20.0, value=float(DEFAULT_TARGETS["maximum_median_sensitivity_move"]), step=1.0)

issues = validate_review_frame(review)
if issues and issues != ["No reviewed locations were supplied."]:
    for issue in issues:
        st.error(issue)
    st.stop()

targets = {
    "minimum_completed_reviews": minimum,
    "weighted_evidence_support_rate": support_target,
    "explanation_clarity_rate": clarity_target,
    "actionability_rate": action_target,
    "maximum_median_sensitivity_move": sensitivity_target,
}
scorecard = calculate_pilot_scorecard(review, baseline_minutes or None, assisted_minutes if baseline_minutes else None, targets)

st.subheader("Pilot result")
if scorecard.recommendation == "EXPANSION CASE":
    st.success(f"**{scorecard.recommendation}** — {scorecard.recommendation_reason}")
elif scorecard.recommendation == "CONTINUE VALIDATION":
    st.info(f"**{scorecard.recommendation}** — {scorecard.recommendation_reason}")
else:
    st.warning(f"**{scorecard.recommendation}** — {scorecard.recommendation_reason}")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Reviewed", scorecard.completed_reviews, delta=f"Target {minimum}")
k2.metric("Evidence support", f"{scorecard.weighted_evidence_support_rate:.0%}", delta=scorecard.evidence_support_status)
k3.metric("Priorities changed", scorecard.priorities_changed)
k4.metric("Overlooked surfaced", scorecard.overlooked_sites_surfaced)
k5.metric("Minutes returned", "Not measured" if scorecard.minutes_returned is None else f"{scorecard.minutes_returned:.0f}")

summary = pd.DataFrame([
    {"Measure": "Completed reviews", "Result": scorecard.completed_reviews, "Target": minimum, "Status": scorecard.completed_review_status},
    {"Measure": "Weighted evidence support", "Result": f"{scorecard.weighted_evidence_support_rate:.0%}", "Target": f"{support_target:.0%}", "Status": scorecard.evidence_support_status},
    {"Measure": "Explanation clarity", "Result": f"{scorecard.explanation_clarity_rate:.0%}", "Target": f"{clarity_target:.0%}", "Status": scorecard.explanation_clarity_status},
    {"Measure": "Actionability", "Result": f"{scorecard.actionability_rate:.0%}", "Target": f"{action_target:.0%}", "Status": scorecard.actionability_status},
    {"Measure": "Median sensitivity rank move", "Result": "Not assessed" if scorecard.median_sensitivity_move is None else f"{scorecard.median_sensitivity_move:.1f}", "Target": f"≤ {sensitivity_target:.1f}", "Status": scorecard.sensitivity_status},
])
st.dataframe(summary, hide_index=True, use_container_width=True)

completed_csv = safe_csv_frame(review).to_csv(index=False)
pdf = build_pilot_scorecard_report(scorecard, review, targets)
d1, d2 = st.columns(2)
d1.download_button("Download completed evidence CSV", completed_csv, "Locivra_Pilot_Evidence_Review_Completed.csv", "text/csv", use_container_width=True)
d2.download_button("Download executive pilot scorecard PDF", pdf.getvalue(), "Locivra_Pilot_Results_Scorecard.pdf", "application/pdf", use_container_width=True)
if st.button("Clear pilot client data from this session"):
    clear_client_session(st.session_state)
    st.success("Pilot session data cleared. Downloaded files are not affected.")

with st.expander("Data and use boundary"):
    st.dataframe(pd.DataFrame([data_provenance()]), hide_index=True, use_container_width=True)
    st.caption("Time returned is measured process time, not a dollar-savings or risk-reduction claim. No crime-reduction claim is made without longitudinal client outcome data.")
