import streamlit as st
import pandas as pd
import time
from geopy.geocoders import Nominatim

st.title("📋 Batch Location Scorer")
st.write("Upload a CSV of store addresses to score all locations at once and get a ranked risk report.")

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

    be = calc_score(get_nearby("Break & Enter"), city_avg_be)
    assault = calc_score(get_nearby("Assault"), city_avg_assault)
    robbery = calc_score(get_nearby("Robbery"), city_avg_robbery)
    auto = calc_score(get_nearby("Auto Theft"), city_avg_auto)

    overall = round((be * 0.4) + (robbery * 0.3) + (assault * 0.2) + (auto * 0.1), 1)

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
        "Break & Enter": be,
        "Robbery": robbery,
        "Assault": assault,
        "Auto Theft": auto,
    }

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

        st.header("Priority Actions")
        critical = results_df[results_df["Overall Score"] >= 75]
        high = results_df[(results_df["Overall Score"] >= 60) & (results_df["Overall Score"] < 75)]

        if len(critical) > 0:
            st.error(f"**{len(critical)} Critical Risk locations** require immediate security review")
            for _, row in critical.iterrows():
                st.write(f"🔴 {row['Address']} — {row['Overall Score']}/100")

        if len(high) > 0:
            st.warning(f"**{len(high)} High Risk locations** require significant security investment")
            for _, row in high.iterrows():
                st.write(f"🟠 {row['Address']} — {row['Overall Score']}/100")

        csv_output = results_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Full Results CSV",
            data=csv_output,
            file_name="retail_safety_scores.csv",
            mime="text/csv"
        )
