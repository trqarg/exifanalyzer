# EXIF Photo Analyzer

A Streamlit web app that analyzes EXIF metadata from your photos and visualizes your shooting habits.

## Features

- **Summary** — Top camera, lens, aperture, ISO, shutter speed, focal length, white balance, peak shooting hour, and estimated shutter count
- **Charts** — Percentage-based bar charts for all settings, focal length distribution per lens, and shooting time of day
- **Raw Data** — Browsable table with every EXIF field per photo
- **Folder picker** — Native macOS folder dialog (local) or file/ZIP upload (cloud)

## Supported formats

JPG, TIFF, NEF, CR2, ARW, DNG, RAF, ORF

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py --theme.base light
```

Open http://localhost:8501 in your browser.

## Tech stack

- [Streamlit](https://streamlit.io/) — UI
- [exifread](https://pypi.org/project/ExifRead/) — EXIF parsing
- [Plotly](https://plotly.com/python/) — Charts
- [Pandas](https://pandas.pydata.org/) — Data processing
