import streamlit as st
import pandas as pd
from difflib import SequenceMatcher
import pydeck as pdk

#helper functions
def fuzzy_match_score(s1, s2):
    #returns similarity score between two strings
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

def create_map(df):
    # Clean and prepare the data
    # Remove rows where Latitude is "Not available" or invalid
    df = df[df['Latitude'] != 'Not available']
    
    # Convert Latitude and Longitude to numeric, removing any invalid entries
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    
    # Remove rows with NaN coordinates
    df = df.dropna(subset=['Latitude', 'Longitude'])
    
    # Remove rows with 0,0 coordinates (likely invalid)
    df = df[~((df['Latitude'] == 0) & (df['Longitude'] == 0))]

    # Color mapping for label types
    color_map = {
        'PREF': [255, 0, 0, 160],  # Red
    }

    filtered_df = df[df['label_type']=='PREF']

    # Create the map
    if len(filtered_df) > 0:
        # Calculate the center of the map
        center_lat = filtered_df['Latitude'].mean()
        center_lon = filtered_df['Longitude'].mean()
        
        # Create the pydeck layer
        layer = pdk.Layer(
            'ScatterplotLayer',
            data=filtered_df,
            get_position=['Longitude', 'Latitude'],
            get_color=[255, 0, 0, 160],
            get_radius=50000,
            pickable=True,
            auto_highlight=True
        )
        
        # Set the view state
        view_state = pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=2,
            pitch=0
        )
        
        # Create the deck
        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={
                'html': '<b>ID:</b> {glob_id}<br/>'
                        '<b>Label:</b> {label}<br/>'
                        '<b>Preferred:</b> {pref_label}<br/>'
                        '<b>Type:</b> {label_type}<br/>'
                        '<b>Coordinates:</b> {Latitude}, {Longitude}',
                'style': {'color': 'white'}
            }
        )
        
    return st.pydeck_chart(deck)

def search_locations(df, query, top_n=10):
    #search through locations based on the query
    if not query:
        return pd.DataFrame()
    
    # Calculate scores for all labels
    scores = []
    for idx, row in df.iterrows():
        label = str(row['label'])
        pref_label = str(row['pref_label'])
        
        # Calculate score based on label match
        score = fuzzy_match_score(query, label)
        
        # Bonus if it matches the preferred label
        if label == pref_label:
            score += 0.1
        
        scores.append({
            'glob_id': row['glob_id'],
            'label': label,
            'pref_label': pref_label,
            'label_type': row['label_type'],
            'Latitude': row['Latitude'],
            'Longitude': row['Longitude'],
            'score': score
        })
    
    # Convert to dataframe and sort by score
    results_df = pd.DataFrame(scores)
    results_df = results_df.sort_values('score', ascending=False).head(top_n)
    
    # Group by glob_id to show all variants
    results_df = results_df[results_df['score'] > 0.3]  # Filter low matches
    
    return results_df

st.set_page_config(page_title="Location ID Search", layout="wide")

st.title("🗺️ GLOBALISE places dataset search")
st.markdown("Search through the GLOBALISE places data using fuzzy search.")

if "locations_df" not in st.session_state:
    st.session_state.locations_df = pd.read_csv('locationdata.csv')

# Load the CSV file
try:
    df = st.session_state.locations_df
    # Clean up column names (remove extra spaces)
    df.columns = df.columns.str.strip()
    
    # Remove empty columns
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    
    st.success(f"✅ Loaded {len(df)} location records with {df['glob_id'].nunique()} unique IDs")
    
    # Search interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input("🔍 Enter place name:", placeholder="e.g., Aburkeh, Fujiyama")
    
    with col2:
        top_n = st.number_input("Max results:", min_value=5, max_value=50, value=10)
    
    with st.expander("🗺️ View the locations on the map"):
        create_map(df)

    if search_query:
        results = search_locations(df, search_query, top_n)
        
        if not results.empty:
            st.markdown(f"### Found {len(results)} matches for '{search_query}'")
            
            # Group results by glob_id for better display
            unique_ids = results['glob_id'].unique()
            
            for glob_id in unique_ids:
                id_results = results[results['glob_id'] == glob_id]
                best_match = id_results.iloc[0]
                
                with st.container():
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        st.markdown(f"**ID:** `{glob_id}`")
                        st.markdown(f"**Preferred Name:** {best_match['pref_label']}")
                    
                    with col2:
                        # Show all variants for this ID
                        variants = id_results['label'].tolist()
                        st.markdown(f"**Variants:** {', '.join(variants)}")
                    
                    with col3:
                        score_pct = int(best_match['score'] * 100)
                        st.metric("Match", f"{score_pct}%")
                    
                    # Show coordinates
                    st.caption(f"📍 Coordinates: {best_match['Latitude']}, {best_match['Longitude']}")
                    
                    st.divider()
        else:
            st.warning("No matches found. Try a different search term.")
    
    # Give info about the data
    with st.expander("👥 Who created this data?"):
        st.markdown("This application uses the data created by Dung Thuy Pham, Brecht Nijman, Ruben Land, Andy Houwer, Marc Widmer & Manjusha Kurrupath for the GLOBALISE project. It is available for download [here](https://datasets.iisg.amsterdam/dataset.xhtml?persistentId=hdl:10622/WYVERW). The full citation is:")
        st.code("""Pham, Thuy Dung; Nijman, Brecht; Land, Ruben; Houwer, Andy; Widmer, Marc; Kuruppath, Manjusha, 2025, "GLOBALISE - Places in the Dutch East India Company Archives (1602-1799)", https://hdl.handle.net/10622/WYVERW, IISH Data Collection, V1, UNF:6:ReciyJlxCaRV5CSVvIzP8g== [fileUNF]""")
        st.markdown("The app itself was coded by [Kay Pepping](https://github.com/KayWP/). Improvements and bug report can be suggested on Github.")
    
    # Show sample data
    with st.expander("📊 View Sample Data"):
        st.dataframe(df.head(20), use_container_width=True)
    
    # Stats
    with st.expander("📈 Dataset Statistics"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Records", len(df))
        with col2:
            st.metric("Unique IDs", df['glob_id'].nunique())
        with col3:
            st.metric("Unique Locations", df['pref_label'].nunique())
            
except FileNotFoundError:
    st.error("❌ Could not find 'locationdata.csv'. Please make sure the file is in the same directory as this script.")
except Exception as e:
    st.error(f"❌ Error loading data: {str(e)}")

with st.expander("Upload additional data"):    
    uploaded_file = st.file_uploader("Upload your locationdata.csv file", type=['csv'])
    if uploaded_file is not None:
        try:
            extra_df = pd.read_csv(uploaded_file)
            # Optional: clean up column names like before
            extra_df.columns = extra_df.columns.str.strip()
            extra_df = extra_df.loc[:, ~extra_df.columns.str.contains('^Unnamed')]
            
            # Combine with existing data and reset index
            st.session_state.locations_df = pd.concat(
                [st.session_state.locations_df, extra_df],
                ignore_index=True
            )
            
            st.success(f"✅ Uploaded {len(extra_df)} new records. Total: {len(st.session_state.locations_df)}")
            
        except Exception as e:
            st.error(f"❌ Error loading data: {str(e)}")

      
    # Show example
    st.markdown("### Example Data Format")
    st.code("""glob_id,label,pref_label,label_type,Latitude,Longitude
    GLOB_844,Abarkūh,Abarkūh,PREF,31.1289,53.2824
    GLOB_844,Abercouh,Abarkūh,ALT,31.1289,53.2824
    GLOB_1,Abubu,Abubu,PREF,-3.692153,128.789113""")