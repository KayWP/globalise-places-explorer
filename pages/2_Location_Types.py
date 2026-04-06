import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import pydeck as pdk
from utils import (
    init_session_state, sync_query_params, set_selected,
    apply_filters, render_detail_view, render_sidebar,
    build_transcription_query, certainty_color,
)

st.set_page_config(page_title="Location Types — GLOBALISE Places", layout="wide")

st.markdown("""
<style>
.type-badge {
    background: #ede9fe;
    color: #5b21b6;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.8rem;
    margin-right: 4px;
}
</style>
""", unsafe_allow_html=True)

init_session_state()
sync_query_params()
df = st.session_state.locations_df

render_sidebar(df)

# ── Guard ──────────────────────────────────────────────────────────────────
st.title("🏷️ Location Types")
st.markdown("Explore all locations belonging to a particular type.")

if df is None:
    st.warning("No data loaded. Please upload a file to get started.", icon="📂")
    st.stop()

# ── Detail view (takes over the page) ─────────────────────────────────────
if st.session_state.selected_glob_id is not None:
    render_detail_view(df, st.session_state.selected_glob_id, back_label="← Back to location types")
    st.stop()

# ── Type selector ──────────────────────────────────────────────────────────
all_types = sorted({t for lst in df["_type_list"] for t in lst if t})

if not all_types:
    st.info("No location types found in the data.")
    st.stop()

type_counts = {
    t: int(df["_type_list"].apply(lambda lst: t in lst).sum())
    for t in all_types
}

col_type, col_cert = st.columns([3, 2])
with col_type:
    selected_type = st.selectbox(
        "Place type",
        options=all_types,
        format_func=lambda t: f"{t}  ({type_counts[t]:,})",
    )
with col_cert:
    cert_options = sorted(df["coord_certainty"].dropna().unique())
    selected_cert = st.multiselect(
        "Coordinate certainty", cert_options, placeholder="All certainties"
    )

st.divider()

# ── Filter to selected type ────────────────────────────────────────────────
type_df = df[df["_type_list"].apply(lambda lst: selected_type in lst)].copy()
if selected_cert:
    type_df = type_df[type_df["coord_certainty"].isin(selected_cert)]

type_df = type_df.sort_values("pref_label", ignore_index=True)

st.markdown(f"### {len(type_df):,} location(s) of type **{selected_type}**")

# ── Map ────────────────────────────────────────────────────────────────────
map_df = type_df.copy()
map_df = map_df[
    pd.to_numeric(map_df["latitude"], errors="coerce").notna()
    & pd.to_numeric(map_df["longitude"], errors="coerce").notna()
]
map_df["latitude"] = pd.to_numeric(map_df["latitude"])
map_df["longitude"] = pd.to_numeric(map_df["longitude"])
map_df = map_df[~((map_df["latitude"] == 0) & (map_df["longitude"] == 0))]
map_df["color"] = map_df["coord_certainty"].apply(certainty_color)

if not map_df.empty:
    pdk_cols = [
        "glob_id", "pref_label", "types", "latitude", "longitude",
        "coord_certainty", "parent_region_pref_label", "color",
    ]
    map_df_pdk = map_df[[c for c in pdk_cols if c in map_df.columns]]

    layer = pdk.Layer(
        "ScatterplotLayer",
        id="type-layer",
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

    unmapped = len(type_df) - len(map_df)
    note = f"Showing {len(map_df):,} mapped locations"
    if unmapped:
        note += f" · {unmapped:,} location(s) have no coordinates and are not shown"
    st.caption(note)

    # Resolve map click → detail view
    try:
        sel = event.selection
        objects = sel.objects if hasattr(sel, "objects") else sel.get("objects", {})
        for rows in objects.values():
            if rows:
                set_selected(rows[0].get("glob_id"))
                st.rerun()
    except Exception:
        pass
else:
    st.info("No mappable coordinates for this type / filter combination.")

st.divider()

# ── Results list ───────────────────────────────────────────────────────────
if type_df.empty:
    st.info("No locations match the current filters.")
else:
    for _, row in type_df.iterrows():
        alts = row["_alt_list"]
        types = row["_type_list"]
        cert = str(row["coord_certainty"]).lower()
        uncertain = cert in ("approximate", "uncertain")
        all_terms = list({row["pref_label"]} | set(alts))

        with st.expander(f"**{row['pref_label']}**"):
            col_info, col_btn = st.columns([5, 1])

            with col_info:
                if pd.notna(row["parent_region_pref_label"]):
                    st.caption(f"📍 {row['parent_region_pref_label']}")
                if types:
                    st.markdown(" ".join(
                        f"<span class='type-badge'>{t}</span>" for t in types
                    ), unsafe_allow_html=True)
                if alts:
                    st.caption(f"Also known as: {', '.join(alts[:5])}{'…' if len(alts) > 5 else ''}")
                if uncertain:
                    st.caption(f"⚠️ {cert} coordinates")
                lat = row["latitude"]
                lon = row["longitude"]
                if pd.notna(lat) and pd.notna(lon):
                    cert_icon = "🟢" if cert == "certain" else ("🟡" if cert == "approximate" else "🔴")
                    st.caption(f"{cert_icon} {lat:.5f}, {lon:.5f}")

                st.markdown("**GLOBALISE transcriptions query**")
                st.code(build_transcription_query(all_terms), language=None)

            with col_btn:
                if st.button("Full details", key=f"detail_{row['glob_id']}"):
                    set_selected(row["glob_id"])
                    st.rerun()
