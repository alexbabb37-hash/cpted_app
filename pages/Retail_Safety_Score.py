from pathlib import Path
import sys

import pandas as pd
import streamlit as st

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from locivra_core import CRIME_WEIGHTS, WEIGHT_PROFILES, METHODOLOGY_VERSION, data_provenance, data_quality_summary, geocode_address, nearby_incidents, radius_sensitivity, reconcile_location_result, result_warnings, score_location, score_under_weights, temporal_trends
from locivra_reports import build_site_report

st.title("🏪 Location Priority Assessment")
st.caption("Decision support for prioritizing deeper security review across Toronto locations.")

with st.expander("Methodology and responsible use"):
    st.markdown(f"""
**{METHODOLOGY_VERSION}** uses five Toronto Police Service historical incident datasets. It measures
distance-weighted exposure inside the selected radius, compares it with a transparent citywide
baseline, and combines category scores using published retail-relevance weights.

Environmental information is displayed as **context only** and does not change the score.
This is not crime prediction, a safety certification, or a replacement for internal incidents,
professional judgment, CPTED assessment, or a physical site visit.
""")

left, right = st.columns([3, 1])
with left:
    address = st.text_input("Toronto location", placeholder="100 Queen St W, Toronto, ON")
with right:
    radius = st.selectbox("Analysis radius", [250, 500, 750, 1000], index=1, format_func=lambda x: f"{x} m")

if st.button("Assess location", type="primary", use_container_width=True):
    if not address.strip():
        st.warning("Enter a Toronto address to continue.")
        st.stop()
    try:
        with st.spinner("Locating and assessing the site…"):
            latitude, longitude, matched_address = geocode_address(address)
            result = score_location(matched_address, latitude, longitude, radius, submitted_address=address)
    except (ValueError, RuntimeError) as error:
        st.error(str(error))
        st.stop()

    st.session_state["locivra_site_result"] = result

result = st.session_state.get("locivra_site_result")
if result:
    st.subheader("Assessment result")
    c1, c2, c3 = st.columns(3)
    c1.metric("Priority score", f"{result.overall_score:.1f}/100")
    c2.metric("Review priority", result.priority_label.replace(" review priority", ""))
    c3.metric("Radius", f"{result.radius_metres} m")
    st.caption(f"Submitted: {result.submitted_address or result.address}  |  Matched: {result.address}")

    rows = []
    for category, item in result.categories.items():
        rows.append({
            "Crime category": category,
            "Raw incidents": item.raw_incidents,
            "Distance-weighted exposure": item.weighted_exposure,
            "Category score": item.score,
            "Model weight": f"{item.weight:.0%}",
            "Contribution": item.contribution,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    audit = reconcile_location_result(result)
    if audit["Status"] == "PASS":
        st.success(f"Calculation audit passed. Recalculated score: {audit['Recalculated score']:.1f}; display rounding difference: {audit['Display rounding difference']:+.1f} points.")
    else:
        st.error(f"Calculation audit requires review: {audit['Issues']}")
    for warning in result_warnings(result):
        st.warning(warning)

    st.subheader("Evidence map")
    points = nearby_incidents(result.latitude, result.longitude, result.radius_metres)
    st.map(points[["latitude", "longitude"]], use_container_width=True)
    st.caption(f"{len(points):,} displayed historical incident points inside the selected radius. Dense results are deterministically sampled for performance; scoring uses all records.")

    with st.expander("Radius sensitivity", expanded=True):
        sensitivity = radius_sensitivity(result.address, result.latitude, result.longitude)
        st.line_chart(sensitivity.set_index("Radius (m)")["Priority score"])
        st.dataframe(sensitivity, hide_index=True, use_container_width=True)
        st.caption("A result that remains elevated across several radii is a more stable review signal. This is historical sensitivity analysis, not a forecast.")

    with st.expander("Weight-profile sensitivity"):
        weight_rows = [{"Weight profile": name, "Recombined score": score_under_weights(result, profile)} for name, profile in WEIGHT_PROFILES.items()]
        st.dataframe(pd.DataFrame(weight_rows), hide_index=True, use_container_width=True)
        st.caption("These are disclosed stress tests using the same category scores. They do not replace the published profile.")

    st.subheader("Historical direction")
    with st.spinner("Calculating equal-window historical comparisons…"):
        trends = temporal_trends(result.latitude, result.longitude, result.radius_metres)
    st.caption(f"Anchored to the newest configured report date: {trends['cutoff']}. Exposure combines distance decay and the published category weights.")
    metrics = st.columns(2)
    for column, (_, trend_row) in zip(metrics, trends["comparisons"].iterrows()):
        change = trend_row["Exposure change (%)"]
        delta = "Percentage withheld" if pd.isna(change) else f"{change:+.1f}% weighted exposure"
        column.metric(trend_row["Period"], f"{trend_row['Current exposure']:.1f}", delta)
        raw_change = trend_row["Count change (%)"]
        raw_text = "withheld" if pd.isna(raw_change) else f"{raw_change:+.1f}%"
        column.caption(f"Raw incidents: {trend_row['Current incidents']} current vs {trend_row['Previous incidents']} prior ({raw_text}). {trend_row['Stability note']}.")
    monthly = trends["monthly"].set_index("Month")
    st.line_chart(monthly["Exposure"])
    with st.expander("Category-level 12-month changes"):
        st.dataframe(trends["categories"], hide_index=True, use_container_width=True)
    st.caption("These are descriptive historical changes, not forecasts. Percentages are withheld when the prior exposure baseline is too small.")

    drivers = sorted(result.categories.values(), key=lambda item: item.contribution, reverse=True)[:3]
    st.subheader("What to examine next")
    st.write("Use these strongest contributors as questions for internal validation and a professional site review:")
    for item in drivers:
        st.markdown(f"- **{item.category}:** contributes **{item.contribution:.1f} points** to the overall score ({item.score:.1f}/100 category score × {item.weight:.0%} weight), based on {item.raw_incidents} incidents in the selected radius")

    with st.expander("Environmental and neighbourhood context", expanded=True):
        context = result.context
        st.caption(context.get("note", "Context only; not included in the score."))
        a, b, c = st.columns(3)
        a.metric("Nearest TTC", context.get("nearest_ttc_station", "Not available"))
        b.metric("Parks in radius", context.get("parks_within_radius", "—"))
        c.metric("Street-light poles", context.get("street_light_poles_within_radius", "—"))
        neighbourhood = context.get("approximate_neighbourhood", "Not available")
        population = context.get("approximate_neighbourhood_population")
        st.write(f"Approximate neighbourhood: **{neighbourhood}**" + (f" · Population: **{population:,}**" if population else ""))

    st.info("Next step: compare the result with internal incidents and staff knowledge. Select controls only after a qualified site-level review.")
    pdf = build_site_report(result)
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in result.address[:45]).strip("_")
    st.download_button("Download polished PDF assessment", pdf.getvalue(), f"Locivra_Assessment_{safe_name}.pdf", "application/pdf", use_container_width=True)

with st.expander("Published category weights"):
    st.dataframe(pd.DataFrame([{"Category": key, "Weight": f"{value:.0%}"} for key, value in CRIME_WEIGHTS.items()]), hide_index=True, use_container_width=True)

with st.expander("Data provenance"):
    st.dataframe(pd.DataFrame([data_provenance()]), hide_index=True, use_container_width=True)
    quality = data_quality_summary()
    st.dataframe(quality["files"], hide_index=True, use_container_width=True)
    for warning in quality["warnings"]:
        st.warning(warning)
