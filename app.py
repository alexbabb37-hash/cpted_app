from pathlib import Path

import pandas as pd
import streamlit as st

from locivra_core import CRIME_WEIGHTS, data_provenance, data_quality_summary

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Locivra", page_icon="📍", layout="wide")

logo = ROOT / "locivra_logo_report.png"
if logo.exists():
    st.image(str(logo), width=155)

st.title("Location intelligence for smarter security decisions")
st.write("Locivra helps multi-location organizations identify which Toronto locations warrant deeper security review using historical reported-crime exposure and location context.")
st.info("Locivra supports prioritization. It does not predict crime, determine whether a location is safe, or replace professional site review.")

st.subheader("Choose a workflow")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("### Assess one location")
    st.write("Understand the score, its category contributions, evidence map, and sensitivity to radius.")
with c2:
    st.markdown("### Compare locations")
    st.write("Use one consistent method to explain which location warrants review first and why.")
with c3:
    st.markdown("### Rank a portfolio")
    st.write("Upload 5-20 locations, review relative tiers, and download an evidence-backed executive report.")
st.caption("Open a workflow from the sidebar.")

st.subheader("What is included")
st.markdown("""
- Five published crime-category weights totaling 100%
- Geodesic distance and distance-weighted exposure
- A transparent citywide prototype baseline
- Portfolio-relative tiers and percentiles
- Real historical incident maps and radius sensitivity
- Optional client evidence kept separate from the public-data score
""")

left, right = st.columns(2)
with left:
    st.markdown("#### Data provenance")
    st.dataframe(pd.DataFrame([data_provenance()]), hide_index=True, use_container_width=True)
    quality = data_quality_summary()
    st.dataframe(quality["files"], hide_index=True, use_container_width=True)
    for warning in quality["warnings"]:
        st.warning(warning)
with right:
    st.markdown("#### Published category weights")
    st.dataframe(pd.DataFrame([{"Category": category, "Weight": f"{weight:.0%}"} for category, weight in CRIME_WEIGHTS.items()]), hide_index=True, use_container_width=True)
