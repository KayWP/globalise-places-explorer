import streamlit as st
import pandas as pd
import pydeck as pdk
from utils import certainty_color, build_transcription_url


def render_detail_view(df, glob_id, back_label="← Back"):
    """Render the full detail panel for a single location.
    Returns True if the user clicked 'Back', False otherwise."""
    row = df[df["glob_id"] == glob_id].iloc[0]
    alts = row["_alt_list"]
    types = row["_type_list"]
    cert = str(row["coord_certainty"]).lower()
    all_terms = list({row["pref_label"]} | set(alts))

    if st.button(back_label):
        return True  # caller should clear selected_glob_id and rerun

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
                "latitude": lat,
                "longitude": lon,
                "pref_label": row["pref_label"],
                "coord_certainty": cert,
            }])
            single_row["color"] = single_row["coord_certainty"].apply(certainty_color)
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=single_row,
                get_position=["longitude", "latitude"],
                get_color="color",
                get_radius=30000,
                radius_min_pixels=6,
                radius_max_pixels=20,
            )
            view = pdk.ViewState(latitude=lat, longitude=lon, zoom=4)
            st.pydeck_chart(pdk.Deck(
                layers=[layer],
                initial_view_state=view,
                tooltip={"html": "<b>{pref_label}</b>", "style": {"color": "white"}},
            ))

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
        wikidata_url = (
            wikidata_val if wikidata_val.startswith("http")
            else f"https://www.wikidata.org/wiki/{wikidata_val}"
        )
        links.append(f"[🔷 Wikidata]({wikidata_url})")
    if pd.notna(row["tgn_id"]) and str(row["tgn_id"]).strip():
        tgn_val = str(row["tgn_id"]).strip()
        tgn_url = (
            tgn_val if tgn_val.startswith("http")
            else f"http://vocab.getty.edu/tgn/{tgn_val}"
        )
        links.append(f"[🏛️ Getty TGN]({tgn_url})")
    if pd.notna(row["external_id"]) and str(row["external_id"]).startswith("http"):
        links.append(f"[🔗 External]({row['external_id']})")
    st.markdown("  ·  ".join(links))

    return False
