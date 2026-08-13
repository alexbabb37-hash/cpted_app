from pathlib import Path
import io
import sys
import time

import pandas as pd
import streamlit as st

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from locivra_core import data_provenance, data_quality_summary, geocode_address, portfolio_radius_sensitivity, reconcile_results, score_location, weight_sensitivity
from locivra_privacy import SAFE_CLIENT_COLUMNS, clear_client_session, inspect_client_frame, safe_csv_frame, validate_upload_size
from locivra_reports import build_portfolio_report

st.title("📂 Portfolio Priority Ranking")
st.caption("Rank a 5–20 location pilot portfolio for deeper security review.")

with st.expander("Upload format and responsible use"):
    st.markdown("""
Upload a CSV containing an **Address** column. Add Toronto, Ontario and a postal code where possible.
The same scoring method and analysis radius are applied to every successfully matched location.

The output sequences deeper review. It is not crime prediction, a safety certification, or a substitute
for internal incidents, operational knowledge, professional judgment, or site visits.
""")

template = pd.DataFrame({
    "Location ID": ["TOR-001", "TOR-002"],
    "Location Name": ["Downtown Store", "West Store"],
    "Address": ["100 Queen St W, Toronto, ON", "25 The West Mall, Toronto, ON"],
    "Location Type": ["Retail store", "Retail store"],
    "Annual Transactions": ["", ""],
    "Internal Incidents (12 months)": ["", ""],
    "Loss Amount (12 months)": ["", ""],
    "Guard Coverage": ["Unknown", "Unknown"],
    "CCTV Coverage": ["Unknown", "Unknown"],
    "Alarm Monitoring": ["Unknown", "Unknown"],
    "Client Notes": ["", ""],
})
st.download_button("Download CSV template", template.to_csv(index=False), "Locivra_Pilot_Template.csv", "text/csv")
authorized = st.checkbox("I am authorized to use this business-location data and confirm it contains no personal information, credentials, detailed incident narratives, photos or video.")
uploaded = st.file_uploader("Portfolio CSV", type=["csv"], disabled=not authorized)
radius = st.select_slider("Analysis radius for every location", options=[250, 500, 750, 1000], value=500, format_func=lambda x: f"{x} m")

if uploaded is not None:
    size_issues = validate_upload_size(getattr(uploaded, "size", None))
    if size_issues:
        st.error(size_issues[0])
        st.stop()
    try:
        input_df = pd.read_csv(uploaded)
    except Exception:
        st.error("The file could not be read as a CSV.")
        st.stop()
    if "Address" not in input_df.columns:
        st.error("The CSV needs a column named Address.")
        st.stop()
    privacy = inspect_client_frame(input_df, SAFE_CLIENT_COLUMNS)
    if privacy["blocking_issues"]:
        st.error("The upload was blocked by the client-data safeguard.")
        for issue in privacy["blocking_issues"]:
            st.warning(issue)
        st.stop()
    addresses = input_df["Address"].dropna().astype(str).map(str.strip)
    addresses = addresses[addresses.ne("")].drop_duplicates().tolist()
    if not addresses:
        st.error("No usable addresses were found.")
        st.stop()
    if len(addresses) > 20:
        st.error("This pilot workflow accepts up to 20 unique locations per run.")
        st.stop()
    if len(addresses) < 5:
        st.warning("The intended pilot size is 5–20 locations; you can still test a smaller file.")
    st.dataframe(pd.DataFrame({"Address": addresses}), hide_index=True, use_container_width=True)

    if st.button(f"Score {len(addresses)} locations", type="primary", use_container_width=True):
        progress = st.progress(0, text="Starting portfolio assessment…")
        results, failures = [], []
        indexed = input_df.copy()
        indexed["Address"] = indexed["Address"].astype(str).str.strip()
        indexed = indexed[indexed["Address"].isin(addresses)].drop_duplicates("Address")
        optional = [column for column in template.columns if column != "Address"]
        for index, (_, source_row) in enumerate(indexed.iterrows()):
            address = source_row["Address"]
            progress.progress(index / len(addresses), text=f"Matching {index + 1} of {len(addresses)}: {address}")
            try:
                lat, lon, match = geocode_address(address)
                client_data = {column: source_row[column] for column in optional if column in indexed.columns and pd.notna(source_row[column]) and str(source_row[column]).strip()}
                results.append(score_location(match, lat, lon, radius, include_context=False, submitted_address=address, location_id=client_data.get("Location ID", ""), client_data=client_data))
            except (ValueError, RuntimeError) as error:
                failures.append({"Address": address, "Reason": str(error)})
            if index < len(addresses) - 1:
                time.sleep(1.0)
        progress.progress(1.0, text="Portfolio assessment complete")
        st.session_state["locivra_portfolio"] = {"results": results, "failures": failures}

portfolio = st.session_state.get("locivra_portfolio")
if portfolio:
    results, failures = portfolio["results"], portfolio["failures"]
    if failures:
        with st.expander(f"{len(failures)} address(es) need attention", expanded=True):
            st.dataframe(pd.DataFrame(failures), hide_index=True, use_container_width=True)
    if not results:
        st.error("None of the submitted addresses could be scored.")
        st.stop()

    ranked = sorted(results, key=lambda item: item.overall_score, reverse=True)
    rows = []
    for rank, result in enumerate(ranked, 1):
        driver = max(result.categories.values(), key=lambda item: item.score * item.weight).category
        row = result.flat_row()
        row.update({"Rank": rank, "Primary Contributor": driver})
        rows.append(row)
    output = pd.DataFrame(rows)
    output["Portfolio Percentile"] = output["Overall Score"].rank(pct=True, method="average").mul(100).round(0).astype(int)
    total = len(output)
    output["Portfolio Tier"] = output["Rank"].map(lambda rank: "Tier 1 - Review first" if rank <= max(1, round(total * .25)) else ("Tier 2 - Secondary review" if rank <= max(2, round(total * .60)) else "Tier 3 - Monitor"))
    visible = output[["Rank", "Location ID", "Submitted Address", "Overall Score", "Portfolio Percentile", "Portfolio Tier", "Primary Contributor"]]
    st.subheader("Portfolio ranking")
    st.dataframe(visible, hide_index=True, use_container_width=True)
    st.caption("Rank order is relative to this submitted portfolio. Review category detail before making resource decisions.")

    audit = reconcile_results(ranked)
    if (audit["Status"] == "PASS").all():
        st.success(f"Calculation audit passed for all {len(ranked)} scored locations.")
    else:
        st.error("One or more scores failed reconciliation. Review the audit before using the ranking.")
    with st.expander("Calculation reconciliation"):
        st.dataframe(audit, hide_index=True, use_container_width=True)

    with st.expander("Ranking sensitivity", expanded=True):
        st.markdown("**Weight-profile sensitivity**")
        weight_frame = weight_sensitivity(ranked)
        st.dataframe(weight_frame, hide_index=True, use_container_width=True)
        st.markdown("**Radius sensitivity**")
        radius_frame = portfolio_radius_sensitivity(ranked)
        st.dataframe(radius_frame, hide_index=True, use_container_width=True)
        st.caption("Rank change is measured against the submitted-radius ranking under the published weights. Alternative profiles and radii are stress tests, not preferred answers.")

    csv_buffer = io.StringIO()
    safe_csv_frame(output).to_csv(csv_buffer, index=False)
    a, b = st.columns(2)
    a.download_button("Download detailed CSV", csv_buffer.getvalue(), "Locivra_Portfolio_Ranking.csv", "text/csv", use_container_width=True)
    pdf = build_portfolio_report(ranked)
    b.download_button("Download polished PDF report", pdf.getvalue(), "Locivra_Portfolio_Report.pdf", "application/pdf", use_container_width=True)
    if st.button("Clear portfolio client data from this session"):
        clear_client_session(st.session_state)
        st.success("Portfolio session data cleared. Downloaded files are not affected.")

with st.expander("Data provenance"):
    st.dataframe(pd.DataFrame([data_provenance()]), hide_index=True, use_container_width=True)
    quality = data_quality_summary()
    st.dataframe(quality["files"], hide_index=True, use_container_width=True)
    for warning in quality["warnings"]:
        st.warning(warning)
