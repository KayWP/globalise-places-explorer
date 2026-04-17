import pandas as pd
import pydeck as pdk
import streamlit as st
from difflib import SequenceMatcher


# ─────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────

def fuzzy_match_score(s1, s2):
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def parse_alt_labels(raw):
    if pd.isna(raw) or not str(raw).strip():
        return []
    return [lbl.strip() for lbl in str(raw).split("|") if lbl.strip()]


def parse_types(raw):
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


def build_transcription_url(terms):
    base = "https://transcriptions.globalise.huygens.knaw.nl/?query[fullText]="
    query = "%20OR%20".join([f'"{t}"' for t in terms])
    return (base + query).replace(" ", "%20")


def build_transcription_query(terms):
    """Returns a query string with all labels joined by AND."""
    return " AND ".join(f'"{t}"' for t in terms)


def load_and_normalize(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    df.rename(columns={"Latitude": "latitude", "Longitude": "longitude"}, inplace=True)

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

    df["_alt_list"] = df["alt_labels"].apply(parse_alt_labels)
    df["_type_list"] = df["types"].apply(parse_types)
    return df


@st.cache_data
def load_default():
    try:
        raw = pd.read_excel("locationdata.xlsx", sheet_name="Sheet2 Places – Overview")
        return load_and_normalize(raw)
    except FileNotFoundError:
        return None


def init_session_state():
    if "locations_df" not in st.session_state:
        default = load_default()
        st.session_state.locations_df = default
        st.session_state.uploaded_files_processed = set()
    if "selected_glob_id" not in st.session_state:
        st.session_state.selected_glob_id = None


# ─────────────────────────────────────────────
# URL / query-param helpers
# ─────────────────────────────────────────────

def sync_query_params():
    """Read ?glob_id=... from the URL into session state.
    Call once per page after init_session_state(), to support
    shareable URLs and consistent browser back-button behaviour."""
    url_id = st.query_params.get("glob_id", None)
    if url_id and url_id != st.session_state.selected_glob_id:
        st.session_state.selected_glob_id = url_id
    elif not url_id and st.session_state.selected_glob_id:
        # URL was cleared (e.g. browser back button) — honour it
        st.session_state.selected_glob_id = None


def set_selected(glob_id):
    """Select a location: write to session state and push ?glob_id= to the URL."""
    st.session_state.selected_glob_id = glob_id
    if glob_id is None:
        st.query_params.clear()
    else:
        st.query_params["glob_id"] = glob_id


# ─────────────────────────────────────────────
# Shared sidebar
# ─────────────────────────────────────────────

def render_sidebar(df):
    """Renders the standard informational sidebar. Pass the loaded dataframe (or None)."""
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
                'Pham, Thuy Dung; Nijman, Brecht; Land, Ruben; Bellarykar, Nikhil; Tabroni, Roni; '
                'Yeh, Chun-ting; Rabecca Mathai, Meenu; van Wissen, Leon; Houwer, Andy; Widmer, Marc; '
                'Kuruppath, Manjusha, 2026, "GLOBALISE - Places in the Dutch East India Company '
                'Archives (1602-1799)", https://doi.org/10.34894/UFFFNO, DataverseNL, V3'
            )

        st.markdown(
            "Be sure to cite permanent, F.A.I.R. data, not apps!"
            ""
            "App by [Kay Pepping](https://github.com/KayWP/). "
            "Bug reports welcome on Github. "
            "Explore more on [VOCData.nl](https://vocdata.nl/)"
        )


def apply_filters(df, selected_types, selected_ccodes, selected_cert):
    filtered = df.copy()
    if selected_types:
        filtered = filtered[filtered["_type_list"].apply(lambda lst: any(t in selected_types for t in lst))]
    if selected_ccodes:
        filtered = filtered[
            filtered["ccodes"].apply(
                lambda raw: any(c.strip() in selected_ccodes for c in str(raw).split("|"))
                if pd.notna(raw) else False
            )
        ]
    if selected_cert:
        filtered = filtered[filtered["coord_certainty"].isin(selected_cert)]
    return filtered


# ─────────────────────────────────────────────
# Detail view
# ─────────────────────────────────────────────

def render_detail_view(df, glob_id, back_label="← Back"):
    """Renders the full detail panel for a given glob_id."""
    row = df[df["glob_id"] == glob_id].iloc[0]
    alts = row["_alt_list"]
    types = row["_type_list"]
    cert = str(row["coord_certainty"]).lower()
    all_terms = list({row["pref_label"]} | set(alts))

    if st.button(back_label):
        set_selected(None)
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

            single_row = pd.DataFrame([{
                "latitude": lat, "longitude": lon,
                "pref_label": row["pref_label"],
                "coord_certainty": cert,
            }])
            single_row["color"] = single_row["coord_certainty"].apply(certainty_color)
            layer = pdk.Layer(
                "ScatterplotLayer", data=single_row,
                get_position=["longitude", "latitude"],
                get_color="color", get_radius=30000,
                radius_min_pixels=6, radius_max_pixels=20,
            )
            view = pdk.ViewState(latitude=lat, longitude=lon, zoom=4)
            st.pydeck_chart(pdk.Deck(
                layers=[layer], initial_view_state=view,
                tooltip={"html": "<b>{pref_label}</b>", "style": {"color": "white"}},
            ))

    if pd.notna(row["overall_remarks"]) and str(row["overall_remarks"]).strip():
        st.divider()
        st.markdown("**Remarks**")
        st.markdown(str(row["overall_remarks"]))

    st.divider()
    st.markdown("**GLOBALISE transcriptions query**")
    st.code(build_transcription_query(all_terms), language=None)

    st.markdown("**External links**")
    links = []
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
    if links:
        st.markdown("  ·  ".join(links))


def render_footer():
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
