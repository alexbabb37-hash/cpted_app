import streamlit as st
import pandas as pd
import json
import re
from geopy.geocoders import Nominatim
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import io
from datetime import date
from html import escape
from reportlab.platypus import Image

st.title("🏪 Retail Safety Risk Assessment")
st.write("Enter a store address to generate an AI-assisted CPTED risk assessment and safety recommendations.")

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

    all_crimes = pd.concat([assault, breakenter, robbery, autotheft], ignore_index=True)

    all_crimes = all_crimes[
        (all_crimes["LAT_WGS84"] > 43) & (all_crimes["LAT_WGS84"] < 44) &
        (all_crimes["LONG_WGS84"] > -80) & (all_crimes["LONG_WGS84"] < -79)
    ]

    return all_crimes

def risk_label(score):
    if score >= 75:
        return "Critical Risk"
    elif score >= 60:
        return "High Risk"
    elif score >= 40:
        return "Moderate Risk"
    else:
        return "Low Risk"

def short_risk_label(score):
    if score >= 75:
        return "Critical"
    elif score >= 60:
        return "High"
    elif score >= 40:
        return "Moderate"
    else:
        return "Low"

def get_score_summary(score):
    if score >= 75:
        return "well above the city comparison baseline"
    elif score >= 60:
        return "above the city comparison baseline"
    elif score >= 40:
        return "near a moderate comparison level"
    else:
        return "below the city comparison baseline"

def get_crime_guidance(crime_type, score):
    guidance = {
        "Break & Enter": {
            "driver": "property access risk, after-hours vulnerability, and weak perimeter control",
            "areas": [
                "Front and rear entrances",
                "Delivery doors and service corridors",
                "Window lines and commercial glazing",
                "Exterior lighting and concealment points"
            ],
            "strategies": [
                "Strengthen access control at doors, windows, and service entrances",
                "Improve lighting around rear access points and storefront edges",
                "Reduce concealment opportunities near entrances and exterior walls",
                "Use territorial reinforcement such as clear boundaries, signage, and maintained storefront conditions"
            ]
        },
        "Robbery": {
            "driver": "street-level opportunity, cash-handling exposure, pedestrian movement, and escape route availability",
            "areas": [
                "Point-of-sale area",
                "Customer entrance and exit routes",
                "Sightlines from the street into the store",
                "Nearby pedestrian gathering points and transit connections"
            ],
            "strategies": [
                "Improve visibility between the cashier area, entrance, and public realm",
                "Use cash-control procedures, drop safes, and reduced drawer balances",
                "Maintain clear sightlines and remove unnecessary visual obstructions",
                "Support natural surveillance through active frontages and well-lit entrances"
            ]
        },
        "Assault": {
            "driver": "interpersonal conflict risk, public disorder, crowding, and visibility conditions",
            "areas": [
                "Entrances and customer gathering areas",
                "Aisles and blind spots",
                "Checkout visibility",
                "Exterior waiting areas and sidewalks"
            ],
            "strategies": [
                "Improve natural surveillance and staff visibility across the floor",
                "Maintain clear sightlines through store layout and product placement",
                "Use lighting to reduce hidden or poorly observed areas",
                "Train staff in de-escalation and establish clear incident response procedures"
            ]
        },
        "Auto Theft": {
            "driver": "parking exposure, offender mobility, vehicle target availability, and low surveillance",
            "areas": [
                "Customer and staff parking areas",
                "Rear lots and loading areas",
                "Lighting coverage across vehicle areas",
                "Camera visibility and access points"
            ],
            "strategies": [
                "Improve lighting and visibility across parking and loading areas",
                "Use cameras and signage to increase perceived guardianship",
                "Reduce uncontrolled access to staff parking or rear lots",
                "Maintain clear sightlines between the building and vehicle areas"
            ]
        }
    }

    return guidance[crime_type]

def get_assessment(address, scores, counts, overall_score):
    label = risk_label(overall_score)

    sorted_threats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary_threat = sorted_threats[0][0]
    secondary_threat = sorted_threats[1][0]

    executive_summary = (
        f"A localized assessment of {address} produced an overall retail safety score of "
        f"{overall_score}/100, classifying the site as {label}. The main risk driver is "
        f"{primary_threat}, with {secondary_threat} also contributing to the location’s risk profile. "
        f"This report should be treated as an early screening tool to support, not replace, a formal site visit or CPTED review."
    )

    key_drivers = []
    areas_to_examine = []
    recommendations = []

    for crime_type, score in sorted_threats:
        if score >= 40:
            guidance = get_crime_guidance(crime_type, score)

            key_drivers.append(
                f"{crime_type}: {score}/100 ({short_risk_label(score)}) — {counts[crime_type]} nearby incidents, "
                f"{get_score_summary(score)}. Primary concern: {guidance['driver']}."
            )

            areas_to_examine.extend(guidance["areas"])
            recommendations.extend(guidance["strategies"])

    if not key_drivers:
        key_drivers.append(
            "No major crime category is currently elevated based on the selected comparison method."
        )
        areas_to_examine = [
            "Entrances and exits",
            "Exterior lighting",
            "Parking areas",
            "Sightlines from public areas"
        ]
        recommendations = [
            "Maintain clear sightlines and good lighting",
            "Continue monitoring local crime conditions",
            "Preserve clean, well-maintained exterior conditions",
            "Review access control and staff safety procedures periodically"
        ]

    areas_to_examine = list(dict.fromkeys(areas_to_examine))
    recommendations = list(dict.fromkeys(recommendations))

    return executive_summary, key_drivers, areas_to_examine, recommendations

def generate_pdf(address, overall_score, score_dict, count_dict, executive_summary, key_drivers, areas_to_examine, recommendations):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = []

    logo = Image("riskterrain_logo.png")
    logo.drawWidth = 220
    logo.drawHeight = 120

    story.append(logo)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Retail Safety Risk Assessment", styles["Heading1"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Target Location:</b> {escape(address)}", styles["Normal"]))
    story.append(Paragraph(f"<b>Assessment Date:</b> {date.today().strftime('%B %d, %Y')}", styles["Normal"]))
    story.append(Spacer(1, 12))

    label = risk_label(overall_score)
    story.append(Paragraph(f"<b>Overall Retail Safety Score: {overall_score}/100 — {label}</b>", styles["Heading1"]))
    story.append(Paragraph("<b>Risk Confidence:</b> Preliminary — based on available historical Toronto crime data within the selected location radius.", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>1. Executive Summary</b>", styles["Heading2"]))
    story.append(Paragraph(escape(executive_summary), styles["Normal"]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>2. Crime Sub-Scores</b>", styles["Heading2"]))
    story.append(Spacer(1, 6))

    table_data = [
        ["Crime Type", "Nearby Incidents", "Score", "Risk Level"],
        ["Break & Enter", str(count_dict["Break & Enter"]), f"{score_dict['Break & Enter']}/100", short_risk_label(score_dict["Break & Enter"])],
        ["Robbery", str(count_dict["Robbery"]), f"{score_dict['Robbery']}/100", short_risk_label(score_dict["Robbery"])],
        ["Assault", str(count_dict["Assault"]), f"{score_dict['Assault']}/100", short_risk_label(score_dict["Assault"])],
        ["Auto Theft", str(count_dict["Auto Theft"]), f"{score_dict['Auto Theft']}/100", short_risk_label(score_dict["Auto Theft"])],
    ]

    table = Table(table_data, colWidths=[150, 110, 90, 90])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#e8f1f8")]),
    ]))
    story.append(table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("<b>3. Key Risk Drivers</b>", styles["Heading2"]))
    for item in key_drivers:
        story.append(Paragraph(f"• {escape(item)}", styles["Normal"]))
        story.append(Spacer(1, 5))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>4. Areas to Examine During Site Review</b>", styles["Heading2"]))
    for item in areas_to_examine:
        story.append(Paragraph(f"• {escape(item)}", styles["Normal"]))
        story.append(Spacer(1, 5))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>5. Priority CPTED Strategies</b>", styles["Heading2"]))
    for item in recommendations:
        story.append(Paragraph(f"• {escape(item)}", styles["Normal"]))
        story.append(Spacer(1, 5))

    story.append(Spacer(1, 18))
    story.append(Paragraph("<b>Limitations:</b> This report is generated from available Toronto crime data and should be used as an early screening tool. A formal CPTED assessment should include a site visit, environmental review, stakeholder input, and professional judgment.", styles["Normal"]))
    story.append(Spacer(1, 16))
    story.append(Paragraph("Generated by RiskTerrain™", styles["Normal"]))
    story.append(Paragraph("AI-Assisted CPTED Analytics", styles["Normal"]))
    story.append(Paragraph("Built by Alex Babb — University of Guelph", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer

df = load_data()

address = st.text_input("Enter store address", "500 Yonge St, Toronto, Ontario")

if st.button("Generate Safety Score"):
    geolocator = Nominatim(user_agent="cpted_retail")

    try:
        location = geolocator.geocode(address)

        if location:
            lat = location.latitude
            lon = location.longitude

            st.success(f"Location found: {round(lat, 5)}, {round(lon, 5)}")

            radius = 0.005

            def get_nearby(crime_type):
                subset = df[df["CRIME_TYPE"] == crime_type]
                nearby = (
                    ((subset["LAT_WGS84"] - lat) ** 2 +
                     (subset["LONG_WGS84"] - lon) ** 2) ** 0.5
                ) < radius
                return int(nearby.sum())

            count_dict = {
                "Break & Enter": get_nearby("Break & Enter"),
                "Robbery": get_nearby("Robbery"),
                "Assault": get_nearby("Assault"),
                "Auto Theft": get_nearby("Auto Theft")
            }

            city_avg = {
                "Break & Enter": len(df[df["CRIME_TYPE"] == "Break & Enter"]) / 140,
                "Robbery": len(df[df["CRIME_TYPE"] == "Robbery"]) / 140,
                "Assault": len(df[df["CRIME_TYPE"] == "Assault"]) / 140,
                "Auto Theft": len(df[df["CRIME_TYPE"] == "Auto Theft"]) / 140
            }

            def calc_score(count, avg):
                ratio = count / max(avg, 1)
                score = min(100, ratio * 50)
                return round(score, 1)

            score_dict = {
                "Break & Enter": calc_score(count_dict["Break & Enter"], city_avg["Break & Enter"]),
                "Robbery": calc_score(count_dict["Robbery"], city_avg["Robbery"]),
                "Assault": calc_score(count_dict["Assault"], city_avg["Assault"]),
                "Auto Theft": calc_score(count_dict["Auto Theft"], city_avg["Auto Theft"])
            }

            overall_score = round(
                (score_dict["Break & Enter"] * 0.35) +
                (score_dict["Robbery"] * 0.30) +
                (score_dict["Assault"] * 0.25) +
                (score_dict["Auto Theft"] * 0.10),
                1
            )

            executive_summary, key_drivers, areas_to_examine, recommendations = get_assessment(
                address, score_dict, count_dict, overall_score
            )

            st.header("Overall Retail Safety Score")

            if overall_score >= 75:
                st.error(f"### {overall_score} / 100 — {risk_label(overall_score)}")
            elif overall_score >= 60:
                st.warning(f"### {overall_score} / 100 — {risk_label(overall_score)}")
            elif overall_score >= 40:
                st.info(f"### {overall_score} / 100 — {risk_label(overall_score)}")
            else:
                st.success(f"### {overall_score} / 100 — {risk_label(overall_score)}")

            st.header("Sub-Scores by Crime Type")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Break & Enter", f"{score_dict['Break & Enter']}/100", f"{count_dict['Break & Enter']} nearby")
            col2.metric("Robbery", f"{score_dict['Robbery']}/100", f"{count_dict['Robbery']} nearby")
            col3.metric("Assault", f"{score_dict['Assault']}/100", f"{count_dict['Assault']} nearby")
            col4.metric("Auto Theft", f"{score_dict['Auto Theft']}/100", f"{count_dict['Auto Theft']} nearby")

            st.header("AI-Assisted CPTED Risk Report")

            st.subheader("Executive Summary")
            st.write(executive_summary)

            st.subheader("Key Risk Drivers")
            for item in key_drivers:
                st.write(f"🔴 {item}")

            st.subheader("Areas to Examine During Site Review")
            for item in areas_to_examine:
                st.write(f"• {item}")

            st.subheader("Priority CPTED Strategies")
            for item in recommendations:
                st.write(f"✅ {item}")

            st.caption("This tool supports early-stage screening only. A formal CPTED review should include a site visit, environmental observations, stakeholder input, and professional judgment.")
            st.caption("Risk Confidence: Preliminary — based on available historical Toronto crime data within the selected location radius.")

            st.header("Download Report")
            pdf = generate_pdf(
                address,
                overall_score,
                score_dict,
                count_dict,
                executive_summary,
                key_drivers,
                areas_to_examine,
                recommendations
            )

            clean_filename = re.sub(r"[^a-zA-Z0-9_-]", "_", address)
            st.download_button(
                label="📄 Download CPTED Risk Report",
                data=pdf,
                file_name=f"retail_safety_report_{clean_filename}.pdf",
                mime="application/pdf"
            )

        else:
            st.error("Address not found — try adding Toronto, Ontario to the address.")

    except Exception as e:
        st.error(f"Error: {e}")