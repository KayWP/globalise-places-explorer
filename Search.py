import streamlit as st
import pandas as pd
from utils import (
    search_locations, load_and_normalize,
    COMMON_CSS,
)
from detail_view import render_detail_view

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="GLOBALISE Places — Search",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(COMMON_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────

@st.cache_data
def load_default():
    try:
        raw = pd.read_excel("locationdata.xlsx", sheet_name="Sheet2 Places – Overview")
        return load_and_normalize(raw)
    except FileNotFoundError:
        return None


if "locations_df" not in st.session_state:
    default = load_default()
    st.session_state.locations_df = default
    st.session_state.uploaded_files_processed = set()

df = st.session_state.locations_df

# ─────────────────────────────────────────────
# Sidebar: filters + upload
# ─────────────────────────────────────────────

with st.sidebar:
    st.header("Filters")

    if df is not None:
        all_types = sorted({t for lst in df["_type_list"] for t in lst if t})
        selected_types = st.multiselect("Place type", all_types, placeholder="All types")

        all_ccodes = sorted(
            {c.strip() for raw in df["ccodes"].dropna() for c in str(raw).split("|") if c.strip()}
        )
        selected_ccodes = st.multiselect("Country code (ISO-2)", all_ccodes, placeholder="All countries")

        cert_options = sorted(df["coord_certainty"].dropna().unique())
        selected_cert = st.multiselect("Coordinate certainty", cert_options, placeholder="All")

        st.divider()
    else:
        selected_types = []
        selected_ccodes = []
        selected_cert = []

    st.subheader("Upload data")
    uploaded_file = st.file_uploader("CSV or XLSX file", type=["csv", "xlsx"])
    if uploaded_file is not None:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        if file_id not in st.session_state.uploaded_files_processed:
            try:
                if uploaded_file.name.endswith(".xlsx"):
                    xl = pd.ExcelFile(uploaded_file)
                    sheet = (
                        "Sheet2 Places – Overview"
                        if "Sheet2 Places – Overview" in xl.sheet_names
                        else xl.sheet_names[0]
                    )
                    extra_df = xl.parse(sheet)
                else:
                    extra_df = pd.read_csv(uploaded_file)
                extra_df = load_and_normalize(extra_df)

                if st.session_state.locations_df is not None:
                    st.session_state.locations_df = pd.concat(
                        [st.session_state.locations_df, extra_df], ignore_index=True
                    )
                else:
                    st.session_state.locations_df = extra_df

                st.session_state.uploaded_files_processed.add(file_id)
                st.success(f"✅ Added {len(extra_df)} records. Total: {len(st.session_state.locations_df)}")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error loading file: {e}")
        else:
            st.info(f"'{uploaded_file.name}' already loaded.")

    st.divider()
    st.markdown(
        "**Expected format (v2)**\n\n"
        "Multi-sheet XLSX. Primary sheet: `Sheet2 Places – Overview`.\n\n"
        "Columns: `glob_id`, `pref_label`, `alt_labels` (pipe-separated), "
        "`types`, `latitude`, `longitude`, `coord_certainty`, "
        "`coord_remarks`, `overall_remarks`, `ccodes`, `geonames_id`, "
        "`whg_id`, `amh_id`, `external_id`, `wikidata_id`, `tgn_id`, "
        "`parent_region`, `parent_region_pref_label`"
    )

# ─────────────────────────────────────────────
# Guard: no data
# ─────────────────────────────────────────────

st.title("🔍 Search places")

if df is None:
    st.warning("No default data found. Please upload a file in the sidebar to get started.", icon="📂")
    st.stop()

# ─────────────────────────────────────────────
# Apply filters
# ─────────────────────────────────────────────

filtered_df = df.copy()
if selected_types:
    filtered_df = filtered_df[
        filtered_df["_type_list"].apply(lambda lst: any(t in selected_types for t in lst))
    ]
if selected_ccodes:
    filtered_df = filtered_df[
        filtered_df["ccodes"].apply(
            lambda raw: any(c.strip() in selected_ccodes for c in str(raw).split("|"))
            if pd.notna(raw) else False
        )
    ]
if selected_cert:
    filtered_df = filtered_df[filtered_df["coord_certainty"].isin(selected_cert)]

# Stats bar
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total records", f"{len(df):,}")
c2.metric("Filtered records", f"{len(filtered_df):,}")
c3.metric("Unique IDs", f"{filtered_df['glob_id'].nunique():,}")
c4.metric(
    "With coordinates",
    f"{pd.to_numeric(filtered_df['latitude'], errors='coerce').notna().sum():,}",
)

# ─────────────────────────────────────────────
# Detail view (takes over the page)
# ─────────────────────────────────────────────

if "search_selected_glob_id" not in st.session_state:
    st.session_state.search_selected_glob_id = None

if st.session_state.search_selected_glob_id is not None:
    went_back = render_detail_view(df, st.session_state.search_selected_glob_id, "← Back to results")
    if went_back:
        st.session_state.search_selected_glob_id = None
        st.rerun()
    st.stop()

# ─────────────────────────────────────────────
# Search bar
# ─────────────────────────────────────────────

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

# ─────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────

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

            with st.expander(
                f"**{row['pref_label']}** — {row.get('parent_region_pref_label', '')}  `{score_pct}%`",
                expanded=False,
            ):
                col_info, col_btn = st.columns([5, 1])

                with col_info:
                    if types:
                        st.caption(", ".join(types))
                    if alts:
                        st.caption(f"Also known as: {', '.join(alts[:5])}{'…' if len(alts) > 5 else ''}")
                    if uncertain:
                        st.caption(f"⚠️ {cert} coordinates")
                    lat = row.get("latitude")
                    lon = row.get("longitude")
                    if pd.notna(lat) and pd.notna(lon):
                        st.caption(f"📍 {lat:.4f}, {lon:.4f}")

                with col_btn:
                    if st.button("Full details", key=f"detail_{row['glob_id']}"):
                        st.session_state.search_selected_glob_id = row["glob_id"]
                        st.rerun()

else:
    # Default: sample of data
    st.markdown("Enter a place name above to search.")
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

# ─────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────

st.divider()
with st.expander("👥 About the data"):
    st.markdown(
        "This application uses the data created by Dung Thuy Pham, Brecht Nijman, "
        "Ruben Land, Andy Houwer, Marc Widmer & Manjusha Kurrupath for the GLOBALISE project. "
        "Available for download [here](https://datasets.iisg.amsterdam/dataset.xhtml?persistentId=hdl:10622/WYVERW)."
    )
    st.code(
        'Pham, Thuy Dung; Nijman, Brecht; Land, Ruben; Houwer, Andy; Widmer, Marc; '
        'Kuruppath, Manjusha, 2025, "GLOBALISE - Places in the Dutch East India Company '
        'Archives (1602-1799)", https://hdl.handle.net/10622/WYVERW, IISH Data Collection, V1'
    )

st.markdown(
    "App by [Kay Pepping](https://github.com/KayWP/). "
    "Improvements and bug reports can be suggested on Github."
)
