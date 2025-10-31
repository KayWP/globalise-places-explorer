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
        
    return st.pydeck_chart(deck)