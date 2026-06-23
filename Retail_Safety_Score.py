open -a IDLE pages/Retail_Safety_Score.py
import streamlit as st
import pandas as pd
import json
import re
from geopy.geocoders import Nominatim

st.title("🏪 Retail Safety Score")
st.write("Enter a store address to get an instant crime risk assessment and safety recommendations.")

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

df = load_data()

address = st.text_input("Enter store address", "500 Gordon St, Guelph, Ontario")

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
                return nearby.sum()

            be_count = get_nearby("Break & Enter")
            assault_count = get_nearby("Assault")
            robbery_count = get_nearby("Robbery")
            auto_count = get_nearby("Auto Theft")

            city_avg_be = len(df[df["CRIME_TYPE"] == "Break & Enter"]) / 140
            city_avg_assault = len(df[df["CRIME_TYPE"] == "Assault"]) / 140
            city_avg_robbery = len(df[df["CRIME_TYPE"] == "Robbery"]) / 140
            city_avg_auto = len(df[df["CRIME_TYPE"] == "Auto Theft"]) / 140

            def calc_score(count, avg):
                ratio = count / max(avg, 1)
                score = min(100, ratio * 50)
                return round(score, 1)

            be_score = calc_score(be_count, city_avg_be)
            assault_score = calc_score(assault_count, city_avg_assault)
            robbery_score = calc_score(robbery_count, city_avg_robbery)
            auto_score = calc_score(auto_count, city_avg_auto)

            overall_score = round(
                (be_score * 0.4) +
                (robbery_score * 0.3) +
                (assault_score * 0.2) +
                (auto_score * 0.1), 1
            )

            st.header("Overall Retail Safety Score")

            if overall_score >= 75:
                st.error(f"### {overall_score} / 100 — Critical Risk")
            elif overall_score >= 60:
                st.warning(f"### {overall_score} / 100 — High Risk")
            elif overall_score >= 40:
                st.info(f"### {overall_score} / 100 — Moderate Risk")
            else:
                st.success(f"### {overall_score} / 100 — Low Risk")

            st.header("Sub-Scores by Crime Type")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Break & Enter", f"{be_score}/100")
            col2.metric("Robbery", f"{robbery_score}/100")
            col3.metric("Assault", f"{assault_score}/100")
            col4.metric("Auto Theft", f"{auto_score}/100")

            st.header("Recommendations")

            def get_recommendations(crime_type, score):
                recs = {
                    "Break & Enter": {
                        "low": ["Maintain standard door and window locks", "Basic CCTV coverage at entrances"],
                        "moderate": ["Upgrade to commercial-grade locks", "Install alarm system", "Add CCTV to stockroom and back entrance"],
                        "high": ["Install reinforced doors and frames", "24/7 monitored alarm system", "Comprehensive CCTV with off-site recording", "Safe for cash storage"],
                        "critical": ["Security grilles on windows and doors", "On-site security guard during closing", "Panic buttons for staff", "Full perimeter CCTV system"]
                    },
                    "Robbery": {
                        "low": ["Standard cash handling procedures", "Basic staff safety training"],
                        "moderate": ["Limit cash on hand", "Install panic buttons", "Staff robbery prevention training"],
                        "high": ["Time-delay safe", "Dye packs or GPS trackers in cash", "Increased staff during high-risk hours", "Visible CCTV signage"],
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

            for crime_type, score in [
                ("Break & Enter", be_score),
                ("Robbery", robbery_score),
                ("Assault", assault_score),
                ("Auto Theft", auto_score)
            ]:
                with st.expander(f"{crime_type} — Score: {score}/100"):
                    recs = get_recommendations(crime_type, score)
                    for rec in recs:
                        st.write(f"• {rec}")

            st.header("Recommended Security Vendors")
            st.info("Partner security companies will appear here based on your risk profile. Vendor partnerships coming soon.")

        else:
            st.error("Address not found — try adding the city name")

    except Exception as e:
        st.error(f"Error: {e}")
        
