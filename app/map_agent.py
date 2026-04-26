import streamlit as st

import folium
from streamlit_folium import st_folium
import json
import googlemaps
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Map Agent",
    page_icon="🗺️",
    layout="wide"
)

# --- GOOGLE MAPS CONFIG ---
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
if GOOGLE_MAPS_API_KEY:
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
else:
    gmaps = None

# --- CORE PROCESSING FUNCTION ---
def process_map_dispatch(location, services):
    """
    Process incident location and find nearby authorities
    Returns structured result with authorities organized by service type
    """
    if not gmaps:
        return {"error": "Google Maps API key not configured"}
    
    try:
        # 🔥 STEP 1: Geocode
        geo = gmaps.geocode(location)
        if not geo:
            return {"error": "Geocoding failed"}

        lat = geo[0]["geometry"]["location"]["lat"]
        lng = geo[0]["geometry"]["location"]["lng"]

        service_map = {
            "fire": "fire_station",
            "ambulance": "hospital",
            "police": "police"
        }

        authorities = []

        # 🔥 STEP 2: Collect authorities for each service
        for s in services:
            collected = []

            if s == "ambulance":
                queries = [
                    f"emergency care hospital near {location}",
                    f"government hospital near {location}",
                    f"multi speciality hospital near {location}"
                ]

                for query in queries:
                    places = gmaps.places(query=query)

                    for p in places.get("results", []):
                        name = (p.get("name") or "").lower()
                        rating = p.get("rating", 0)

                        if rating < 3.8:
                            continue

                        loc = p.get("geometry", {}).get("location")
                        if not loc:
                            continue

                        collected.append({
                            "name": p.get("name"),
                            "service": s,
                            "lat": loc["lat"],
                            "lng": loc["lng"]
                        })

                    if len(collected) >= 3:
                        break

            else:
                places = gmaps.places_nearby(
                    location=(lat, lng),
                    radius=5000,
                    type=service_map.get(s)
                )

                for p in places.get("results", []):
                    name = (p.get("name") or "").lower()
                    loc = p.get("geometry", {}).get("location")
                    if not loc:
                        continue

                    # 🔥 FIRE STATION FILTERING
                    if s == "fire":
                        exclude_keywords = [
                            "equipment", "shop", "store", "supply", "supplies",
                            "sales", "retail", "vendor", "distributor",
                            "trade", "commerce", "merchant", "dealer", "export"
                        ]
                        required_keywords = [
                            "fire", "station", "department", "firefighting", "brigade"
                        ]
                        
                        has_required = any(keyword in name for keyword in required_keywords)
                        has_excluded = any(keyword in name for keyword in exclude_keywords)
                        
                        if not has_required or has_excluded:
                            continue

                    collected.append({
                        "name": p.get("name"),
                        "service": s,
                        "lat": loc["lat"],
                        "lng": loc["lng"]
                    })

            # Remove duplicates
            unique = {}
            for a in collected:
                unique[a["name"]] = a

            # 🔥 LIMIT TO 2-5 PER SERVICE
            service_authorities = list(unique.values())
            
            if service_authorities:
                service_authorities.sort(key=lambda a: (a["lat"] - lat) ** 2 + (a["lng"] - lng) ** 2)
                service_authorities = service_authorities[:5]
            
            if len(service_authorities) == 0:
                continue
            
            authorities.extend(service_authorities)

        if not authorities:
            return {"error": "No authorities found"}

        # 🔥 SORT ALL BY DISTANCE
        authorities.sort(key=lambda a: (a["lat"] - lat) ** 2 + (a["lng"] - lng) ** 2)

        # 🔥 DISTANCE MATRIX
        destinations = [f"{a['lat']},{a['lng']}" for a in authorities]
        matrix = gmaps.distance_matrix(
            origins=[f"{lat},{lng}"],
            destinations=destinations,
            mode="driving"
        )

        elements = matrix["rows"][0]["elements"]

        for i, e in enumerate(elements):
            if e["status"] == "OK":
                authorities[i]["distance_km"] = round(e["distance"]["value"] / 1000, 2)
                authorities[i]["eta"] = e["duration"]["value"] // 60
            else:
                authorities[i]["distance_km"] = None
                authorities[i]["eta"] = None

            authorities[i]["alert_sent"] = False

        authorities.sort(key=lambda x: x.get("distance_km") or 9999)

        # 🔥 ORGANIZE BY SERVICE TYPE
        primaries_by_service = {}
        all_by_service = {}

        for service in services:
            all_by_service[service] = [a for a in authorities if a.get("service") == service]
            if all_by_service[service]:
                primaries_by_service[service] = all_by_service[service][0]
                all_by_service[service][0]["alert_sent"] = True

        return {
            "location": location,
            "coordinates": {"lat": lat, "lng": lng},
            "requested_services": services,
            "primary": authorities[0] if authorities else None,
            "primaries_by_service": primaries_by_service,
            "authorities_by_service": all_by_service,
            "authorities": authorities
        }

    except Exception as e:
        return {"error": str(e)}

# --- CUSTOM CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Barlow', sans-serif; }
.stApp { background: #080d18; color: #dde6f5; }
h1, h2, h3 { font-family: 'Share Tech Mono', monospace !important; color: #f0a500 !important; }
.authority-card {
    background: #0f1828;
    border-left: 3px solid #2ecc71;
    padding: 12px 16px;
    border-radius: 3px 10px 10px 3px;
    margin: 8px 0;
    font-size: 0.92rem;
    color: #dde6f5;
}
.primary-card {
    background: #0e1f10;
    border-left: 3px solid #4caf50;
    padding: 12px 16px;
    border-radius: 3px 10px 10px 3px;
    margin: 12px 0;
    font-size: 0.95rem;
    color: #7ed47e;
}
.stButton > button {
    background: #b87800 !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'Barlow', sans-serif !important;
    font-weight: 700 !important;
}
.stButton > button:hover { background: #8a5a00 !important; }
</style>
""", unsafe_allow_html=True)

st.title("🗺️ Emergency Authorities Map Agent")

# --- SESSION STATE ---
# --- LOAD TRIAGE DATA ---

if "data" not in st.session_state:
    st.session_state.data = None

if "auto_loaded" not in st.session_state:
    st.session_state.auto_loaded = False
# --- LOAD TRIAGE DATA ---
if "shared_triage_json" in st.session_state and not st.session_state.auto_loaded:
    try:
        triage_data = json.loads(st.session_state.shared_triage_json)

        comms = triage_data.get("comms_payload", {})
        location = comms.get("affected_area")
        services = comms.get("required_services", [])

        if location and services:
            with st.spinner("Processing triage dispatch..."):
                data = process_map_dispatch(location, services)

            st.session_state.data = data
            st.session_state.auto_loaded = True

    except Exception as e:
        st.error(f"Triage → Map error: {e}")

# --- AUTO-LOAD FROM BACKEND ---


# --- MANUAL INPUT SECTION ---
with st.expander("📍 Manual Dispatch", expanded=not st.session_state.data):
    col1, col2 = st.columns(2)
    
    with col1:
        location = st.text_input("Location", key="location_input")
    
    with col2:
        services = st.multiselect(
            "Services",
            ["fire", "ambulance", "police"],
            key="services_input"
        )

    # --- DISPATCH BUTTON ---
    if st.button("🚀 Dispatch"):

        if not location or not services:
            st.error("Please provide location and at least one service")
            st.stop()

        with st.spinner("Finding nearest authorities..."):
            data = process_map_dispatch(location, services)

        if not data:
            st.error("❌ No data returned")
            st.stop()

        if "error" in data:
            st.error(f"❌ {data['error']}")
            st.stop()

        # ✅ Save result
        st.session_state.data = data
        st.session_state.auto_loaded = True
        st.rerun()

        
# --- USE STORED DATA ---
data = st.session_state.data

if not data:
    st.info("📍 Enter a location and click 'Dispatch' to fetch authorities, or send data from the Triage Agent")
    st.stop()

if "error" in data:
    st.error(data["error"])
    st.stop()

st.success("✅ Authorities alerted and dispatched")

# --- LOCATION & REQUESTED SERVICES ---
location = data.get("location", "Unknown")
services_requested = data.get("requested_services", [])
st.markdown(f"**Incident Location:** {location}")
st.markdown(f"**Services Requested:** {', '.join([s.upper() for s in services_requested])}")

st.divider()

# --- PRIMARIES BY SERVICE TYPE ---
primaries_by_service = data.get("primaries_by_service", {})

if primaries_by_service:
    st.markdown("### 🚨 Primary Response Authority by Service Type (ALERTED)")
    
    cols = st.columns(min(3, len(primaries_by_service)))
    
    for idx, (service, authority) in enumerate(primaries_by_service.items()):
        with cols[idx % len(cols)]:
            if authority:
                name = authority.get("name", "N/A")
                distance = authority.get("distance_km", "N/A")
                eta = authority.get("eta", "N/A")
                total_in_service = len(data.get("authorities_by_service", {}).get(service, []))
                
                service_icons = {
                    "fire": "🚒",
                    "ambulance": "🚑",
                    "police": "🚓"
                }
                icon = service_icons.get(service, "📍")
                
                st.markdown(f"""
<div class="primary-card">
<b>{icon} {service.upper()}</b><br>
<b>Primary (ALERTED):</b> {name}<br>
📍 Distance: {distance} km | ⏱️ ETA: {eta} min<br>
<i style="font-size: 0.8rem">({total_in_service} total authorities available)</i>
</div>
                """, unsafe_allow_html=True)
            else:
                st.warning(f"No {service} authority found")

# --- MAP ---
st.markdown("### 🗺️ Authority Locations Map")

coords = data.get("coordinates")
primaries_by_service = data.get("primaries_by_service", {})

if coords and "lat" in coords and "lng" in coords:
    try:
        m = folium.Map(
            location=[coords["lat"], coords["lng"]],
            zoom_start=13,
            control_scale=True
        )

        # Incident marker (in red)
        folium.Marker(
            [coords["lat"], coords["lng"]],
            popup="<b>🚨 Incident Location</b>",
            icon=folium.Icon(color="red", icon="exclamation-triangle")
        ).add_to(m)

        authorities = data.get("authorities", [])

        # Filter valid points
        valid_points = [
            a for a in authorities
            if isinstance(a, dict)
            and a.get("lat") is not None
            and a.get("lng") is not None
        ]

        valid_points = valid_points[:20]

        # Service type colors
        service_colors = {
            "fire": "orange",
            "ambulance": "blue",
            "police": "purple"
        }

        # Get primary names for each service
        primary_names = {s: auth.get("name") for s, auth in primaries_by_service.items()}

        # Add authority markers
        for i, a in enumerate(valid_points):
            name = a.get("name", "Unknown")
            dist = a.get("distance_km")
            service = a.get("service", "unknown")

            popup = f"<b>{name}</b><br>Service: {service.upper()}<br>Distance: {dist} km" if dist else f"<b>{name}</b><br>Service: {service.upper()}"

            # Check if this is a primary for its service type
            is_primary = name == primary_names.get(service)
            
            if is_primary:
                color = service_colors.get(service, "blue")
                icon_name = "shield"
            else:
                color = "gray"
                icon_name = "hospital"

            folium.Marker(
                [a["lat"], a["lng"]],
                popup=popup,
                icon=folium.Icon(color=color, icon=icon_name)
            ).add_to(m)

        st_folium(m, width=1200, height=600)

    except Exception as e:
        st.error(f"Map rendering failed: {e}")
else:
    st.warning("No valid coordinates for map")

# --- DETAILED AUTHORITY LIST ---
st.markdown("### 📡 All Nearby Authorities by Service Type")

authorities_by_service = data.get("authorities_by_service", {})
primaries_by_service = data.get("primaries_by_service", {})

service_icons = {
    "fire": "🚒",
    "ambulance": "🚑",
    "police": "🚓"
}

for service in services_requested:
    if service in authorities_by_service and authorities_by_service[service]:
        st.markdown(f"#### {service_icons.get(service, '📍')} {service.upper()}")
        
        authorities = authorities_by_service[service]
        primary_auth = primaries_by_service.get(service)
        
        for i, a in enumerate(authorities):
            name = a.get("name", "Unknown")
            distance = a.get("distance_km", "N/A")
            eta = a.get("eta", "N/A")
            alert_sent = "✅ Alert Sent" if a.get("alert_sent") else "⏳ Secondary"
            
            is_primary = (primary_auth and name == primary_auth.get("name"))
            badge = "🥇 PRIMARY" if is_primary else f"#{i+1}"
            
            # Color coding for alert status
            status_color = "#2ecc71" if a.get("alert_sent") else "#f0a500"
            
            st.markdown(f"""
<div class="authority-card" style="border-left-color: {status_color}">
<b>{badge} - {name}</b><br>
📍 Distance: {distance} km | ⏱️ ETA: {eta} min | Status: {alert_sent}
</div>
            """, unsafe_allow_html=True)
    else:
        st.warning(f"📍 {service.upper()}: Not enough nearby authorities found (need at least 2)")