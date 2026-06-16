
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json

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

df = load_data()

st.sidebar.header("Filters")
selected_crime = st.sidebar.selectbox("Crime Type", ["Assault", "Break & Enter", "Robbery", "Auto Theft"])
time_filter = st.sidebar.slider("Hour of Day", 0, 23, (0, 23))
show_poles = st.sidebar.checkbox("Show Street Pole Infrastructure")

filtered = df[df["CRIME_TYPE"] == selected_crime]
filtered = filtered[
    (filtered["OCC_HOUR"] >= time_filter[0]) &
    (filtered["OCC_HOUR"] <= time_filter[1])
]

st.write(f"**{len(filtered):,} incidents** match your filters")

st.header("Crime Map")
fig, ax = plt.subplots(figsize=(10, 7))
ax.scatter(filtered["LONG_WGS84"], filtered["LAT_WGS84"],
           alpha=0.1, s=1, color="red", label=selected_crime)

if show_poles:
    poles = load_poles()
    ax.scatter(poles["LONG"], poles["LAT"],
               alpha=0.1, s=1, color="deepskyblue", label="Street Poles")
    ax.legend(markerscale=8)

ax.set_title(f"{selected_crime} - Hours {time_filter[0]}:00 to {time_filter[1]}:00")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
st.pyplot(fig)

st.header("Top 10 High Risk Neighbourhoods")
top_hoods = filtered["NEIGHBOURHOOD_158"].value_counts().head(10)
fig2, ax2 = plt.subplots(figsize=(10, 5))
top_hoods.plot(kind="barh", ax=ax2, color="crimson")
ax2.set_title(f"Top Neighbourhoods for {selected_crime}")
ax2.set_xlabel("Number of Incidents")
plt.tight_layout()
st.pyplot(fig2)

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
