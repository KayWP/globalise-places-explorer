import streamlit as st
import pandas as pd
from difflib import SequenceMatcher
import pydeck as pdk

# ─────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────

def fuzzy_match_score(s1, s2):
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def parse_alt_labels(raw):
    """Return a list of alt labels from a pipe-separated string, or []."""
    if pd.isna(raw) or not str(raw).strip():
        return []
    return [lbl.strip() for lbl in str(raw).split("|") if lbl.strip()]


def parse_types(raw):
    """Return a list of place types from a pipe-separated string, or []."""
    if pd.isna(raw) or not str(raw).strip():
        return []
    return [t.strip() for t in str(raw).split("|") if t.strip()]


def search_locations(df, query, top_n=10):
    if not query:
        return pd.DataFrame()

    scores = []
    for _, row in df.iterrows():
        pref = str(row["pref_label"])
        alts = row["_alt_list"]
        all_labels = [pref] + alts

        best = max(fuzzy_match_score(query, lbl) for lbl in all_labels)
        # Small bonus for exact prefix match on preferred label
        if pref.lower().startswith(query.lower()):
            best = min(best + 0.15, 1.0)

        scores.append({"_idx": row.name, "score": best})

    scores_df = pd.DataFrame(scores).set_index("_idx")
    top = scores_df[scores_df["score"] > 0.3].nlargest(top_n, "score")
    result = df.loc[top.index].copy()
    result["score"] = top["score"]
    return result.reset_index(drop=True)


def certainty_color(cert):
    return {
        "certain": [34, 197, 94, 200],
        "approximate": [251, 191, 36, 200],
        "uncertain": [239, 68, 68, 200],
    }.get(str(cert).lower(), [148, 163, 184, 200])


def create_map(df, zoom=2):
    map_df = df.copy()
    map_df = map_df[
        pd.to_numeric(map_df["latitude"], errors="coerce").notna()
        & pd.to_numeric(map_df["longitude"], errors="coerce").notna()
    ]
    map_df["latitude"] = pd.to_numeric(map_df["latitude"])
    map_df["longitude"] = pd.to_numeric(map_df["longitude"])
    map_df = map_df[~((map_df["latitude"] == 0) & (map_df["longitude"] == 0))]

    if map_df.empty:
        st.info("No mappable coordinates in current data.")
        return None

    map_df["color"] = map_df["coord_certainty"].apply(certainty_color)

    # Drop private/list columns that can confuse pydeck's JSON serialiser
    pdk_cols = ["glob_id", "pref_label", "types", "latitude", "longitude",
                "coord_certainty", "parent_region_pref_label", "color"]
    map_df = map_df[[c for c in pdk_cols if c in map_df.columns]]

    layer = pdk.Layer(
        "ScatterplotLayer",
        id="places-layer",
        data=map_df,
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
        zoom=zoom,
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
                "<i style='font-size:11px;opacity:0.8'>Click to open detail view</i>"
            ),
            "style": {"color": "white", "fontSize": "13px"},
        },
    )

    event = st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object")

    st.caption(
        "🟢 Certain &nbsp;&nbsp; 🟡 Approximate &nbsp;&nbsp; 🔴 Uncertain"
    )

    with st.expander("🐛 Debug: raw click event", expanded=False):
        try:
            st.write(event.selection)
        except Exception as e:
            st.write(f"Error reading selection: {e}")

    # Return the glob_id of the clicked point, if any
    try:
        sel = event.selection
        # selection may be a dict or an object with attribute access
        if hasattr(sel, "objects"):
            objects = sel.objects or {}
        elif isinstance(sel, dict):
            objects = sel.get("objects", {})
        else:
            objects = {}

        # Iterate all layer keys — the exact key depends on pydeck version
        for rows in objects.values():
            if rows:
                return rows[0].get("glob_id")
    except Exception:
        pass
    return None


def build_transcription_url(terms):
    base = "https://transcriptions.globalise.huygens.knaw.nl/?query[fullText]="
    query = "%20OR%20".join([f'"{t}"' for t in terms])
    return (base + query).replace(" ", "%20")


def load_and_normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise a raw DataFrame (v2 schema) for use in the app."""
    df.columns = df.columns.str.strip()
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    # Lowercase coordinate column names if needed
    df.rename(
        columns={"Latitude": "latitude", "Longitude": "longitude"},
        inplace=True,
    )

    # Ensure expected columns exist with sensible defaults
    for col in [
        "glob_id", "pref_label", "alt_labels", "types",
        "latitude", "longitude", "coord_certainty", "coord_remarks",
        "coord_remarks_source", "coord_source",
        "overall_remarks", "overall_remarks_source",
        "ccodes", "esta_id", "geonames_id",
        "whg_id", "amh_id", "external_id",
        "wikidata_id", "tgn_id",
        "parent_region", "parent_region_pref_label",
    ]:
        if col not in df.columns:
            df[col] = pd.NA

    # Pre-parse list columns for performance
    df["_alt_list"] = df["alt_labels"].apply(parse_alt_labels)
    df["_type_list"] = df["types"].apply(parse_types)

    return df


# ─────────────────────────────────────────────
# Page setup
# ─────────────────────────────────────────────

st.set_page_config(page_title="GLOBALISE places search", layout="wide")

st.markdown(
    """
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
    """,
    unsafe_allow_html=True,
)

st.title("🗺️ GLOBALISE places dataset search")
st.markdown("Search through the GLOBALISE places data using fuzzy search.")

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
    if default is not None:
        st.session_state.locations_df = default
        st.session_state.uploaded_files_processed = set()
    else:
        st.session_state.locations_df = None
        st.session_state.uploaded_files_processed = set()

df = st.session_state.locations_df

if df is None:
    st.warning(
        "No default data found. Please upload a file below to get started.",
        icon="📂",
    )

# ─────────────────────────────────────────────
# Sidebar filters
# ─────────────────────────────────────────────

with st.sidebar:
    st.header("Filters")

    if df is not None:
        # Place type filter
        all_types = sorted(
            {t for lst in df["_type_list"] for t in lst if t}
        )
        selected_types = st.multiselect(
            "Place type", all_types, placeholder="All types"
        )

        # Country code filter
        all_ccodes = sorted(
            {c.strip() for raw in df["ccodes"].dropna() for c in str(raw).split("|") if c.strip()}
        )
        selected_ccodes = st.multiselect(
            "Country code (ISO-2)", all_ccodes, placeholder="All countries"
        )

        # Coordinate certainty filter
        cert_options = sorted(df["coord_certainty"].dropna().unique())
        selected_cert = st.multiselect(
            "Coordinate certainty", cert_options, placeholder="All"
        )

        st.divider()

    # Upload
    st.subheader("Upload data")
    uploaded_file = st.file_uploader(
        "CSV or XLSX file", type=["csv", "xlsx"]
    )
    if uploaded_file is not None:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        if file_id not in st.session_state.uploaded_files_processed:
            try:
                if uploaded_file.name.endswith(".xlsx"):
                    xl = pd.ExcelFile(uploaded_file)
                    sheet = "Sheet2 Places – Overview" if "Sheet2 Places – Overview" in xl.sheet_names else xl.sheet_names[0]
                    extra_df = xl.parse(sheet)
                else:
                    extra_df = pd.read_csv(uploaded_file)
                extra_df = load_and_normalize(extra_df)

                if st.session_state.locations_df is not None:
                    st.session_state.locations_df = pd.concat(
                        [st.session_state.locations_df, extra_df],
                        ignore_index=True,
                    )
                else:
                    st.session_state.locations_df = extra_df

                st.session_state.uploaded_files_processed.add(file_id)
                st.success(
                    f"✅ Added {len(extra_df)} records. "
                    f"Total: {len(st.session_state.locations_df)}"
                )
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
# Main content
# ─────────────────────────────────────────────

if df is None:
    st.stop()

# Apply sidebar filters
filtered_df = df.copy()
if selected_types:
    filtered_df = filtered_df[
        filtered_df["_type_list"].apply(
            lambda lst: any(t in selected_types for t in lst)
        )
    ]
if selected_ccodes:
    filtered_df = filtered_df[
        filtered_df["ccodes"].apply(
            lambda raw: any(
                c.strip() in selected_ccodes
                for c in str(raw).split("|")
            )
            if pd.notna(raw)
            else False
        )
    ]
if selected_cert:
    filtered_df = filtered_df[
        filtered_df["coord_certainty"].isin(selected_cert)
    ]

# Stats bar
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total records", f"{len(df):,}")
c2.metric("Filtered records", f"{len(filtered_df):,}")
c3.metric("Unique IDs", f"{filtered_df['glob_id'].nunique():,}")
c4.metric(
    "With coordinates",
    f"{pd.to_numeric(filtered_df['latitude'], errors='coerce').notna().sum():,}",
)

# Search bar
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
        label_visibility="collapsed"
    )

# Compute results early so the map can use them
if search_query:
    results = search_locations(filtered_df, search_query, top_n)
    map_data = results if not results.empty else filtered_df
    map_zoom = 4 if (not results.empty and len(results) <= 20) else 2
    map_label = f"🗺️ Map view — {len(results)} result(s)" if not results.empty else "🗺️ Map view"
else:
    results = None
    map_data = filtered_df
    map_zoom = 2
    map_label = "🗺️ Map view"

# Map — auto-expanded when searching
with st.expander(map_label, expanded=bool(search_query)):
    clicked_id = create_map(map_data, zoom=map_zoom)
    if clicked_id:
        st.session_state.selected_glob_id = clicked_id
        st.rerun()

st.divider()

# ─────────────────────────────────────────────
# Detail page
# ─────────────────────────────────────────────

if "selected_glob_id" not in st.session_state:
    st.session_state.selected_glob_id = None

if st.session_state.selected_glob_id is not None:
    row = df[df["glob_id"] == st.session_state.selected_glob_id].iloc[0]
    alts = row["_alt_list"]
    types = row["_type_list"]
    cert = str(row["coord_certainty"]).lower()
    uncertain = cert in ("approximate", "uncertain")
    all_terms = list({row["pref_label"]} | set(alts))

    if st.button("← Back to results"):
        st.session_state.selected_glob_id = None
        st.rerun()

    st.markdown(f"## {row['pref_label']}")
    if types:
        st.caption(" · ".join(types))

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**ID**")
        st.code(row["glob_id"], language=None)

        if pd.notna(row["parent_region_pref_label"]):
            st.markdown(f"**Region:** {row['parent_region_pref_label']}")
        if pd.notna(row["ccodes"]):
            st.markdown(f"**Country code:** {row['ccodes']}")
        if alts:
            st.markdown(f"**Alternative names:** {', '.join(alts)}")

    with col_b:
        lat = row["latitude"]
        lon = row["longitude"]
        if pd.notna(lat) and pd.notna(lon):
            cert_icon = "🟢" if cert == "certain" else ("🟡" if cert == "approximate" else "🔴")
            st.markdown(f"**Coordinates:** {lat:.5f}, {lon:.5f}")
            st.markdown(f"**Certainty:** {cert_icon} {cert}")
            if pd.notna(row["coord_source"]) and str(row["coord_source"]).strip():
                st.caption(f"Source: {row['coord_source']}")
            if pd.notna(row["coord_remarks"]) and str(row["coord_remarks"]).strip():
                st.caption(f"_{row['coord_remarks']}_")

            single_row = pd.DataFrame([{"latitude": lat, "longitude": lon,
                                        "pref_label": row["pref_label"],
                                        "coord_certainty": cert}])
            single_row["color"] = single_row["coord_certainty"].apply(certainty_color)
            layer = pdk.Layer("ScatterplotLayer", data=single_row,
                              get_position=["longitude", "latitude"],
                              get_color="color", get_radius=30000,
                              radius_min_pixels=6, radius_max_pixels=20)
            view = pdk.ViewState(latitude=lat, longitude=lon, zoom=4)
            st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view,
                                     tooltip={"html": "<b>{pref_label}</b>",
                                              "style": {"color": "white"}}))

    if pd.notna(row["overall_remarks"]) and str(row["overall_remarks"]).strip():
        st.divider()
        st.markdown("**Remarks**")
        st.markdown(str(row["overall_remarks"]))

    st.divider()
    st.markdown("**External links**")
    links = [f"[🔎 Search Transcriptions]({build_transcription_url(all_terms)})"]
    if pd.notna(row["geonames_id"]) and str(row["geonames_id"]).startswith("http"):
        links.append(f"[🌍 GeoNames]({row['geonames_id']})")
    if pd.notna(row["whg_id"]) and str(row["whg_id"]).startswith("http"):
        links.append(f"[🗺️ WHG]({row['whg_id']})")
    if pd.notna(row["amh_id"]) and str(row["amh_id"]).strip():
        links.append(f"[📚 AMH]({row['amh_id']})")
    if pd.notna(row["wikidata_id"]) and str(row["wikidata_id"]).strip():
        wikidata_val = str(row["wikidata_id"]).strip()
        wikidata_url = wikidata_val if wikidata_val.startswith("http") else f"https://www.wikidata.org/wiki/{wikidata_val}"
        links.append(f"[🔷 Wikidata]({wikidata_url})")
    if pd.notna(row["tgn_id"]) and str(row["tgn_id"]).strip():
        tgn_val = str(row["tgn_id"]).strip()
        tgn_url = tgn_val if tgn_val.startswith("http") else f"http://vocab.getty.edu/tgn/{tgn_val}"
        links.append(f"[🏛️ Getty TGN]({tgn_url})")
    if pd.notna(row["external_id"]) and str(row["external_id"]).startswith("http"):
        links.append(f"[🔗 External]({row['external_id']})")
    st.markdown("  ·  ".join(links))

    st.stop()

# ─────────────────────────────────────────────
# Search results
# ─────────────────────────────────────────────

if search_query:
    if results is None or results.empty:
        st.warning("No matches found. Try a different search term.")
    else:
        st.markdown(f"### {len(results)} result(s) for **{search_query}**")

        for _, row in results.iterrows():
            alts = row["_alt_list"]
            types = row["_type_list"]
            score_pct = int(row["score"] * 100)
            cert = str(row["coord_certainty"]).lower()
            uncertain = cert in ("approximate", "uncertain")

            col_name, col_meta, col_score, col_btn = st.columns([3, 4, 1, 1])

            with col_name:
                st.markdown(f"**{row['pref_label']}**")
                if pd.notna(row["parent_region_pref_label"]):
                    st.caption(str(row["parent_region_pref_label"]))

            with col_meta:
                parts = []
                if types:
                    parts.append(", ".join(types))
                if alts:
                    parts.append(f"also: {', '.join(alts[:3])}{'…' if len(alts) > 3 else ''}")
                st.caption("  ·  ".join(parts) if parts else "")
                if uncertain:
                    st.caption(f"⚠️ {cert} coordinates")

            with col_score:
                st.caption(f"{score_pct}%")

            with col_btn:
                if st.button("Details", key=f"detail_{row['glob_id']}"):
                    st.session_state.selected_glob_id = row["glob_id"]
                    st.rerun()

            st.divider()

else:
    # Default view — sample of data
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
