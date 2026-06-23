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
    all_crimes = pd.concat([assault, breakenter, robbery, autotheft], ignore_index=True)
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

    be_count = get_nearby("Break & Enter")
    assault_count = get_nearby("Assault")
    robbery_count = get_nearby("Robbery")
    auto_count = get_nearby("Auto Theft")

    be = calc_score(be_count, city_avg_be)
    assault = calc_score(assault_count, city_avg_assault)
    robbery = calc_score(robbery_count, city_avg_robbery)
    auto = calc_score(auto_count, city_avg_auto)

    overall = round((be * 0.4) + (robbery * 0.3) + (assault * 0.2) + (auto * 0.1), 1)

    return {
        "Overall": overall,
        "Break & Enter": be,
        "Robbery": robbery,
        "Assault": assault,
        "Auto Theft": auto,
        "BE_count": int(be_count),
        "Robbery_count": int(robbery_count),
        "Assault_count": int(assault_count),
        "Auto_count": int(auto_count),
        "Total_count": int(be_count + assault_count + robbery_count + auto_count)
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
                categories = ["Overall", "Break & Enter", "Robbery", "Assault", "Auto Theft"]
                vals1 = [scores1["Overall"], scores1["Break & Enter"], scores1["Robbery"], scores1["Assault"], scores1["Auto Theft"]]
                vals2 = [scores2["Overall"], scores2["Break & Enter"], scores2["Robbery"], scores2["Assault"], scores2["Auto Theft"]]

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
                    "Crime Type": ["Break & Enter", "Robbery", "Assault", "Auto Theft", "Total"],
                    "Store 1 Incidents": [scores1["BE_count"], scores1["Robbery_count"], scores1["Assault_count"], scores1["Auto_count"], scores1["Total_count"]],
                    "Store 2 Incidents": [scores2["BE_count"], scores2["Robbery_count"], scores2["Assault_count"], scores2["Auto_count"], scores2["Total_count"]],
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

                # Recommendations for higher risk store
                higher_risk_scores = scores1 if scores1["Overall"] >= scores2["Overall"] else scores2
                higher_risk_address = address1 if scores1["Overall"] >= scores2["Overall"] else address2

                st.header(f"Priority Recommendations for Higher Risk Location")
                st.write(f"**{higher_risk_address}**")

                for crime_type, key in [
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
