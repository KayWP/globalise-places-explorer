A Streamlit application for searching and exploring places from the Dutch East India Company Archives (1602-1799). This tool provides fuzzy search capabilities and interactive map visualization for the [GLOBALISE places dataset](https://hdl.handle.net/10622/WYVERW).

It is currently live [here](vocdata.nl/place-search/).

## Installation

### Prerequisites

- Python 3.7+
- Pandas
- Streamlit
- PyDeck

### Setup

1. Clone this repository:

```bash
git clone https://github.com/KayWP/globalise-places-search.git
cd globalise-places-search
```

2. Install required packages:

```bash
pip install streamlit pandas pydeck
```

3. Ensure you have the `locationdata.csv` file in the same directory as the script.

## Usage

Run the application with:

```bash
streamlit run location_search.py
```

The app will open in your default web browser at `http://localhost:8501`.

### Uploading Additional Data

1. Expand the "Upload additional data" section
2. Upload a CSV file with the following format:

```csv
glob_id,label,pref_label,label_type,Latitude,Longitude
GLOB_844,Abarkūh,Abarkūh,PREF,31.1289,53.2824
GLOB_844,Abercouh,Abarkūh,ALT,31.1289,53.2824
```

## Data Source

This application uses data created by **Dung Thuy Pham, Brecht Nijman, Ruben Land, Andy Houwer, Marc Widmer & Manjusha Kurrupath** for the GLOBALISE project.

**Full Citation:**

```
Pham, Thuy Dung; Nijman, Brecht; Land, Ruben; Houwer, Andy; Widmer, Marc; 
Kuruppath, Manjusha, 2025, "GLOBALISE - Places in the Dutch East India Company 
Archives (1602-1799)", https://hdl.handle.net/10622/WYVERW, IISH Data Collection, 
V1, UNF:6:ReciyJlxCaRV5CSVvIzP8g== [fileUNF]
```

**Download Dataset:** [IISH Data Collection](https://datasets.iisg.amsterdam/dataset.xhtml?persistentId=hdl:10622/WYVERW)

## How It Works

The application uses:

- **SequenceMatcher** from Python's difflib for fuzzy string matching
- **Streamlit** for the web interface
- **PyDeck** for interactive map visualization
- **Pandas** for data manipulation
