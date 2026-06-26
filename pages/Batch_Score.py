import streamlit as st
import pandas as pd
import time
from geopy.geocoders import Nominatim
import io
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

st.title("📂 Portfolio Risk Ranking")
st.write("Upload multiple store locations to identify which sites need security attention first.")
with st.expander("📚 Data & Methodology", expanded=False):
    st.markdown("""
RiskTerrain currently uses **Toronto Police Service Open Data**.

Crime categories analyzed:
- Assault
- Break & Enter
- Robbery
- Auto Theft
- Theft Over $5000

Scores are based on nearby incidents, crime category weighting, distance from the selected location, and comparison against broader Toronto patterns.

This tool is designed for **first-pass screening only** and does not replace a full CPTED assessment, site visit, internal incident data, or professional judgment.
""")

@st.cache_data
def load_data():
    assault = pd.read_csv("toronto_crime.csv")
    assault["CRIME_TYPE"] = "Assault"
    breakenter = pd.read_csv("breakenter.csv")
    breakenter["CRIME_TYPE"] = "Break & Enter"
    robbery = pd.read_csv("robbery.csv")
    robbery["CRIME_TYPE"] = "Robbery"
    autotheft = pd.read_csv("autotheft.csv")
    autotheft["CRIME_TYPE"] = "Auto Theft"
    theftover = pd.read_csv("theft_over.csv")
    theftover["CRIME_TYPE"] = "Theft Over $5000"
    all_crimes = pd.concat([assault, breakenter, robbery, autotheft, theftover], ignore_index=True)
    all_crimes = all_crimes[
        (all_crimes["LAT_WGS84"] > 43) & (all_crimes["LAT_WGS84"] < 44) &
        (all_crimes["LONG_WGS84"] > -80) & (all_crimes["LONG_WGS84"] < -79)
    ]
    return all_crimes

def calc_scores(df, lat, lon):
    radius = 0.005

    def get_nearby(crime_type):
        subset = df[df["CRIME_TYPE"] == crime_type]
        nearby = (
            ((subset["LAT_WGS84"] - lat) ** 2 +
             (subset["LONG_WGS84"] - lon) ** 2) ** 0.5
        ) < radius
        return nearby.sum()

    def calc_score(count, avg):
        ratio = count / max(avg, 1)
        score = min(100, ratio * 50)
        return round(score, 1)

    city_avg_be = len(df[df["CRIME_TYPE"] == "Break & Enter"]) / 140
    city_avg_assault = len(df[df["CRIME_TYPE"] == "Assault"]) / 140
    city_avg_robbery = len(df[df["CRIME_TYPE"] == "Robbery"]) / 140
    city_avg_auto = len(df[df["CRIME_TYPE"] == "Auto Theft"]) / 140
    city_avg_theft = len(df[df["CRIME_TYPE"] == "Theft Over $5000"]) / 140

    be = calc_score(get_nearby("Break & Enter"), city_avg_be)
    assault = calc_score(get_nearby("Assault"), city_avg_assault)
    robbery = calc_score(get_nearby("Robbery"), city_avg_robbery)
    auto = calc_score(get_nearby("Auto Theft"), city_avg_auto)
    theft = calc_score(get_nearby("Theft Over $5000"), city_avg_theft)

    overall = round(
        (theft * 0.30) +
        (be * 0.25) +
        (robbery * 0.25) +
        (assault * 0.15) +
        (auto * 0.05),
        1
    )

    def risk_label(s):
        if s >= 75:
            return "🔴 Critical"
        elif s >= 60:
            return "🟠 High"
        elif s >= 40:
            return "🟡 Moderate"
        else:
            return "🟢 Low"

    return {
        "Overall Score": overall,
        "Risk Level": risk_label(overall),
        "Theft Over $5000": theft,
        "Break & Enter": be,
        "Robbery": robbery,
        "Assault": assault,
        "Auto Theft": auto,
    }

def generate_portfolio_pdf(results_df):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=45,
        leftMargin=45,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    story = []

    total_locations = len(results_df)
    critical = results_df[results_df["Overall Score"] >= 75]
    high = results_df[(results_df["Overall Score"] >= 60) & (results_df["Overall Score"] < 75)]
    moderate = results_df[(results_df["Overall Score"] >= 40) & (results_df["Overall Score"] < 60)]
    low = results_df[results_df["Overall Score"] < 40]

    # Logo
    try:
        logo = Image("riskterrain_logo.png")
        logo.drawWidth = 170
        logo.drawHeight = 85
        story.append(logo)
    except:
        story.append(Paragraph("RiskTerrain™", styles["Title"]))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Portfolio Security Prioritization Report", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"<b>Report Date:</b> {date.today().strftime('%B %d, %Y')}", styles["Normal"]))
    story.append(Paragraph(f"<b>Locations Analyzed:</b> {total_locations}", styles["Normal"]))
    story.append(Spacer(1, 18))

    story.append(Paragraph("Executive Summary", styles["Heading1"]))

    story.append(Paragraph(
        f"{total_locations} locations were analyzed using Toronto Police Service Open Data. "
        f"{len(critical)} locations were identified as Critical Risk, {len(high)} as High Risk, "
        f"{len(moderate)} as Moderate Risk, and {len(low)} as Low Risk. "
        "This report helps identify which locations should receive security attention first.",
        styles["Normal"]
    ))

    story.append(Spacer(1, 14))

    key_decision = (
        f"<b>Key Decision:</b> Prioritize detailed site assessments for "
        f"{len(critical) + len(high)} Critical or High Risk location(s)."
    )

    decision_table = Table([[Paragraph(key_decision, styles["Normal"])]], colWidths=[500])
    decision_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef4ff")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#2563eb")),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))

    story.append(decision_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("Portfolio Overview", styles["Heading1"]))

    overview_data = [
        ["Risk Level", "Count"],
        ["Critical", len(critical)],
        ["High", len(high)],
        ["Moderate", len(moderate)],
        ["Low", len(low)],
    ]

    overview_table = Table(overview_data, colWidths=[260, 120])
    overview_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))

    story.append(overview_table)
    story.append(PageBreak())

    story.append(Paragraph("Top Priority Locations", styles["Heading1"]))

    top_priority = results_df[results_df["Overall Score"] >= 60].head(5)

    if len(top_priority) > 0:
        top_data = [["Rank", "Address", "Score", "Risk Level", "Next Step"]]

        rank = 1
        for _, row in top_priority.iterrows():
            top_data.append([
                str(rank),
                row["Address"],
                f"{row['Overall Score']}/100",
                row["Risk Level"].replace("🔴", "").replace("🟠", "").strip(),
                "Detailed Assessment"
            ])
            rank += 1

        top_table = Table(top_data, colWidths=[40, 190, 70, 90, 130])
        top_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))

        story.append(top_table)
        story.append(Spacer(1, 20))

    story.append(Paragraph("Portfolio Recommendations", styles["Heading1"]))

    if len(critical) > 0:
        story.append(Paragraph("Immediate Action Recommended", styles["Heading2"]))
        story.append(Paragraph(
            "The following locations should receive detailed Retail Safety Risk Assessments first. "
            "They were flagged because multiple crime categories contributed to elevated portfolio risk.",
            styles["Normal"]
        ))
        story.append(Spacer(1, 8))

        for _, row in critical.head(5).iterrows():
            drivers = []

            if row["Theft Over $5000"] >= 75:
                drivers.append("Theft Over $5000")
            if row["Break & Enter"] >= 75:
                drivers.append("Break & Enter")
            if row["Robbery"] >= 75:
                drivers.append("Robbery")
            if row["Assault"] >= 75:
                drivers.append("Assault")
            if row["Auto Theft"] >= 75:
                drivers.append("Auto Theft")

            driver_text = ", ".join(drivers) if drivers else "elevated overall risk indicators"

            story.append(Paragraph(
                f"<b>{row['Address']}</b> — {row['Overall Score']}/100<br/>"
                f"Flagged due to elevated {driver_text}.<br/>"
                f"<b>Next Step:</b> Generate a Detailed Site Assessment to identify CPTED vulnerabilities and site-specific recommendations.",
                styles["Normal"]
            ))
            story.append(Spacer(1, 10))

    if len(high) > 0:
        story.append(Paragraph("High Priority Monitoring", styles["Heading2"]))
        story.append(Paragraph(
            "High Risk locations should be reviewed as resources allow and may warrant additional security planning.",
            styles["Normal"]
        ))

    if len(moderate) > 0:
        story.append(Paragraph("Medium Priority", styles["Heading2"]))
        story.append(Paragraph(
            "Moderate Risk locations should be monitored and reviewed during routine security planning.",
            styles["Normal"]
        ))

    if len(low) > 0:
        story.append(Paragraph("Lower Priority Sites", styles["Heading2"]))
        story.append(Paragraph(
            "Low Risk locations do not require immediate action based on current available data, but should remain part of routine review.",
            styles["Normal"]
        ))

    story.append(PageBreak())

    story.append(Paragraph("Methodology & Limitations", styles["Heading1"]))

    story.append(Paragraph(
        "<b>Data Source:</b> Toronto Police Service Open Data.",
        styles["Normal"]
    ))

    story.append(Paragraph(
        "<b>Crime Categories:</b> Assault, Break & Enter, Robbery, Auto Theft, and Theft Over $5000.",
        styles["Normal"]
    ))

    story.append(Paragraph(
        "<b>Scoring Approach:</b> Scores are based on nearby crime incidents, category weighting, proximity, and relative comparison across Toronto locations.",
        styles["Normal"]
    ))

    story.append(Paragraph(
        "<b>Purpose:</b> This report is intended for first-pass portfolio prioritization.",
        styles["Normal"]
    ))

    story.append(Paragraph(
        "<b>Limitations:</b> This report should be used alongside professional judgment, internal incident data, CPTED assessments, and physical site visits.",
        styles["Normal"]
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


df = load_data()

st.header("How It Works")
st.write("1. Download the sample CSV template below")
st.write("2. Fill in your store addresses")
st.write("3. Upload it and click Score All Locations")
st.write("4. Download your ranked results")

sample_csv = "Address\n500 Yonge St, Toronto, Ontario\n2150 Pharmacy Ave, Toronto, Ontario\n1000 Bloor St W, Toronto, Ontario\n3401 Dufferin St, Toronto, Ontario\n2900 Warden Ave, Toronto, Ontario"

st.download_button(
    label="📥 Download Sample CSV Template",
    data=sample_csv,
    file_name="store_addresses_template.csv",
    mime="text/csv"
)

st.header("Upload Your Addresses")
uploaded_file = st.file_uploader("Upload CSV file", type="csv")

if uploaded_file:
    addresses_df = pd.read_csv(uploaded_file)
    st.write(f"Found **{len(addresses_df)}** addresses to score")
    st.dataframe(addresses_df.head(), use_container_width=True)

    if st.button("Score All Locations"):
        geolocator = Nominatim(user_agent="cpted_batch")
        results = []
        progress = st.progress(0)
        status = st.empty()

        for i, row in addresses_df.iterrows():
            address = row["Address"]
            status.write(f"Scoring {i+1} of {len(addresses_df)}: {address}")

            try:
                location = geolocator.geocode(address)
                if location:
                    scores = calc_scores(df, location.latitude, location.longitude)
                    results.append({
                        "Address": address,
                        **scores
                    })
                else:
                    results.append({
                        "Address": address,
                        "Overall Score": "Not found",
                        "Risk Level": "—",
                        "Theft Over $5000": "—",
                        "Break & Enter": "—",
                        "Robbery": "—",
                        "Assault": "—",
                        "Auto Theft": "—",
                    })
            except Exception as e:
                results.append({
                    "Address": address,
                    "Overall Score": "Error",
                    "Risk Level": "—",
                    "Theft Over $5000": "—",
                    "Break & Enter": "—",
                    "Robbery": "—",
                    "Assault": "—",
                    "Auto Theft": "—",
                })

            progress.progress((i + 1) / len(addresses_df))
            time.sleep(1)

        status.write("✅ All locations scored!")

        results_df = pd.DataFrame(results)
        results_df = results_df[results_df["Overall Score"] != "Not found"]
        results_df = results_df[results_df["Overall Score"] != "Error"]
        results_df["Overall Score"] = pd.to_numeric(results_df["Overall Score"])
        results_df = results_df.sort_values("Overall Score", ascending=False).reset_index(drop=True)

        st.header("Results — Ranked by Risk")
        st.dataframe(results_df, use_container_width=True)

        st.header("Top Priority Locations")

        top_locations = results_df[results_df["Overall Score"] >= 60].head(3)

        if len(top_locations) == 0:
            st.success("No Critical or High Risk priority locations identified in this upload.")

        for index, row in top_locations.iterrows():
            st.subheader(f"Priority #{index + 1}: {row['Address']}")
            st.write(f"**Overall Score:** {row['Overall Score']}/100")
            if row["Overall Score"] >= 85:
                confidence = "High"
            elif row["Overall Score"] >= 60:
                confidence = "Medium"
            else:
                confidence = "Preliminary"

            st.write(f"**Assessment Confidence:** {confidence}")
            st.caption(
                "Confidence reflects the strength of the available crime data and should be considered alongside professional judgment and site-specific factors."

            )
            st.write(f"**Risk Level:** {row['Risk Level']}")

            st.write("**Why this location is a priority:**")

            drivers = []

            if row["Theft Over $5000"] >= 75:
                drivers.append("High Theft Over $5000 risk")
            if row["Break & Enter"] >= 75:
                drivers.append("High Break & Enter risk")
            if row["Robbery"] >= 75:
                drivers.append("High Robbery risk")
            if row["Assault"] >= 75:
                drivers.append("High Assault risk")
            if row["Auto Theft"] >= 75:
                drivers.append("High Auto Theft risk")

            if drivers:
                for driver in drivers:
                    st.write(f"• {driver}")
            else:
                st.write("• Elevated overall score compared to other uploaded locations")

            st.write("**Component Scores:**")
            st.write(f"• Theft Over $5000: {row['Theft Over $5000']}/100")
            st.write(f"• Break & Enter: {row['Break & Enter']}/100")
            st.write(f"• Robbery: {row['Robbery']}/100")
            st.write(f"• Assault: {row['Assault']}/100")
            st.write(f"• Auto Theft: {row['Auto Theft']}/100")

            st.write("**Recommended next step:** Conduct a full CPTED/security review for this location.")
            st.divider()

        st.header("Portfolio Summary")

        critical_count = len(results_df[results_df["Overall Score"] >= 75])
        high_count = len(results_df[(results_df["Overall Score"] >= 60) & (results_df["Overall Score"] < 75)])
        moderate_count = len(results_df[(results_df["Overall Score"] >= 40) & (results_df["Overall Score"] < 60)])
        low_count = len(results_df[results_df["Overall Score"] < 40])

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("🔴 Critical", critical_count)

        with col2:
            st.metric("🟠 High", high_count)

        with col3:
            st.metric("🟡 Moderate", moderate_count)

        with col4:
            st.metric("🟢 Low", low_count)

        st.info(
            "Use this summary to quickly identify which locations should be reviewed first for CPTED assessments, security upgrades, or further investigation."
        )
        st.header("Portfolio Insights")

        avg_score = round(results_df["Overall Score"].mean(), 1)
        highest_risk = results_df.iloc[0]
        lowest_risk = results_df.iloc[-1]

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Average Portfolio Score", f"{avg_score}/100")

        with col2:
            st.metric("Highest Risk Site", highest_risk["Address"])

        with col3:
            st.metric("Lowest Risk Site", lowest_risk["Address"])

        if critical_count > 0:
            st.error(f"Immediate review recommended for {critical_count} Critical Risk location(s).")
        elif high_count > 0:
            st.warning(f"Review recommended for {high_count} High Risk location(s).")
        else:
            st.success("No Critical or High Risk locations identified in this upload.")

        st.header("Next Step: Review Highest Priority Site")

        if len(results_df) > 0:
            top_address = results_df.iloc[0]["Address"]
            top_score = results_df.iloc[0]["Overall Score"]
            top_risk = results_df.iloc[0]["Risk Level"]

            st.success(
                f"Highest priority location: **{top_address}** — {top_score}/100 ({top_risk})"
            )

            st.write(
                "Copy this address into the Retail Safety Risk Assessment page to generate a full site-level report."
            )

            st.code(top_address)
        
        st.header("Priority Actions")
        critical = results_df[results_df["Overall Score"] >= 75]
        high = results_df[(results_df["Overall Score"] >= 60) & (results_df["Overall Score"] < 75)]
        moderate = results_df[(results_df["Overall Score"] >= 40) & (results_df["Overall Score"] < 60)]
        low = results_df[results_df["Overall Score"] < 40]

        st.write("Use the risk ranking to decide which locations should receive security attention first.")

        if len(critical) > 0:
            st.error(f"**{len(critical)} Critical Risk locations** require immediate security review")
            for _, row in critical.iterrows():
                st.write(f"🔴 {row['Address']} — {row['Overall Score']}/100")

        if len(high) > 0:
            st.warning(f"**{len(high)} High Risk locations** require significant security investment")
            for _, row in high.iterrows():
                st.write(f"🟠 {row['Address']} — {row['Overall Score']}/100")

        if len(moderate) > 0:
            st.info(
                f"**{len(moderate)} Moderate Risk locations** should be monitored and reviewed as resources allow."
            )

        if len(low) > 0:
            st.success(
                f"**{len(low)} Low Risk locations** are lower priority based on current available data."
            )

        portfolio_pdf = generate_portfolio_pdf(results_df)

        st.download_button(
            label="📄 Download Portfolio Report PDF",
            data=portfolio_pdf,
            file_name="riskterrain_portfolio_report.pdf",
            mime="application/pdf"
        )

        csv_output = results_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Full Results CSV",
            data=csv_output,
            file_name="retail_safety_scores.csv",
            mime="text/csv"
        )
