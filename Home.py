import streamlit as st
import pandas as pd
from utils import (
    init_session_state, render_sidebar, apply_filters,
    render_detail_view, render_footer, search_locations,
)

st.set_page_config(page_title="Search — GLOBALISE Places", layout="wide")

st.markdown("""
<style>
.result-card {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    background: #f8fafc;
}
.uncertain-badge {
    background: #fef3c7;
    color: #92400e;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.8rem;
}
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
df = st.session_state.locations_df
selected_types, selected_ccodes, selected_cert = render_sidebar(df)

st.title("🔍 Search places")
st.markdown("Search through the GLOBALISE places data using fuzzy matching.")

if df is None:
    st.warning("No data loaded. Please upload a file in the sidebar.", icon="📂")
    st.stop()

filtered_df = apply_filters(df, selected_types, selected_ccodes, selected_cert)

# ── Stats bar ──────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total records", f"{len(df):,}")
c2.metric("Filtered records", f"{len(filtered_df):,}")
c3.metric("Unique IDs", f"{filtered_df['glob_id'].nunique():,}")
c4.metric(
    "With coordinates",
    f"{pd.to_numeric(filtered_df['latitude'], errors='coerce').notna().sum():,}",
)

# ── Detail view (takes over the page) ─────────────────────────────────────
if st.session_state.selected_glob_id is not None:
    render_detail_view(df, st.session_state.selected_glob_id, back_label="← Back to search results")
    render_footer()
    st.stop()

# ── Search bar ─────────────────────────────────────────────────────────────
col_q, col_n = st.columns([4, 1])
with col_q:
    search_query = st.text_input(
        "🔍 Search place names",
        placeholder="e.g. Larike, Malabar, Batavia…",
        label_visibility="collapsed",
    )
with col_n:
    top_n = st.number_input(
        "Max results", min_value=5, max_value=100, value=10,
        label_visibility="collapsed",
    )

st.divider()

# ── Results ────────────────────────────────────────────────────────────────
if search_query:
    results = search_locations(filtered_df, search_query, top_n)

    if results.empty:
        st.warning("No matches found. Try a different search term.")
    else:
        st.markdown(f"### {len(results)} result(s) for **{search_query}**")

        for _, row in results.iterrows():
            alts = row["_alt_list"]
            types = row["_type_list"]
            score_pct = int(row["score"] * 100)
            cert = str(row["coord_certainty"]).lower()
            uncertain = cert in ("approximate", "uncertain")

            with st.expander(f"**{row['pref_label']}** — {score_pct}% match"):
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

                with col_btn:
                    if st.button("Full details", key=f"detail_{row['glob_id']}"):
                        st.session_state.selected_glob_id = row["glob_id"]
                        st.rerun()
else:
    with st.expander("📊 Sample data (first 20 rows)"):
        display_cols = [
            "glob_id", "pref_label", "alt_labels", "types",
            "latitude", "longitude", "coord_certainty",
            "parent_region_pref_label", "ccodes",
        ]
        st.dataframe(
            filtered_df[[c for c in display_cols if c in filtered_df.columns]].head(20),
            use_container_width=True,
        )

render_footer()
