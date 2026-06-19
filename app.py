
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import numpy as np
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap

st.title("Toronto CPTED Crime Analysis")
st.write("AI-assisted Crime Prevention Through Environmental Design")


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

@st.cache_data
def load_poles():
    poles = pd.read_csv("poles.csv")
    poles["LONG"] = poles["geometry"].apply(lambda x: json.loads(x)["coordinates"][0][0])
    poles["LAT"] = poles["geometry"].apply(lambda x: json.loads(x)["coordinates"][0][1])
    return poles

@st.cache_data
def load_stations():
    stations = pd.read_csv("ttc_stations.csv")
    return stations

@st.cache_data
def load_parks():
    parks = pd.read_csv("parks.csv")
    parks["LONG"] = parks["geometry"].apply(lambda x: json.loads(x)["coordinates"][0][0])
    parks["LAT"] = parks["geometry"].apply(lambda x: json.loads(x)["coordinates"][0][1])
    return parks

@st.cache_data
def load_population():
    pop = pd.read_csv("population_clean.csv")
    return pop

import re
def clean_neighbourhood(name):
    name = re.sub(r'\s*\(\d+\)', '', str(name)).strip()
    name = name.replace("St.James", "St. James")
    name = name.replace("O'Connor-Parkview", "O`Connor Parkview")
    name = name.replace("Danforth East York", "Danforth-East York")
    name = name.replace("East End-Danforth", "East End Danforth")
    name = name.replace("Taylor-Massey", "Taylor Massey")
    name = name.replace("Yonge-St.Clair", "Yonge-St. Clair")
    return name
df = load_data()
stations = load_stations()
parks = load_parks()
population = load_population()

df["NEIGHBOURHOOD_CLEAN"] = df["NEIGHBOURHOOD_158"].apply(clean_neighbourhood)

st.sidebar.header("🔍 Filters")
st.sidebar.markdown("---")
selected_crime = st.sidebar.selectbox("Crime Type", ["Assault", "Break & Enter", "Robbery", "Auto Theft"])
time_filter = st.sidebar.slider("Hour of Day", 0, 23, (0, 23))
st.sidebar.markdown("---")
st.sidebar.header("🗺️ Map Layers")
show_poles = st.sidebar.checkbox("Street Pole Infrastructure")
show_stations = st.sidebar.checkbox("TTC Subway Stations")
show_parks = st.sidebar.checkbox("Parks")
st.sidebar.markdown("---")
st.sidebar.caption("Toronto CPTED Analysis Tool")
st.sidebar.caption("Built by Alex Babb — University of Guelph")

filtered = df[df["CRIME_TYPE"] == selected_crime]
filtered = filtered[
    (filtered["OCC_HOUR"] >= time_filter[0]) &
    (filtered["OCC_HOUR"] <= time_filter[1])
]

st.write(f"**{len(filtered):,} incidents** match your filters")

st.header("Crime Map")
fig, ax = plt.subplots(figsize=(10, 7))

ax.scatter(
    filtered["LONG_WGS84"],
    filtered["LAT_WGS84"],
    alpha=0.03,
    s=0.5,
    color="red"
)

if show_poles:
    poles = load_poles()
    ax.scatter(poles["LONG"], poles["LAT"],
               alpha=0.1, s=1, color="deepskyblue", label="Street Poles")
if show_stations:
    ax.scatter(stations["longitude"], stations["latitude"],
               alpha=0.8, s=30, color="navy", marker="o",
               label="TTC Subway Stations", zorder=5)
if show_parks:
    ax.scatter(parks["LONG"], parks["LAT"],
               alpha=0.4, s=6, color="green", marker="o",
               label="Parks", zorder=4)

ax.legend(markerscale=8)
ax.set_title(f"{selected_crime} - Hours {time_filter[0]}:00 to {time_filter[1]}:00")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
st.pyplot(fig)

st.header("Top 10 Neighbourhoods by Incident Count")

top_hoods = filtered["NEIGHBOURHOOD_158"].value_counts().head(10)

fig2, ax2 = plt.subplots(figsize=(10, 5))
top_hoods.sort_values().plot(kind="barh", ax=ax2, color="crimson")
ax2.set_title(f"Top Neighbourhoods for {selected_crime}")
ax2.set_xlabel("Number of Incidents")
plt.tight_layout()
st.pyplot(fig2)

st.header("Neighbourhood CPTED Risk Rankings")

hood_risk = filtered["NEIGHBOURHOOD_158"].value_counts().reset_index()
hood_risk.columns = ["Neighbourhood", "Incidents"]

max_incidents = hood_risk["Incidents"].max()

hood_risk["Risk Score"] = (
    hood_risk["Incidents"] / max_incidents * 100
).round(1)

hood_risk = hood_risk.sort_values(
    "Risk Score",
    ascending=False
)

st.dataframe(
    hood_risk.head(10).reset_index(drop=True),
    use_container_width=True
)
st.header("Neighbourhood Assessment")
selected_hood = st.selectbox(
    "Select a Neighbourhood",
    sorted(hood_risk["Neighbourhood"].unique())
)
hood_info = hood_risk[
    hood_risk["Neighbourhood"] == selected_hood
]

hood_row = hood_info.iloc[0]
st.metric(
    "Neighbourhood Risk Score",
    round(hood_row["Risk Score"], 1)
)

st.write(f"**Incidents:** {int(hood_row['Incidents'])}")

st.subheader("Key Risk Drivers")
if hood_row["Risk Score"] >= 60:
    st.write("- High concentration of reported incidents compared to other neighbourhoods")
    st.write("- Priority area for CPTED review and targeted intervention")
    st.write("- May require stronger lighting, visibility, and access control strategies")

elif hood_row["Risk Score"] >= 20:
    st.write("- Moderate incident concentration")
    st.write("- Area may benefit from targeted CPTED improvements")
    st.write("- Focus should be on visibility, maintenance, and natural surveillance")

else:
    st.write("- Lower incident concentration compared to other neighbourhoods")
    st.write("- Focus should be on maintaining existing safety conditions")
    st.write("- Continue monitoring for changes over time")

st.subheader("Assessment Summary")

if hood_row["Risk Score"] >= 60:
    st.write(
        "This neighbourhood has a high concentration of reported incidents and should be prioritized for CPTED review and targeted interventions."
    )

elif hood_row["Risk Score"] >= 20:
    st.write(
        "This neighbourhood demonstrates a moderate level of reported incidents and may benefit from focused CPTED improvements and ongoing monitoring."
    )

else:
    st.write(
        "This neighbourhood has a relatively low concentration of reported incidents compared to other Toronto neighbourhoods."
    )


st.header("Address / Location Lookup")

address = st.text_input(
    "Enter an address",
    "100 Queen St W, Toronto"
)

geolocator = Nominatim(user_agent="cpted_app")

try:
    location = geolocator.geocode(address)

    if location:
        input_lat = location.latitude
        input_lon = location.longitude

        st.write(f"Latitude: {round(input_lat, 6)}")
        st.write(f"Longitude: {round(input_lon, 6)}")
    else:
        st.error("Address not found")
        input_lat = 43.6532
        input_lon = -79.3832

except Exception as e:
    st.error(f"Error: {e}")
    input_lat = 43.6532
    input_lon = -79.3832

nearest_station = stations.copy()

nearest_station["Distance"] = (
    ((nearest_station["latitude"] - input_lat) ** 2 +
     (nearest_station["longitude"] - input_lon) ** 2) ** 0.5
)

nearby_incidents = (
    (((filtered["LAT_WGS84"] - input_lat) ** 2 +
      (filtered["LONG_WGS84"] - input_lon) ** 2) ** 0.5
     < 0.0025)
).sum()

nearest = nearest_station.sort_values("Distance").iloc[0]

col1, col2, col3 = st.columns(3)
col1.metric("Nearby Incidents", nearby_incidents)
col2.metric("Nearest Station", nearest["STATION"])
col3.metric("Distance to Station", f"{round(nearest['Distance'] * 111000)}m")
if nearby_incidents >= 800:
    st.error("High crime activity area")
    st.write("This location is associated with a high concentration of reported incidents.")

elif nearby_incidents >= 300:
    st.warning("Moderate crime activity area")
    st.write("This location is associated with a moderate concentration of reported incidents.")

else:
    st.success("Lower crime activity area")
    st.write("This location is associated with a lower concentration of reported incidents.")

st.subheader("Interactive Location Map")

m = folium.Map(
    location=[input_lat, input_lon],
    zoom_start=15
)

folium.Marker(
    [input_lat, input_lon],
    popup="Selected Location",
    tooltip="Selected Location",
    icon=folium.Icon(color="blue", icon="star")
).add_to(m)
folium.Circle(
    location=[input_lat, input_lon],
    radius=300,
    color="blue",
    fill=False
).add_to(m)

nearby_points = filtered[
    (((filtered["LAT_WGS84"] - input_lat) ** 2 +
      (filtered["LONG_WGS84"] - input_lon) ** 2) ** 0.5) < 0.0025
]

heat_data = nearby_points[["LAT_WGS84", "LONG_WGS84"]].dropna().values.tolist()

HeatMap(
    heat_data,
    radius=12,
    blur=18,
    max_zoom=15
).add_to(m)

st_folium(m, width=700, height=500)
st.subheader("Location Map")
fig3, ax3 = plt.subplots(figsize=(8, 6))
local = filtered[
    (abs(filtered["LAT_WGS84"] - input_lat) < 0.02) &
    (abs(filtered["LONG_WGS84"] - input_lon) < 0.02)
]
ax3.scatter(local["LONG_WGS84"], local["LAT_WGS84"],
            alpha=0.3, s=5, color="red", label="Incidents")
ax3.scatter(input_lon, input_lat,
            s=200, color="blue", marker="*", label="Your Location", zorder=5)
ax3.set_title(f"Crime Activity Near {address}")
ax3.legend()
st.pyplot(fig3)
st.subheader("Location Assessment")
st.subheader("CPTED Factor Analysis")
risk_factors = []
protective_factors = []

if nearby_incidents >= 800:
    risk_factors.append("High concentration of reported incidents")
elif nearby_incidents >= 300:
    risk_factors.append("Moderate concentration of reported incidents")
else:
    protective_factors.append("Lower concentration of reported incidents")

station_passengers = nearest["AVG_PASSEN"]

if station_passengers >= 50000:
    risk_factors.append("Heavy transit activity")
elif station_passengers >= 25000:
    risk_factors.append("Moderate transit activity")
else:
    protective_factors.append("Lower transit activity")

st.write("### Risk Factors")
for factor in risk_factors:
    st.write(f"🔴 {factor}")

st.write("### Protective Factors")
for factor in protective_factors:
    st.write(f"🟢 {factor}")

if nearby_incidents >= 800:
    st.write(
        "This location is situated within a high incident concentration area. CPTED priorities should focus on natural surveillance, lighting, visibility, access control, and territorial reinforcement."
    )

elif nearby_incidents >= 300:
    st.write(
        "This location experiences a moderate level of reported incidents. CPTED strategies should focus on visibility, maintenance, and supporting positive activity generators."
    )

else:
    st.write(
        "This location experiences a relatively low concentration of reported incidents. CPTED efforts should focus on maintaining existing safety conditions and monitoring future trends."
    )
st.header(f"Top TTC Stations for {selected_crime}")
station_results = []
for _, station in stations.iterrows():
    nearby = (
        ((filtered["LAT_WGS84"] - station["latitude"])**2 +
         (filtered["LONG_WGS84"] - station["longitude"])**2)**0.5)
    count = (nearby < 0.0025).sum()
    station_results.append({
    "Station": station["STATION"],
    "Incidents Nearby": count,
    "Daily Passengers": station["AVG_PASSEN"]
})

station_ranking = pd.DataFrame(station_results)

station_ranking["Risk Score"] = (
    station_ranking["Incidents Nearby"] / station_ranking["Daily Passengers"]
) * 10000

station_ranking = station_ranking.sort_values("Risk Score", ascending=False).head(10)
st.dataframe(station_ranking, use_container_width=True)

st.header("TTC Station Lookup")

selected_station = st.selectbox(
    "Select a TTC Station",
    sorted(station_ranking["Station"].unique())
)

station_info = station_ranking[
    station_ranking["Station"] == selected_station
]

station_row = station_info.iloc[0]

st.metric(
    "Risk Score",
    round(station_row["Risk Score"], 1)
)

st.write(f"**Incidents Nearby:** {int(station_row['Incidents Nearby'])}")
st.write(f"**Daily Passengers:** {int(station_row['Daily Passengers'])}")

if station_row["Risk Score"] > 400:
    st.error("High CPTED Risk Area")
elif station_row["Risk Score"] > 200:
    st.warning("Moderate CPTED Risk Area")
else:
    st.success("Lower CPTED Risk Area")

st.header("Multi-Factor CPTED Score")

filtered = filtered[filtered["NEIGHBOURHOOD_CLEAN"] != "NSA"]
hood_stats = filtered.groupby("NEIGHBOURHOOD_CLEAN").agg(
    Incidents=("CRIME_TYPE", "count"),
    Night_Incidents=("OCC_HOUR", lambda x: (x >= 20).sum()),
    Outside_Incidents=("PREMISES_TYPE", lambda x: (x == "Outside").sum())
).reset_index()

hood_stats["Night_Ratio"] = (hood_stats["Night_Incidents"] / hood_stats["Incidents"]).round(2)
hood_stats["Outside_Ratio"] = (hood_stats["Outside_Incidents"] / hood_stats["Incidents"]).round(2)

hood_stats = hood_stats.merge(
    population, left_on="NEIGHBOURHOOD_CLEAN", right_on="Neighbourhood", how="left"
)

hood_stats["Crime_Rate"] = (hood_stats["Incidents"] / hood_stats["Population"]) * 1000
hood_stats["Crime_Rate"] = hood_stats["Crime_Rate"].fillna(hood_stats["Incidents"])

max_rate = hood_stats["Crime_Rate"].max()
hood_stats["CPTED_Score"] = (
    (hood_stats["Crime_Rate"] / max_rate * 60) +
    (hood_stats["Night_Ratio"] * 20) +
    (hood_stats["Outside_Ratio"] * 20)
).round(1)

hood_stats = hood_stats.sort_values("CPTED_Score", ascending=False)

st.dataframe(
    hood_stats[["NEIGHBOURHOOD_CLEAN", "Incidents", "Population", "Crime_Rate", "Night_Ratio", "Outside_Ratio", "CPTED_Score"]]
    .head(10)
    .rename(columns={"NEIGHBOURHOOD_CLEAN": "Neighbourhood"})
    .reset_index(drop=True),
    use_container_width=True
)
st.header("Crime Trend Over Time")

yearly = filtered.groupby("OCC_YEAR").size()
yearly = yearly[(yearly.index >= 2014) & (yearly.index < 2026)]
fig7, ax7 = plt.subplots(figsize=(10, 4))
yearly.plot(kind="line", ax=ax7, color="crimson", marker="o")
ax7.set_title(f"{selected_crime} Trend 2014-Present")
ax7.set_xlabel("Year")
ax7.set_ylabel("Incidents")
plt.tight_layout()
st.pyplot(fig7)

if yearly.iloc[-1] > yearly.iloc[0]:
    st.write("**Trend: Increasing** — CPTED interventions increasingly important")
else:
    st.write("**Trend: Decreasing** — existing interventions showing impact")
st.header("Crime by Location Type")

premises = filtered["PREMISES_TYPE"].value_counts()

fig5, ax5 = plt.subplots(figsize=(10, 4))
premises.sort_values().plot(kind="barh", ax=ax5, color="darkorange")
ax5.set_title(f"{selected_crime} by Premises Type")
ax5.set_xlabel("Number of Incidents")
plt.tight_layout()
st.pyplot(fig5)

top_premises = premises.index[0]
st.write(f"**Most common location:** {top_premises}")
st.header("Time of Day Analysis")

hourly = filtered.groupby("OCC_HOUR").size()

fig4, ax4 = plt.subplots(figsize=(10, 4))
hourly.plot(kind="bar", ax=ax4, color="crimson")
ax4.set_title(f"{selected_crime} by Hour of Day")
ax4.set_xlabel("Hour")
ax4.set_ylabel("Incidents")
plt.tight_layout()
st.pyplot(fig4)

peak_hour = hourly[hourly.index > 0].idxmax()
st.write(f"**Peak hour for {selected_crime}:** {peak_hour}:00")
st.header("CPTED Analysis")
cpted_insights = {
    "Assault": """
**Primary CPTED Factors:**
- Natural surveillance failures in high density areas
- Inadequate lighting in nighttime hotspots
- Access control failures in apartment buildings
- Lack of territorial reinforcement in public spaces

**Recommended Interventions:**
- Improve lighting in top neighbourhood hotspots
- Redesign building entrances for natural surveillance
- Increase mixed use development to add eyes on street
    """,
    "Break & Enter": """
**Primary CPTED Factors:**
- Weak access control on residential properties
- Poor natural surveillance between properties
- Lack of territorial reinforcement in residential areas

**Recommended Interventions:**
- Improve boundary definition between public and private space
- Enhance lighting in residential areas
- Encourage neighbourhood watch programs
    """,
    "Robbery": """
**Primary CPTED Factors:**
- High pedestrian density with poor natural surveillance
- Transit congregation points with limited visibility
- Escape route availability in dense urban areas

**Recommended Interventions:**
- Improve lighting at transit stops
- Reduce escape route options through design
- Increase natural surveillance through active frontages
    """,
    "Auto Theft": """
**Primary CPTED Factors:**
- Poor lighting in residential parking areas
- Lack of natural surveillance over parking
- Weak territorial reinforcement in parking lots

**Recommended Interventions:**
- Improve parking lot lighting and surveillance
- Design parking with natural oversight from buildings
- Implement access control for parking facilities
    """
}
st.markdown(cpted_insights[selected_crime])
