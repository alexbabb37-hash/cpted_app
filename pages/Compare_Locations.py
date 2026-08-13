from pathlib import Path
import sys

import pandas as pd
import streamlit as st

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from locivra_core import CRIME_WEIGHTS, comparison_explanation, comparison_interpretation, data_provenance, data_quality_summary, geocode_address, radius_sensitivity, reconcile_results, score_location, temporal_trends, weight_sensitivity
from locivra_reports import build_comparison_report

st.title("📊 Compare Locations")
st.caption("Compare two Toronto locations using the same radius, data, weights, and baseline.")

with st.expander("How to interpret this comparison"):
    st.write("The higher score indicates which location should be reviewed first. It does not prove that one location is safe or unsafe, and it does not predict future crime.")

col1, col2 = st.columns(2)
with col1:
    address1 = st.text_input("Location 1", placeholder="100 Queen St W, Toronto, ON")
with col2:
    address2 = st.text_input("Location 2", placeholder="200 Front St W, Toronto, ON")
radius = st.select_slider("Analysis radius", options=[250, 500, 750, 1000], value=500, format_func=lambda x: f"{x} m")

if st.button("Compare locations", type="primary", use_container_width=True):
    if not address1.strip() or not address2.strip():
        st.warning("Enter both Toronto addresses to continue.")
        st.stop()
    try:
        with st.spinner("Locating and comparing both sites…"):
            coordinates = [geocode_address(address1), geocode_address(address2)]
            submitted = [address1, address2]
            results = [score_location(match, lat, lon, radius, submitted_address=submitted[index]) for index, (lat, lon, match) in enumerate(coordinates)]
    except (ValueError, RuntimeError) as error:
        st.error(str(error))
        st.stop()
    st.session_state["locivra_comparison"] = results

results = st.session_state.get("locivra_comparison")
if results:
    first, second = results
    decision = comparison_interpretation(first, second)
    explanation = comparison_explanation(first, second)
    st.subheader("Decision summary")
    st.info(f"**{decision['strength']} ({decision['difference']:.1f} points).** {decision['guidance']}")
    st.write(explanation["summary"])

    c1, c2 = st.columns(2)
    for column, result, label in ((c1, first, "Location 1"), (c2, second, "Location 2")):
        with column:
            st.metric(label, f"{result.overall_score:.1f}/100")
            st.caption(result.priority_label)
            st.write(f"Submitted: **{result.submitted_address or result.address}**")
            st.caption(f"Matched: {result.address}")

    rows = []
    for category in CRIME_WEIGHTS:
        first_item, second_item = first.categories[category], second.categories[category]
        rows.append({
            "Crime category": category,
            "Weight": f"{CRIME_WEIGHTS[category]:.0%}",
            "Location 1 score": first_item.score,
            "Location 1 contribution": first_item.contribution,
            "Location 1 incidents": first_item.raw_incidents,
            "Location 2 score": second_item.score,
            "Location 2 contribution": second_item.contribution,
            "Location 2 incidents": second_item.raw_incidents,
        })
    comparison = pd.DataFrame(rows)
    contribution_chart = comparison.set_index("Crime category")[["Location 1 contribution", "Location 2 contribution"]]
    st.subheader("What creates the difference")
    st.bar_chart(contribution_chart, horizontal=True)
    st.dataframe(comparison, hide_index=True, use_container_width=True)
    st.caption("Contribution equals category score multiplied by its published model weight. Compare the pattern, not only the composite score.")
    audit = reconcile_results(results)
    if (audit["Status"] == "PASS").all():
        st.success("Both composite scores passed automated reconciliation.")
    else:
        st.error("At least one score failed reconciliation. Review the audit table before using the comparison.")
    with st.expander("Calculation audit"):
        st.dataframe(audit, hide_index=True, use_container_width=True)

    with st.expander("Radius sensitivity", expanded=True):
        first_sensitivity = radius_sensitivity(first.address, first.latitude, first.longitude)
        second_sensitivity = radius_sensitivity(second.address, second.latitude, second.longitude)
        sensitivity = pd.concat([first_sensitivity.assign(Location="Location 1"), second_sensitivity.assign(Location="Location 2")])
        chart = sensitivity.pivot(index="Radius (m)", columns="Location", values="Priority score")
        st.line_chart(chart)
        gaps = chart["Location 1"] - chart["Location 2"]
        if (gaps.abs() < 3).any() or (gaps.min() < 0 < gaps.max()):
            st.warning("The ordering is sensitive to the selected radius. Treat the locations as a close or assumption-dependent comparison.")
        else:
            st.success("The ordering remains consistent across the tested radii, providing a more stable first-pass comparison.")
        st.caption("This tests whether the comparison remains stable when the analysis boundary changes. It is not a forecast.")

    with st.expander("Weight-profile sensitivity", expanded=True):
        weights = weight_sensitivity(results)
        st.dataframe(weights, hide_index=True, use_container_width=True)
        st.caption("Alternative weighting profiles are disclosed stress tests. They show whether the review order depends on the published retail weights.")

    with st.expander("Historical direction", expanded=True):
        trend_results = [temporal_trends(item.latitude, item.longitude, item.radius_metres) for item in results]
        trend_rows = []
        for label, trend in zip(("Location 1", "Location 2"), trend_results):
            for row in trend["comparisons"].to_dict("records"):
                trend_rows.append({"Location": label, **row})
        st.dataframe(pd.DataFrame(trend_rows), hide_index=True, use_container_width=True)
        st.caption(f"Equal rolling windows anchored to {trend_results[0]['cutoff']}. Changes describe history and do not forecast future incidents.")

    with st.expander("Environmental and neighbourhood context"):
        context_rows = []
        for label, result in (("Location 1", first), ("Location 2", second)):
            context = result.context
            context_rows.append({
                "Location": label,
                "Nearest TTC": context.get("nearest_ttc_station", "Not available"),
                "TTC distance (m)": context.get("ttc_distance_metres", "—"),
                "Parks in radius": context.get("parks_within_radius", "—"),
                "Street-light poles": context.get("street_light_poles_within_radius", "—"),
                "Approximate neighbourhood": context.get("approximate_neighbourhood", "Not available"),
            })
        st.dataframe(pd.DataFrame(context_rows), hide_index=True, use_container_width=True)
        st.caption("Context only. These environmental values do not affect the current score.")

    pdf = build_comparison_report(results)
    st.download_button("Download polished comparison PDF", pdf.getvalue(), "Locivra_Location_Comparison.pdf", "application/pdf", use_container_width=True)

with st.expander("Data provenance"):
    st.dataframe(pd.DataFrame([data_provenance()]), hide_index=True, use_container_width=True)
    quality = data_quality_summary()
    st.dataframe(quality["files"], hide_index=True, use_container_width=True)
    for warning in quality["warnings"]:
        st.warning(warning)
