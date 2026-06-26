import io
from datetime import date
from html import escape
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from geopy.geocoders import Nominatim

st.title("📊 Compare Store Locations")
st.write("Enter two store addresses to compare their Retail Safety Scores side by side.")

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

    all_crimes = pd.concat(
        [assault, breakenter, robbery, autotheft, theftover],
        ignore_index=True
    )
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

    be_count = get_nearby("Break & Enter")
    assault_count = get_nearby("Assault")
    robbery_count = get_nearby("Robbery")
    auto_count = get_nearby("Auto Theft")
    theft_count = get_nearby("Theft Over $5000")

    be = calc_score(be_count, city_avg_be)
    assault = calc_score(assault_count, city_avg_assault)
    robbery = calc_score(robbery_count, city_avg_robbery)
    auto = calc_score(auto_count, city_avg_auto)
    theft = calc_score(theft_count, city_avg_theft)

    overall = round(
        (theft * 0.30) +
        (be * 0.25) +
        (robbery * 0.25) +
        (assault * 0.15) +
        (auto * 0.05),
        1
    )

    overall = min(overall, 100)

    return {
        "Overall": overall,
        "Break & Enter": be,
        "Robbery": robbery,
        "Assault": assault,
        "Auto Theft": auto,
        "Theft Over $5000": theft,
        "Theft_count": int(theft_count),
        "BE_count": int(be_count),
        "Robbery_count": int(robbery_count),
        "Assault_count": int(assault_count),
        "Auto_count": int(auto_count),
        "Total_count": int(theft_count + be_count + assault_count + robbery_count + auto_count)
    }

def risk_label(score):
    if score >= 75:
        return "🔴 Critical"
    elif score >= 60:
        return "🟠 High"
    elif score >= 40:
        return "🟡 Moderate"
    else:
        return "🟢 Low"

def risk_summary(score, address):
    if score >= 75:
        return f"{address} is in a **critical risk area** requiring immediate and comprehensive security measures."
    elif score >= 60:
        return f"{address} is in a **high risk area** requiring significant security investment."
    elif score >= 40:
        return f"{address} is in a **moderate risk area** that would benefit from targeted security improvements."
    else:
        return f"{address} is in a **low risk area** — standard security measures are appropriate."

def get_recommendations(crime_type, score):
    recs = {
        "Theft Over $5000": {
    "low": [
        "Standard loss prevention procedures",
        "Basic CCTV at exits"
    ],
    "moderate": [
        "EAS tagging on high-value merchandise",
        "Dedicated loss prevention staff during peak hours",
        "CCTV covering high-value areas"
    ],
    "high": [
        "Full EAS system throughout store",
        "Plainclothes loss prevention staff",
        "Locked cases for high-value items",
        "Receipt checking at exits"
    ],
    "critical": [
        "Dedicated loss prevention team",
        "Real-time CCTV monitoring",
        "Access control on stockroom",
        "Comprehensive EAS system",
        "Regular staff theft-prevention training"
    ]
},
        "Break & Enter": {
            "low": ["Maintain standard door and window locks", "Basic CCTV coverage at entrances"],
            "moderate": ["Upgrade to commercial-grade locks", "Install alarm system", "Add CCTV to stockroom and back entrance"],
            "high": ["Install reinforced doors and frames", "24/7 monitored alarm system", "Comprehensive CCTV with off-site recording", "Safe for cash storage"],
            "critical": ["Security grilles on windows and doors", "On-site security guard during closing", "Panic buttons for staff", "Full perimeter CCTV system"]
        },
        "Robbery": {
            "low": ["Standard cash handling procedures", "Basic staff safety training"],
            "moderate": ["Limit cash on hand", "Install panic buttons", "Staff robbery prevention training"],
            "high": ["Time-delay safe", "Increased staff during high-risk hours", "Visible CCTV signage"],
            "critical": ["On-site security guard", "Bullet-resistant barrier at cash", "Real-time monitoring", "Emergency response protocol"]
        },
        "Assault": {
            "low": ["Standard conflict de-escalation training"],
            "moderate": ["Enhanced staff safety training", "Clear sightlines throughout store", "Improve lighting in all areas"],
            "high": ["Security guard during peak hours", "Panic buttons throughout store", "Real-time CCTV monitoring"],
            "critical": ["On-site security guard at all times", "Access control on staff areas", "Direct police liaison"]
        },
        "Auto Theft": {
            "low": ["Standard parking lot lighting"],
            "moderate": ["Improve parking lot lighting", "CCTV covering parking area"],
            "high": ["24/7 monitored parking lot cameras", "Security patrols of parking area"],
            "critical": ["Gated parking with access control", "On-site security patrol", "CCTV with license plate recognition"]
        }
    }
    if score >= 75:
        level = "critical"
    elif score >= 60:
        level = "high"
    elif score >= 40:
        level = "moderate"
    else:
        level = "low"
    return recs[crime_type][level]

def generate_compare_pdf(address1, address2, scores1, scores2):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []

    logo = Image("riskterrain_logo.png")
    logo.drawWidth = 220
    logo.drawHeight = 120

    story.append(logo)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Location Comparison Report", styles["Heading1"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"<b>Store 1:</b> {escape(address1)}", styles["Normal"]))
    story.append(Paragraph(f"<b>Store 2:</b> {escape(address2)}", styles["Normal"]))
    story.append(Paragraph(f"<b>Report Date:</b> {date.today().strftime('%B %d, %Y')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    if scores1["Overall"] > scores2["Overall"]:
        verdict = f"Store 1 is higher risk by {round(scores1['Overall'] - scores2['Overall'], 1)} points."
    elif scores2["Overall"] > scores1["Overall"]:
        verdict = f"Store 2 is higher risk by {round(scores2['Overall'] - scores1['Overall'], 1)} points."
    else:
        verdict = "Both locations have equal overall risk scores."

    story.append(Paragraph("<b>Executive Verdict</b>", styles["Heading2"]))
    story.append(Paragraph(escape(verdict), styles["Normal"]))
    story.append(Spacer(1, 12))
    
    if scores1["Overall"] > scores2["Overall"]:
        higher_store = "Store 1"
        lower_store = "Store 2"
        higher_scores = scores1
    elif scores2["Overall"] > scores1["Overall"]:
        higher_store = "Store 2"
        lower_store = "Store 1"
        higher_scores = scores2
    else:
        higher_store = "Both stores"
        lower_store = "Neither store"
        higher_scores = scores1

    summary_text = (
        f"{higher_store} has the higher overall risk profile. The largest areas of concern are the crime categories "
        f"with the highest scores, especially any category rated High or Critical. This comparison can help decide "
        f"which location should be prioritized first for security planning, CPTED improvements, and loss prevention review."
    )

    story.append(Paragraph("<b>Quick Summary</b>", styles["Heading2"]))
    story.append(Paragraph(escape(summary_text), styles["Normal"]))
    story.append(Spacer(1, 12))

    table_data = [
        ["Category", "Store 1", "Store 2"],
        ["Overall", scores1["Overall"], scores2["Overall"]],
        ["Theft Over $5000", scores1["Theft Over $5000"], scores2["Theft Over $5000"]],
        ["Break & Enter", scores1["Break & Enter"], scores2["Break & Enter"]],
        ["Robbery", scores1["Robbery"], scores2["Robbery"]],
        ["Assault", scores1["Assault"], scores2["Assault"]],
        ["Auto Theft", scores1["Auto Theft"], scores2["Auto Theft"]],
    ]

    table = Table(table_data, colWidths=[180, 120, 120])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#e8f1f8")]),
    ]))

    story.append(Paragraph("<b>Risk Score Comparison</b>", styles["Heading2"]))
    story.append(table)
    story.append(Spacer(1, 16))

    focus_areas = [
        "Access control at entrances, exits, and rear doors",
        "Lighting and visibility around the storefront",
        "Cash handling and robbery prevention procedures",
        "High-value merchandise protection and stockroom access control",
        "Staff safety, de-escalation, and incident response procedures"
    ]

    story.append(Paragraph("<b>Recommended Focus Areas</b>", styles["Heading2"]))
    for area in focus_areas:
        story.append(Paragraph(f"• {escape(area)}", styles["Normal"]))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 12))
    story.append(Paragraph("<b>Methodology</b>", styles["Heading2"]))
    story.append(Paragraph(
        "This comparison uses historical Toronto crime data to compare nearby incident concentrations and generate relative retail safety scores.",
        styles["Normal"]
    ))

    story.append(Spacer(1, 16))
    count_table_data = [
        ["Crime Type", "Store 1 Incidents", "Store 2 Incidents"],
        ["Theft Over $5000", scores1["Theft_count"], scores2["Theft_count"]],
        ["Break & Enter", scores1["BE_count"], scores2["BE_count"]],
        ["Robbery", scores1["Robbery_count"], scores2["Robbery_count"]],
        ["Assault", scores1["Assault_count"], scores2["Assault_count"]],
        ["Auto Theft", scores1["Auto_count"], scores2["Auto_count"]],
        ["Total", scores1["Total_count"], scores2["Total_count"]],
    ]

    count_table = Table(count_table_data, colWidths=[180, 120, 120])
    count_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#e8f1f8")]),
    ]))

    story.append(Paragraph("<b>Nearby Incident Count Comparison</b>", styles["Heading2"]))
    story.append(count_table)
    story.append(Spacer(1, 16))
    story.append(Paragraph("Generated by RiskTerrain™", styles["Normal"]))
    story.append(Paragraph("AI-Assisted CPTED Analytics", styles["Normal"]))
    story.append(Paragraph("Built by Alex Babb — University of Guelph", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer
df = load_data()
geolocator = Nominatim(user_agent="cpted_compare")

col1, col2 = st.columns(2)
with col1:
    address1 = st.text_input("Store 1 Address", "500 Yonge St, Toronto, Ontario")
with col2:
    address2 = st.text_input("Store 2 Address", "2150 Pharmacy Ave, Toronto, Ontario")

if st.button("Compare Locations"):
    with st.spinner("Analyzing both locations..."):
        try:
            loc1 = geolocator.geocode(address1)
            loc2 = geolocator.geocode(address2)

            if loc1 and loc2:
                scores1 = calc_scores(df, loc1.latitude, loc1.longitude)
                scores2 = calc_scores(df, loc2.latitude, loc2.longitude)

                # Overall scores
                st.header("Overall Safety Score")
                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Store 1")
                    st.caption(address1)
                    if scores1["Overall"] >= 75:
                        st.error(f"## {scores1['Overall']}/100")
                    elif scores1["Overall"] >= 60:
                        st.warning(f"## {scores1['Overall']}/100")
                    elif scores1["Overall"] >= 40:
                        st.info(f"## {scores1['Overall']}/100")
                    else:
                        st.success(f"## {scores1['Overall']}/100")
                    st.write(risk_label(scores1["Overall"]))
                    st.write(f"**Total nearby incidents:** {scores1['Total_count']}")
                    st.markdown(risk_summary(scores1["Overall"], "This location"))

                with col2:
                    st.subheader("Store 2")
                    st.caption(address2)
                    if scores2["Overall"] >= 75:
                        st.error(f"## {scores2['Overall']}/100")
                    elif scores2["Overall"] >= 60:
                        st.warning(f"## {scores2['Overall']}/100")
                    elif scores2["Overall"] >= 40:
                        st.info(f"## {scores2['Overall']}/100")
                    else:
                        st.success(f"## {scores2['Overall']}/100")
                    st.write(risk_label(scores2["Overall"]))
                    st.write(f"**Total nearby incidents:** {scores2['Total_count']}")
                    st.markdown(risk_summary(scores2["Overall"], "This location"))

                # Visual bar chart comparison
                st.header("Score Comparison Chart")
                categories = ["Overall", "Theft Over $5000", "Break & Enter", "Robbery", "Assault", "Auto Theft"]
                vals1 = [scores1["Overall"], scores1["Theft Over $5000"], scores1["Break & Enter"], scores1["Robbery"], scores1["Assault"], scores1["Auto Theft"]]
                vals2 = [scores2["Overall"], scores2["Theft Over $5000"], scores2["Break & Enter"], scores2["Robbery"], scores2["Assault"], scores2["Auto Theft"]]

                x = np.arange(len(categories))
                width = 0.35

                fig, ax = plt.subplots(figsize=(10, 5))
                bars1 = ax.bar(x - width/2, vals1, width, label="Store 1", color="crimson", alpha=0.8)
                bars2 = ax.bar(x + width/2, vals2, width, label="Store 2", color="steelblue", alpha=0.8)

                ax.set_ylabel("Risk Score (0-100)")
                ax.set_title("Risk Score Comparison by Crime Type")
                ax.set_xticks(x)
                ax.set_xticklabels(categories)
                ax.legend()
                ax.set_ylim(0, 110)
                ax.axhline(y=75, color="red", linestyle="--", alpha=0.5, label="Critical threshold")
                ax.axhline(y=40, color="orange", linestyle="--", alpha=0.5, label="Moderate threshold")

                for bar in bars1:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                            f"{bar.get_height()}", ha="center", va="bottom", fontsize=8)
                for bar in bars2:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                            f"{bar.get_height()}", ha="center", va="bottom", fontsize=8)

                plt.tight_layout()
                st.pyplot(fig)

                # Incident count breakdown
                st.header("Nearby Incident Counts")
                incident_data = {
                    "Crime Type": ["Theft Over $5000", "Break & Enter", "Robbery", "Assault", "Auto Theft", "Total"],
                    "Store 1 Incidents": [scores1["Theft_count"], scores1["BE_count"], scores1["Robbery_count"], scores1["Assault_count"], scores1["Auto_count"], scores1["Total_count"]],
                    "Store 2 Incidents": [scores2["Theft_count"], scores2["BE_count"], scores2["Robbery_count"], scores2["Assault_count"], scores2["Auto_count"], scores2["Total_count"]],
                }
                st.dataframe(pd.DataFrame(incident_data), use_container_width=True)

                # Verdict
                st.header("Verdict")
                if scores1["Overall"] > scores2["Overall"]:
                    diff = round(scores1["Overall"] - scores2["Overall"], 1)
                    st.error(f"**Store 1 is higher risk** by {diff} points — priority location for security investment")
                elif scores2["Overall"] > scores1["Overall"]:
                    diff = round(scores2["Overall"] - scores1["Overall"], 1)
                    st.error(f"**Store 2 is higher risk** by {diff} points — priority location for security investment")
                else:
                    st.info("Both locations have equal risk scores")

                pdf = generate_compare_pdf(address1, address2, scores1, scores2)

                st.download_button(
                    label="📄 Download Comparison Report",
                    data=pdf,
                    file_name="riskterrain_location_comparison.pdf",
                    mime="application/pdf"
                )

                # Recommendations for higher risk store
                higher_risk_scores = scores1 if scores1["Overall"] >= scores2["Overall"] else scores2
                higher_risk_address = address1 if scores1["Overall"] >= scores2["Overall"] else address2

                st.header(f"Priority Recommendations for Higher Risk Location")
                st.write(f"**{higher_risk_address}**")

                for crime_type, key in [
                    ("Theft Over $5000", "Theft Over $5000"),
                    ("Break & Enter", "Break & Enter"),
                    ("Robbery", "Robbery"),
                    ("Assault", "Assault"),
                    ("Auto Theft", "Auto Theft")
                ]:
                    score = higher_risk_scores[key]
                    with st.expander(f"{crime_type} — {score}/100 — {risk_label(score)}"):
                        recs = get_recommendations(crime_type, score)
                        for rec in recs:
                            st.write(f"• {rec}")

            else:
                st.error("One or both addresses could not be found — try adding the city name")

        except Exception as e:
            st.error(f"Error: {e}")
