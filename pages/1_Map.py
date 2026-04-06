import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import pydeck as pdk
from utils import (
    init_session_state, apply_filters,
    render_detail_view, render_footer, certainty_color,
)

st.set_page_config(page_title="Map — GLOBALISE Places", layout="wide")

init_session_state()
df = st.session_state.locations_df

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    if df is not None:
        st.metric("Total records", f"{len(df):,}")
        st.divider()

        display_cols = [
            "glob_id", "pref_label", "alt_labels", "types",
            "latitude", "longitude", "coord_certainty",
            "parent_region_pref_label", "ccodes",
        ]
        with st.expander("📊 Sample data (first 20 rows)"):
            st.dataframe(
                df[[c for c in display_cols if c in df.columns]].head(20),
                use_container_width=True,
            )
        st.divider()

    with st.expander("👥 About the data"):
        st.markdown(
            "Data created by Dung Thuy Pham e.a. for the GLOBALISE project. "
            "Available for download [here](https://doi.org/10.34894/UFFFNO)."
            "\n"
            "**Citation**:"
        )
        st.code(
            'Pham, Thuy Dung; Nijman, Brecht; Land, Ruben; Bellarykar, Nikhil; Tabroni, Roni; Yeh, Chun-ting; Rabecca Mathai, Meenu; van Wissen, Leon; Houwer, Andy; Widmer, Marc; Kuruppath, Manjusha, 2026, "GLOBALISE - Places in the Dutch East India Company Archives (1602-1799)", https://doi.org/10.34894/UFFFNO, DataverseNL, V3'
        )

    st.markdown(
        "App by [Kay Pepping](https://github.com/KayWP/). "
        "Bug reports welcome on Github."
    )

st.title("🗺️ Map view")

if df is None:
    st.warning("No data loaded. Please upload a file in the sidebar.", icon="📂")
    st.stop()

filtered_df = apply_filters(df, [], [], [])

# ── Build mappable data ────────────────────────────────────────────────────
map_df = filtered_df.copy()
map_df = map_df[
    pd.to_numeric(map_df["latitude"], errors="coerce").notna()
    & pd.to_numeric(map_df["longitude"], errors="coerce").notna()
]
map_df["latitude"] = pd.to_numeric(map_df["latitude"])
map_df["longitude"] = pd.to_numeric(map_df["longitude"])
map_df = map_df[~((map_df["latitude"] == 0) & (map_df["longitude"] == 0))]

if map_df.empty:
    st.info("No mappable coordinates in the current data.")
    st.stop()

map_df["color"] = map_df["coord_certainty"].apply(certainty_color)

pdk_cols = [
    "glob_id", "pref_label", "types", "latitude", "longitude",
    "coord_certainty", "parent_region_pref_label", "color",
]
map_df_pdk = map_df[[c for c in pdk_cols if c in map_df.columns]]

# ── Map ────────────────────────────────────────────────────────────────────
layer = pdk.Layer(
    "ScatterplotLayer",
    id="places-layer",
    data=map_df_pdk,
    get_position=["longitude", "latitude"],
    get_color="color",
    get_radius=5000,
    radius_min_pixels=4,
    radius_max_pixels=20,
    pickable=True,
    auto_highlight=True,
)

view_state = pdk.ViewState(
    latitude=map_df["latitude"].mean(),
    longitude=map_df["longitude"].mean(),
    zoom=2,
    pitch=0,
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    tooltip={
        "html": (
            "<b>{pref_label}</b><br/>"
            "<i>{types}</i><br/>"
            "📍 {latitude}, {longitude}<br/>"
            "Certainty: {coord_certainty}<br/>"
            "Region: {parent_region_pref_label}<br/>"
            "<i style='font-size:11px;opacity:0.8'>Click to see details below</i>"
        ),
        "style": {"color": "white", "fontSize": "13px"},
    },
)

event = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object")

st.caption("🟢 Certain &nbsp;&nbsp; 🟡 Approximate &nbsp;&nbsp; 🔴 Uncertain", unsafe_allow_html=True)
st.caption(f"Showing {len(map_df_pdk):,} locations")

# ── Resolve clicked point ──────────────────────────────────────────────────
clicked_id = None
try:
    sel = event.selection
    if hasattr(sel, "objects"):
        objects = sel.objects or {}
    elif isinstance(sel, dict):
        objects = sel.get("objects", {})
    else:
        objects = {}
    for rows in objects.values():
        if rows:
            clicked_id = rows[0].get("glob_id")
            break
except Exception:
    pass

# ── Detail panel below the map ─────────────────────────────────────────────
if clicked_id:
    st.session_state.selected_glob_id = clicked_id

if st.session_state.selected_glob_id is not None:
    st.divider()
    render_detail_view(df, st.session_state.selected_glob_id, back_label="✕ Close details")

render_footer()
