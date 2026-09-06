import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import datetime
import pandas as pd

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & UNIVERSAL RESPONSIVE STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Outdoor Planner Pro",
    page_icon="🌲",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
    /* Global Container Padding & Responsiveness */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 100%;
    }

    /* Mobile & Tablet Optimizations */
    @media (max-width: 992px) {
        .main .block-container {
            padding-top: 0.5rem;
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        h1 {
            font-size: 1.75rem !important;
        }
        h2 {
            font-size: 1.35rem !important;
        }
        h3 {
            font-size: 1.15rem !important;
        }
    }

    /* Score Badge Styling */
    .score-badge-optimal {
        background-color: #064e3b;
        color: #a7f3d0;
        padding: 12px;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        font-size: 1.1rem;
    }
    .score-badge-moderate {
        background-color: #78350f;
        color: #fde68a;
        padding: 12px;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        font-size: 1.1rem;
    }
    .score-badge-poor {
        background-color: #7f1d1d;
        color: #fecaca;
        padding: 12px;
        border-radius: 8px;
        font-weight: bold;
        text-align: center;
        font-size: 1.1rem;
    }
    </style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS & API INTEGRATIONS
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)
def fetch_weather_data(lat: float, lon: float):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,wind_speed_10m,uv_index&hourly=temperature_2m,precipitation_probability,uv_index&forecast_days=1"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to retrieve weather data: {e}")
        return None


@st.cache_data(ttl=1800)
def fetch_venue_density(lat: float, lon: float, radius: int = 1000):
    overpass_query = f"""
    [out:json][timeout:10];
    (
      node["leisure"="park"](around:{radius},{lat},{lon});
      node["amenity"="cafe"](around:{radius},{lat},{lon});
      node["tourism"="viewpoint"](around:{radius},{lat},{lon});
    );
    out count;
    """
    url = "https://overpass-api.de/api/interpreter"
    try:
        response = requests.post(url, data={"data": overpass_query}, timeout=10)
        response.raise_for_status()
        data = response.json()
        count = data.get("elements", [{}])[0].get("tags", {}).get("total", 0)
        return int(count)
    except Exception:
        return 5


def calculate_outdoor_score(temp_c, wind_kmh, precip_mm, humidity, venue_count, activity_type):
    score = 100
    temp_ranges = {
        "Hiking / Walking": (12, 22),
        "Cycling": (15, 24),
        "Outdoor Work / Reading": (18, 25),
        "Picnic": (20, 27)
    }
    ideal_min, ideal_max = temp_ranges.get(activity_type, (15, 25))

    if temp_c < ideal_min:
        score -= (ideal_min - temp_c) * 3
    elif temp_c > ideal_max:
        score -= (temp_c - ideal_max) * 4

    if wind_kmh > 20:
        score -= (wind_kmh - 20) * 1.5

    if precip_mm > 0:
        score -= min(50, precip_mm * 20 + 20)

    if humidity > 70:
        score -= (humidity - 70) * 0.5

    score += min(15, venue_count * 2)
    final_score = max(0, min(100, round(score)))

    if final_score >= 75:
        category, badge_style = "Optimal", "score-badge-optimal"
    elif final_score >= 45:
        category, badge_style = "Moderate", "score-badge-moderate"
    else:
        category, badge_style = "Poor", "score-badge-poor"

    return final_score, category, badge_style


# -----------------------------------------------------------------------------
# 3. SIDEBAR CONTROLS & METRICS CONFIGURATOR
# -----------------------------------------------------------------------------
st.sidebar.title("🌲 Planner Settings")

activity = st.sidebar.selectbox(
    "Select Planned Activity",
    ["Hiking / Walking", "Cycling", "Outdoor Work / Reading", "Picnic"]
)

units = st.sidebar.radio("Unit System", ["Metric (°C, km/h)", "Imperial (°F, mph)"], horizontal=True)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Dynamic Metrics Toggler")
available_metrics = ["Temperature", "Wind Speed", "Precipitation", "Humidity", "Nearby Amenities", "UV Index",
                     "Coordinates"]
selected_metrics = st.sidebar.multiselect(
    "Select metrics to display:",
    options=available_metrics,
    default=["Temperature", "Wind Speed", "Precipitation", "Humidity", "Nearby Amenities", "Coordinates"]
)

st.sidebar.markdown("---")
city_presets = {
    # North America
    "New York (USA)": (40.7128, -74.0060),
    "Los Angeles (USA)": (34.0522, -118.2437),
    "Toronto (Canada)": (43.6532, -79.3832),
    "Mexico City (Mexico)": (19.4326, -99.1332),

    # South America
    "São Paulo (Brazil)": (-23.5505, -46.6333),
    "Buenos Aires (Argentina)": (-34.6037, -58.3816),
    "Bogotá (Colombia)": (4.7110, -74.0721),
    "Santiago (Chile)": (-33.4489, -70.6693),

    # Europe
    "London (UK)": (51.5074, -0.1278),
    "Paris (France)": (48.8566, 2.3522),
    "Berlin (Germany)": (52.5200, 13.4050),
    "Rome (Italy)": (41.9028, 12.4964),
    "Madrid (Spain)": (40.4168, -3.7038),

    # Asia
    "Tokyo (Japan)": (35.6762, 139.6503),
    "Singapore": (1.3521, 103.8198),
    "Dubai (UAE)": (25.2048, 55.2708),
    "Mumbai (India)": (19.0760, 72.8777),
    "Beijing (China)": (39.9042, 116.4074),
    "Seoul (South Korea)": (37.5665, 126.9780),

    # Africa
    "Cairo (Egypt)": (30.0444, 31.2357),
    "Lagos (Nigeria)": (6.5244, 3.3792),
    "Johannesburg (South Africa)": (-26.2041, 28.0473),
    "Nairobi (Kenya)": (-1.2921, 36.8219),

    # Oceania
    "Sydney (Australia)": (-33.8688, 151.2093),
    "Melbourne (Australia)": (-37.8136, 144.9631),
    "Auckland (New Zealand)": (-36.8485, 174.7633)
}

selected_city = st.sidebar.selectbox("Jump to City", list(city_presets.keys()))
default_lat, default_lon = city_presets[selected_city]

if "lat" not in st.session_state:
    st.session_state.lat = default_lat
if "lon" not in st.session_state:
    st.session_state.lon = default_lon

if st.sidebar.button("Reset Pin to Selected City"):
    st.session_state.lat = default_lat
    st.session_state.lon = default_lon

# -----------------------------------------------------------------------------
# 4. MAIN LAYOUT (RESPONSIVE COLUMNS)
# -----------------------------------------------------------------------------
st.title("Outdoor Planner Pro")
st.caption("Cross-platform responsive outdoor conditions evaluator powered by live spatial data.")

# Responsive column split: collapses cleanly on mobile viewports
col_map, col_metrics = st.columns([1.2, 1], gap="medium")

with col_map:
    st.subheader("1. Pick Your Spot")
    m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=12)
    folium.Marker(
        [st.session_state.lat, st.session_state.lon],
        popup="Selected Location",
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)

    map_data = st_folium(m, height=400, width="100%")

    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lon = map_data["last_clicked"]["lng"]
        if clicked_lat != st.session_state.lat or clicked_lon != st.session_state.lon:
            st.session_state.lat = clicked_lat
            st.session_state.lon = clicked_lon
            st.rerun()

with col_metrics:
    st.subheader("2. Real-Time Evaluation")
    weather = fetch_weather_data(st.session_state.lat, st.session_state.lon)
    venues = fetch_venue_density(st.session_state.lat, st.session_state.lon)

    if weather and "current" in weather:
        curr = weather["current"]
        temp_c = curr.get("temperature_2m", 0.0)
        feels_like_c = curr.get("apparent_temperature", 0.0)
        wind_kmh = curr.get("wind_speed_10m", 0.0)
        precip_mm = curr.get("precipitation", 0.0)
        humidity = curr.get("relative_humidity_2m", 0)
        uv_index = curr.get("uv_index", 0.0)

        # Unit Conversions
        if "Imperial" in units:
            temp = round(temp_c * 9 / 5 + 32, 1)
            feels_like = round(feels_like_c * 9 / 5 + 32, 1)
            temp_unit, wind_unit, precip_unit = "°F", "mph", "in"
            wind = round(wind_kmh * 0.621371, 1)
            precip = round(precip_mm * 0.0393701, 2)
        else:
            temp, feels_like = temp_c, feels_like_c
            temp_unit, wind_unit, precip_unit = "°C", "km/h", "mm"
            wind, precip = wind_kmh, precip_mm

        score, rating, badge_style = calculate_outdoor_score(
            temp_c, wind_kmh, precip_mm, humidity, venues, activity
        )

        st.markdown(
            f'<div class="{badge_style}">'
            f'Condition Rating: {rating} ({score} / 100)<br>'
            f'<span style="font-size: 0.85rem; font-weight: normal;">Tailored for: {activity}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # Render dynamically selected metrics in grid columns
        metric_values = {
            "Temperature": (f"{temp} {temp_unit}", f"Feels like {feels_like} {temp_unit}"),
            "Wind Speed": (f"{wind} {wind_unit}", None),
            "Precipitation": (f"{precip} {precip_unit}", None),
            "Humidity": (f"{humidity}%", None),
            "Nearby Amenities": (f"{venues} spots", "Within 1km radius"),
            "UV Index": (str(uv_index), "Solar intensity"),
            "Coordinates": (f"{round(st.session_state.lat, 2)}, {round(st.session_state.lon, 2)}", "Lat / Lon")
        }

        cols = st.columns(2)
        idx = 0
        for m_name in selected_metrics:
            if m_name in metric_values:
                val, sub = metric_values[m_name]
                with cols[idx % 2]:
                    st.metric(m_name, val, sub)
                idx += 1
    else:
        st.warning("Fetching environmental conditions...")

# -----------------------------------------------------------------------------
# 5. HOURLY FORECAST CHART
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("3. 24-Hour Outlook")

if weather and "hourly" in weather:
    hourly = weather["hourly"]
    temps = hourly["temperature_2m"][:24]
    if "Imperial" in units:
        temps = [round(t * 9 / 5 + 32, 1) for t in temps]
        temp_label = "Temperature (°F)"
    else:
        temp_label = "Temperature (°C)"

    df_hourly = pd.DataFrame({
        "Time": [datetime.datetime.fromisoformat(t).strftime("%H") + ":00" for t in hourly["time"][:24]],
        temp_label: temps,
        "Rain Probability (%)": hourly["precipitation_probability"][:24]
    }).set_index("Time")

    tab1, tab2 = st.tabs(["Chart View", "Data Table View"])
    with tab1:
        st.line_chart(df_hourly)
    with tab2:
        st.dataframe(df_hourly, width="stretch")