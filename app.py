from __future__ import annotations

import os
from pathlib import Path

import exifread
import pandas as pd
import plotly.express as px
import streamlit as st

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tiff", ".tif", ".nef", ".cr2", ".arw", ".dng", ".raf", ".orf"}


def _parse_tags(tags, filename: str) -> dict | None:
    """Build a record dict from exifread tags."""
    if not tags:
        return None

    def get(key):
        val = tags.get(key)
        return str(val) if val else None

    date_str = get("EXIF DateTimeOriginal")
    hour = None
    if date_str:
        try:
            hour = int(date_str.split(" ")[1].split(":")[0])
        except (IndexError, ValueError):
            pass

    wb_raw = get("EXIF WhiteBalance")
    wb_map = {"0": "Auto", "1": "Manual"}
    white_balance = wb_map.get(wb_raw, wb_raw) if wb_raw else None

    # Try to find shutter count from various maker note tags
    shutter_count = None
    for key in ("MakerNote TotalShutterReleases", "MakerNote ShutterCount",
                "MakerNote ImageCount", "Image ImageNumber"):
        val = get(key)
        if val:
            try:
                shutter_count = int(val)
                break
            except ValueError:
                pass

    return {
        "file": filename,
        "camera": get("Image Model"),
        "lens": get("EXIF LensModel"),
        "focal_length": get("EXIF FocalLength"),
        "aperture": get("EXIF FNumber"),
        "shutter_speed": get("EXIF ExposureTime"),
        "iso": get("EXIF ISOSpeedRatings"),
        "date": date_str,
        "hour": hour,
        "white_balance": white_balance,
        "metering_mode": get("EXIF MeteringMode"),
        "exposure_mode": get("EXIF ExposureMode"),
        "flash": get("EXIF Flash"),
        "shutter_count": shutter_count,
    }


def extract_exif(file_path: Path) -> dict | None:
    """Extract relevant EXIF fields from an image file on disk."""
    try:
        with open(file_path, "rb") as f:
            tags = exifread.process_file(f, details=True)
    except Exception:
        return None
    return _parse_tags(tags, file_path.name)


def extract_exif_from_upload(uploaded_file) -> dict | None:
    """Extract relevant EXIF fields from a Streamlit UploadedFile."""
    try:
        tags = exifread.process_file(uploaded_file, details=False)
    except Exception:
        return None
    return _parse_tags(tags, uploaded_file.name)


def load_folder(folder: str) -> pd.DataFrame:
    """Scan a folder for images and return a DataFrame of EXIF data."""
    records = []
    folder_path = Path(folder)
    for f in sorted(folder_path.rglob("*")):
        if f.suffix.lower() in IMAGE_EXTENSIONS:
            data = extract_exif(f)
            if data:
                records.append(data)
    return pd.DataFrame(records)


def make_bar_chart(df: pd.DataFrame, column: str, title: str):
    """Create a horizontal bar chart of value percentages."""
    counts = df[column].dropna().value_counts().reset_index()
    counts.columns = [column, "count"]
    total = counts["count"].sum()
    counts["pct"] = (counts["count"] / total * 100).round(1)
    counts = counts.sort_values("pct", ascending=True)
    fig = px.bar(counts, x="pct", y=column, orientation="h", title=title,
                 text=counts["pct"].apply(lambda v: f"{v}%"),
                 color_discrete_sequence=["#333333"])
    fig.update_layout(yaxis_title="", xaxis_title="%", height=max(300, len(counts) * 28 + 100))
    fig.update_traces(textposition="outside")
    return fig


import platform
import shutil

IS_LOCAL = platform.system() == "Darwin" and shutil.which("osascript") is not None


def pick_folder() -> str | None:
    """Open a native macOS folder picker via AppleScript."""
    import subprocess

    result = subprocess.run(
        ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select photos folder")'],
        capture_output=True, text=True, timeout=120,
    )
    folder = result.stdout.strip()
    return folder if folder else None


def load_uploads(uploaded_files) -> pd.DataFrame:
    """Build a DataFrame from a list of Streamlit UploadedFiles."""
    records = []
    for uf in uploaded_files:
        data = extract_exif_from_upload(uf)
        if data:
            records.append(data)
    return pd.DataFrame(records)


def load_zip(uploaded_zip) -> pd.DataFrame:
    """Extract images from a ZIP and read their EXIF data."""
    import io
    import zipfile

    records = []
    with zipfile.ZipFile(io.BytesIO(uploaded_zip.read())) as zf:
        for name in sorted(zf.namelist()):
            ext = Path(name).suffix.lower()
            if ext in IMAGE_EXTENSIONS:
                with zf.open(name) as img_file:
                    try:
                        tags = exifread.process_file(io.BytesIO(img_file.read()), details=False)
                        data = _parse_tags(tags, Path(name).name)
                        if data:
                            records.append(data)
                    except Exception:
                        pass
    return pd.DataFrame(records)


def top(df, col):
    """Return the most common value in a column."""
    s = df[col].dropna()
    return s.value_counts().index[0] if not s.empty else "—"


def to_mm(val):
    """Parse focal length to numeric mm value."""
    try:
        if "/" in str(val):
            num, den = str(val).split("/")
            return round(float(num) / float(den))
        return round(float(val))
    except (ValueError, ZeroDivisionError):
        return None


# ── App config ───────────────────────────────────────────────

st.set_page_config(page_title="Photo Analyzer", layout="wide")

if "df" not in st.session_state:
    st.session_state.df = None
if "folder" not in st.session_state:
    st.session_state.folder = None
if "page" not in st.session_state:
    st.session_state.page = "Home"


# ── Sidebar navigation ──────────────────────────────────────

has_data = st.session_state.df is not None

with st.sidebar:
    st.title("📷 EXIF Photo Analyzer")
    st.divider()

    pages = ["Home", "Summary", "Charts", "Raw Data"]

    def on_nav_change():
        st.session_state.page = st.session_state.nav_radio

    page = st.radio(
        "Navigation",
        pages,
        index=pages.index(st.session_state.page),
        key="nav_radio",
        on_change=on_nav_change,
        label_visibility="collapsed",
    )
    page = st.session_state.page

    if has_data:
        st.divider()
        st.caption(f"**{len(st.session_state.df)}** photos loaded")
        if st.session_state.folder != "uploaded files":
            st.caption(f"`{st.session_state.folder}`")
        else:
            st.caption("From uploaded files")


# ── Page: Home ───────────────────────────────────────────────

if page == "Home":
    st.markdown(
        """
        <style>
        .block-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 80vh;
        }
        .block-container > div { width: auto; }
        .stButton > button { margin: 0 auto; display: block; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<h1 style='text-align:center;'>Welcome to EXIF Photo Analyzer</h1>", unsafe_allow_html=True)
    st.write("")
    st.markdown(
        """
        <div style="text-align:center; max-width:600px; margin:0 auto; line-height:1.8;">
        Analyze the EXIF data from your photos and discover your shooting habits.<br><br>
        <strong>Summary</strong> — Your favorite camera, lens, aperture, ISO and more<br>
        <strong>Charts</strong> — Visual breakdowns of all your settings<br>
        <strong>Lenses</strong> — Focal length distribution per lens<br>
        <strong>Timeline</strong> — When you shoot the most<br>
        <strong>Raw Data</strong> — Browse every detail per photo<br><br>
        Supports JPG, TIFF, NEF, CR2, ARW, DNG, RAF and ORF files.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    if IS_LOCAL:
        tab_folder, tab_upload = st.tabs(["Select Folder", "Upload Files"])
    else:
        tab_upload = st.container()
        tab_folder = None

    # ── Folder picker (local only) ──
    if tab_folder is not None:
        with tab_folder:
            if st.button("📁 Browse Folder", type="primary"):
                chosen = pick_folder()
                if chosen and os.path.isdir(chosen):
                    with st.spinner("Scanning images and reading EXIF data..."):
                        df = load_folder(chosen)
                    if df.empty:
                        st.warning("No images with EXIF data found in that folder.")
                    else:
                        st.session_state.df = df
                        st.session_state.folder = chosen
                        st.session_state.page = "Summary"
                        st.rerun()
                elif chosen:
                    st.error("That folder does not exist.")

    # ── File uploader (works everywhere) ──
    with tab_upload:
        uploaded = st.file_uploader(
            "Drop your photos here",
            type=["jpg", "jpeg", "tiff", "tif", "nef", "cr2", "arw", "dng", "raf", "orf"],
            accept_multiple_files=True,
        )
        if uploaded:
            if st.button("Analyze uploads", type="primary"):
                with st.spinner("Reading EXIF data..."):
                    df = load_uploads(uploaded)
                if df.empty:
                    st.warning("No EXIF data found in the uploaded files.")
                else:
                    st.session_state.df = df
                    st.session_state.folder = "uploaded files"
                    st.session_state.page = "Summary"
                    st.rerun()

    if has_data:
        st.success("Data loaded — use the sidebar to navigate.")


# ── Guard: require data for other pages ──────────────────────

elif not has_data:
    st.warning("No data loaded yet. Go to **Home** and select a folder first.")


# ── Page: Summary ────────────────────────────────────────────

elif page == "Summary":
    df = st.session_state.df
    st.title("Summary")
    st.markdown(f"<p style='font-size:1.3rem;'>Top settings across <strong>{len(df)}</strong> photos</p>", unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Camera", top(df, "camera"))
    m2.metric("Lens", top(df, "lens"))
    m3.metric("Aperture", f"f/{top(df, 'aperture')}")
    m4.metric("ISO", top(df, "iso"))

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Shutter Speed", top(df, "shutter_speed"))
    m6.metric("Focal Length", top(df, "focal_length"))
    m7.metric("White Balance", top(df, "white_balance"))
    hour_series = df["hour"].dropna()
    if not hour_series.empty:
        fav_hour = int(hour_series.value_counts().index[0])
        m8.metric("Peak Hour", f"{fav_hour:02d}:00")
    else:
        m8.metric("Peak Hour", "—")

    # Shutter count row
    shutter_counts = df["shutter_count"].dropna()
    if not shutter_counts.empty:
        max_count = int(shutter_counts.max())
        st.metric("Estimated Shutter Count", f"{max_count:,}")

    st.divider()

    # Top-3 mini tables
    col_a, col_b, col_c = st.columns(3)

    def top_n(col, n=5):
        counts = df[col].dropna().value_counts().head(n).reset_index()
        counts.columns = [col, "photos"]
        total = df[col].dropna().shape[0]
        counts["%"] = (counts["photos"] / total * 100).round(1)
        return counts

    with col_a:
        st.subheader("Top Lenses")
        st.dataframe(top_n("lens"), use_container_width=True, hide_index=True)

    with col_b:
        st.subheader("Top Apertures")
        st.dataframe(top_n("aperture"), use_container_width=True, hide_index=True)

    with col_c:
        st.subheader("Top ISOs")
        st.dataframe(top_n("iso"), use_container_width=True, hide_index=True)

    col_d, col_e, col_f = st.columns(3)

    with col_d:
        st.subheader("Top Shutter Speeds")
        st.dataframe(top_n("shutter_speed"), use_container_width=True, hide_index=True)

    with col_e:
        st.subheader("Top Focal Lengths")
        st.dataframe(top_n("focal_length"), use_container_width=True, hide_index=True)

    with col_f:
        st.subheader("Top Cameras")
        st.dataframe(top_n("camera"), use_container_width=True, hide_index=True)


# ── Page: Charts ─────────────────────────────────────────────

elif page == "Charts":
    df = st.session_state.df
    st.title("Charts")

    col1, col2 = st.columns(2)

    with col1:
        if df["lens"].notna().any():
            st.plotly_chart(make_bar_chart(df, "lens", "Most Used Lenses"), use_container_width=True)

        if df["focal_length"].notna().any():
            st.plotly_chart(make_bar_chart(df, "focal_length", "Focal Length"), use_container_width=True)

        if df["camera"].notna().any():
            st.plotly_chart(make_bar_chart(df, "camera", "Camera Bodies"), use_container_width=True)

        if df["white_balance"].notna().any():
            st.plotly_chart(make_bar_chart(df, "white_balance", "White Balance"), use_container_width=True)

        if df["flash"].notna().any():
            st.plotly_chart(make_bar_chart(df, "flash", "Flash"), use_container_width=True)

    with col2:
        if df["aperture"].notna().any():
            st.plotly_chart(make_bar_chart(df, "aperture", "Aperture (f-number)"), use_container_width=True)

        if df["shutter_speed"].notna().any():
            st.plotly_chart(make_bar_chart(df, "shutter_speed", "Shutter Speed"), use_container_width=True)

        if df["iso"].notna().any():
            st.plotly_chart(make_bar_chart(df, "iso", "ISO"), use_container_width=True)

        if df["metering_mode"].notna().any():
            st.plotly_chart(make_bar_chart(df, "metering_mode", "Metering Mode"), use_container_width=True)

        if df["exposure_mode"].notna().any():
            st.plotly_chart(make_bar_chart(df, "exposure_mode", "Exposure Mode"), use_container_width=True)

    # ── Focal length per lens ────────────────────────────────────
    st.divider()
    st.subheader("Focal Length Distribution per Lens")

    lens_fl = df[["lens", "focal_length"]].dropna()
    if lens_fl.empty:
        st.info("No lens + focal length data available.")
    else:
        lens_fl = lens_fl.copy()
        lens_fl["focal_mm"] = lens_fl["focal_length"].apply(to_mm)
        lens_fl = lens_fl.dropna(subset=["focal_mm"])

        if lens_fl.empty:
            st.info("Could not parse focal lengths.")
        else:
            lenses = lens_fl["lens"].value_counts().index.tolist()
            for lens_name in lenses:
                subset = lens_fl[lens_fl["lens"] == lens_name]
                counts = subset["focal_mm"].value_counts().sort_index().reset_index()
                counts.columns = ["focal_mm", "count"]
                total = counts["count"].sum()
                counts["pct"] = (counts["count"] / total * 100).round(1)
                counts["focal_mm"] = counts["focal_mm"].astype(int).astype(str) + "mm"
                fig = px.bar(counts, x="focal_mm", y="pct", title=f"{lens_name}  ({total} photos)",
                             text=counts["pct"].apply(lambda v: f"{v}%"),
                             color_discrete_sequence=["#333333"])
                fig.update_layout(xaxis_title="Focal Length", yaxis_title="%", height=300)
                fig.update_traces(textposition="outside")
                st.plotly_chart(fig, use_container_width=True)

    # ── Shooting timeline ────────────────────────────────────────
    st.divider()
    st.subheader("Shooting Timeline")

    if df["hour"].notna().any():
        hour_counts = df["hour"].dropna().value_counts().reindex(range(24), fill_value=0).reset_index()
        hour_counts.columns = ["hour", "count"]
        total = hour_counts["count"].sum()
        hour_counts["pct"] = (hour_counts["count"] / total * 100).round(1)
        hour_counts["label"] = hour_counts["hour"].apply(lambda h: f"{h:02d}:00")
        fig = px.bar(hour_counts, x="label", y="pct", title="Photos by Hour of Day",
                     text=hour_counts["pct"].apply(lambda v: f"{v}%"),
                     color_discrete_sequence=["#333333"])
        fig.update_layout(xaxis_title="Hour", yaxis_title="%", height=350)
        fig.update_traces(textposition="outside")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No time-of-day data available.")


# ── Page: Raw Data ───────────────────────────────────────────

elif page == "Raw Data":
    df = st.session_state.df
    st.title("Raw EXIF Data")
    st.dataframe(df, use_container_width=True, height=600)
