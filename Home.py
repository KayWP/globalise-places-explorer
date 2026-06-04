import streamlit as st
import pandas as pd
from utils import (
    init_session_state, sync_query_params, set_selected,
    apply_filters, render_detail_view, render_sidebar,
    search_locations, build_transcription_query,
)

st.set_page_config(page_title="Search — GLOBALISE Places", layout="wide")

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
st.title("🔍 Search places")
st.markdown("Search through the GLOBALISE places data using fuzzy matching.")

if df is None:
    st.warning("No data loaded. Please upload a file to get started.", icon="📂")
    st.stop()

# ── Detail view (takes over the page) ─────────────────────────────────────
if st.session_state.selected_glob_id is not None:
    render_detail_view(df, st.session_state.selected_glob_id, back_label="← Back to search results")
    st.stop()

# ── Search bar ─────────────────────────────────────────────────────────────
col_q, col_n = st.columns([4, 1])
with col_q:
    search_query = st.text_input(
        "Search",
        placeholder="e.g. Larike, Malabar, Batavia…",
        label_visibility="collapsed",
    )
with col_n:
    top_n = st.number_input(
        "Max results", min_value=5, max_value=100, value=10,
        label_visibility="collapsed",
    )

# ── Inline filters ─────────────────────────────────────────────────────────
col_types, col_cert = st.columns(2)
with col_types:
    all_types = sorted({t for lst in df["_type_list"] for t in lst if t})
    selected_types = st.multiselect("Place type", all_types, placeholder="All types")
with col_cert:
    cert_options = sorted(df["coord_certainty"].dropna().unique())
    selected_cert = st.multiselect("Coordinate certainty", cert_options, placeholder="All certainties")

filtered_df = apply_filters(df, selected_types, [], selected_cert)

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
            all_terms = list({row["pref_label"]} | set(alts))

            with st.expander(f"**{row['pref_label']}** — {score_pct}% match"):
                col_info, col_btn = st.columns([5, 1])

                with col_info:
                    if pd.notna(row["parent_region_pref_label"]):
                        st.caption(f"📍 {row['parent_region_pref_label']}")
                    if types:
                        st.markdown(" ".join(
                            f"<span class='type-badge'>{t}</span>" for t in types
                        ), unsafe_allow_html=True)
                    st.code(row["glob_id"])
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
else:
    st.caption("Enter a search term above to find places.")
