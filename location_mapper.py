import streamlit as st
import pandas as pd
import pydeck as pdk

# Set page configuration
st.set_page_config(page_title="Location Data Mapper", layout="wide")

st.title("🗺️ Location Data Mapper")

# File uploader
uploaded_file = st.file_uploader("Upload your locationdata.csv file", type=['csv'])

if uploaded_file is not None:
    # Read the CSV file
    df = pd.read_csv(uploaded_file)
    
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
    
    st.write(f"### Showing {len(df)} valid locations on the map")
    
    # Sidebar filters
    st.sidebar.header("Filters")
    
    # Filter by label_type
    label_types = df['label_type'].unique().tolist()
    selected_types = st.sidebar.multiselect(
        "Filter by Label Type",
        options=label_types,
        default=label_types
    )
    
    # Filter by glob_id (show only unique IDs)
    unique_ids = sorted(df['glob_id'].unique().tolist())
    selected_ids = st.sidebar.multiselect(
        "Filter by Location ID",
        options=unique_ids,
        default=[]
    )
    
    # Apply filters
    filtered_df = df[df['label_type'].isin(selected_types)]
    if selected_ids:
        filtered_df = filtered_df[filtered_df['glob_id'].isin(selected_ids)]
    
    # Color mapping for label types
    color_map = {
        'PREF': [255, 0, 0, 160],  # Red
        'ALT': [0, 0, 255, 160]     # Blue
    }
    
    filtered_df['color'] = filtered_df['label_type'].map(color_map)
    
    # Display statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Locations", len(filtered_df))
    with col2:
        st.metric("Unique IDs", filtered_df['glob_id'].nunique())
    with col3:
        st.metric("Preferred Labels", len(filtered_df[filtered_df['label_type'] == 'PREF']))
    
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
            get_color='color',
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
        
        st.pydeck_chart(deck)
        
        # Display the data table
        st.write("### Location Data")
        st.dataframe(
            filtered_df[['glob_id', 'label', 'pref_label', 'label_type', 'Latitude', 'Longitude']],
            use_container_width=True
        )
        
        # Legend
        st.write("### Legend")
        st.markdown("🔴 **PREF** - Preferred label")
        st.markdown("🔵 **ALT** - Alternative label")
        
    else:
        st.warning("No locations match the selected filters.")
        
else:
    st.info("👆 Please upload your locationdata.csv file to get started")
    
    st.write("### Expected CSV Format")
    st.code("""glob_id,label,pref_label,label_type,Latitude,Longitude
GLOB_844,Abarkūh,Abarkūh,PREF,31.1289,53.2824
GLOB_844,Abercouh,Abarkūh,ALT,31.1289,53.2824""")
