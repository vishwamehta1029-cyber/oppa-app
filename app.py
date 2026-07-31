"""
Internal OPPA - Operational Pain Point Assessment
====================================================
A Streamlit app for comparing Client Self-Assessment (Perception) against
Auditor Floor Reality across 12 operational categories.

--------------------------------------------------------------------------
HOW TO RUN THIS APP (it is NOT run by double-clicking or "Run" in an IDE)
--------------------------------------------------------------------------
1. cd into the folder containing this file
2. pip3 install -r requirements.txt
3. streamlit run app.py
4. It will open automatically in your browser at http://localhost:8501

IMPORTANT: this app also ships a .streamlit/config.toml file that locks
the app into light theme. This file MUST sit in a folder literally named
".streamlit" right next to app.py (same folder as secrets.toml). Without
it, viewers whose phone or browser is set to dark mode will see broken,
low-contrast text, because Streamlit otherwise follows each viewer's own
system dark/light preference.

--------------------------------------------------------------------------
SUPABASE CONFIGURATION
--------------------------------------------------------------------------
This app works with ZERO Supabase configuration ("Demo Mode") -- it will
never crash if keys are missing, it just disables sign-in/persistence so
you can explore the full workflow locally.

To enable real login + save/export to Supabase, create a file at:
    .streamlit/secrets.toml
with the following keys (see secrets.toml.example in this repo):

    SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
    SUPABASE_KEY = "YOUR-SUPABASE-ANON-OR-SERVICE-KEY"

Alternatively, you can set these as environment variables (a .env file
loaded via python-dotenv also works):
    SUPABASE_URL=https://YOUR-PROJECT.supabase.co
    SUPABASE_KEY=YOUR-SUPABASE-ANON-OR-SERVICE-KEY

--------------------------------------------------------------------------
EXPECTED SUPABASE SQL SCHEMA
--------------------------------------------------------------------------
-- audits table
create table audits (
    id uuid primary key default gen_random_uuid(),
    audit_title text not null,
    client_name text,
    auditor_name text,
    audit_date date,
    audit_phase text,
    total_client_score integer,
    total_auditor_score integer,
    overall_gap integer,
    risk_level text,
    created_by text,
    created_at timestamptz default now()
);

-- audit_categories table
-- NOTE: a category can now hold MULTIPLE photos. photo_url and
-- photo_captured_at store one value per photo, joined together with the
-- pipe character "|" in the same order (photo 1's url lines up with photo
-- 1's timestamp, and so on). Voice notes remain single, one per category.
create table audit_categories (
    id uuid primary key default gen_random_uuid(),
    audit_id uuid references audits(id) on delete cascade,
    category text not null,
    client_score integer,
    auditor_score integer,
    gap integer,
    severity_flag text,
    notes text,
    photo_url text,
    audio_url text,
    photo_captured_at text,
    audio_captured_at timestamptz
);

-- Storage buckets (create via Supabase dashboard or storage API):
--   oppa-photos
--   oppa-audio
--------------------------------------------------------------------------
"""

import hashlib
import io
from datetime import datetime, date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# supabase-py is optional -- app must run in Demo Mode without it installed
try:
    from supabase import create_client, Client  # noqa: F401
    SUPABASE_SDK_AVAILABLE = True
except ImportError:
    SUPABASE_SDK_AVAILABLE = False

# python-dotenv is optional, used only to load a local .env file if present
try:
    from dotenv import load_dotenv
    import os
    load_dotenv()
except ImportError:
    import os


# ==========================================================================
# CONSTANTS
# ==========================================================================

APP_TITLE = "Internal OPPA - Operational Pain Point Assessment"

CATEGORIES = [
    "Labor Productivity",
    "Process Flow",
    "Dock Operations",
    "Quality",
    "Inventory Access",
    "Safety",
    "Equipment Utilization",
    "Warehouse Layout and Space",
    "Standard Operating Procedures and Training",
    "Performance Management",
    "Continuous Improvement",
    "General Operations",
]

SEVERITY_OPTIONS = [
    "Normal",
    "Minor Issue",
    "Major Friction",
    "Critical Safety / Cost Risk",
]

AUDIT_PHASES = ["Baseline", "30-Day Check-in", "Final Review"]

CRITICAL_GAP_THRESHOLD = 2


# ==========================================================================
# STYLING (fonts, white background, black square tabs and buttons)
# ==========================================================================

def inject_custom_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=Almarai:wght@300;400;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Almarai', sans-serif;
        }

        /* Force readable colors everywhere, regardless of the viewer's
           own system dark/light mode preference. The .streamlit/config.toml
           file locks the underlying theme, this is the CSS-level backup. */
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
            background-color: #ffffff !important;
        }

        h1, h2, h3, h4, h5, h6,
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
        .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
            font-family: 'Libre Baskerville', serif !important;
            letter-spacing: 0.2px;
            color: #1a1a1a !important;
        }

        .stMarkdown p, .stMarkdown li,
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] label,
        [data-testid="stMarkdownContainer"] p {
            color: #1a1a1a !important;
        }

        [data-testid="stCaptionContainer"], .stCaption {
            color: #666666 !important;
        }

        :root {
            --oppa-red: #A10D29;
            --oppa-grey: #888888;
            --oppa-border: #e0e0e0;
        }

        [data-testid="stHeader"] {
            background-color: #ffffff !important;
        }

        .stMarkdown h1 {
            font-size: 3rem !important;
            line-height: 1.15 !important;
        }

        [data-testid="stExpander"],
        [data-testid="stVerticalBlockBorderWrapper"],
        [data-testid="stMetric"] {
            background-color: #ffffff !important;
            border: 1px solid var(--oppa-border);
            border-radius: 0 !important;
        }

        [data-testid="stMetricValue"] {
            color: var(--oppa-red) !important;
            font-family: 'Libre Baskerville', serif;
        }

        [data-testid="stMetricLabel"] {
            color: #666666 !important;
        }

        hr, [data-testid="stDivider"] {
            border-color: var(--oppa-border) !important;
        }

        /* Text inputs, number inputs, selects, date pickers, text areas:
           force a white field with black text, so they never render as a
           dark box with invisible labels under a viewer's dark mode. */
        .stTextInput input, .stTextArea textarea, .stDateInput input,
        .stNumberInput input,
        [data-baseweb="select"] > div,
        [data-baseweb="input"] {
            background-color: #ffffff !important;
            color: #1a1a1a !important;
            border-radius: 0 !important;
            border: 1px solid #000000 !important;
        }

        [data-baseweb="select"] span {
            color: #1a1a1a !important;
        }

        /* Tabs: sleek squares, no rounded corners, centered labels */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0;
            background-color: transparent;
            border-radius: 0 !important;
        }

        .stTabs [data-baseweb="tab"] {
            background-color: #ffffff !important;
            border-radius: 0 !important;
            border: 1px solid #000000;
            font-family: 'Almarai', sans-serif;
            font-weight: 700;
            color: #000000 !important;
            padding: 12px 32px;
            justify-content: center;
        }

        .stTabs [data-baseweb="tab"] p {
            width: 100%;
            text-align: center;
            color: inherit !important;
        }

        .stTabs [aria-selected="true"] {
            background-color: #000000 !important;
            border: 1px solid #000000 !important;
            color: #ffffff !important;
        }

        .stTabs [aria-selected="true"] p {
            color: #ffffff !important;
        }

        .stTabs [data-baseweb="tab-highlight"] {
            background-color: transparent;
        }

        .stTabs [data-baseweb="tab-border"] {
            display: none;
        }

        /* Buttons: square, black and white by default */
        .stButton > button, .stDownloadButton > button {
            border-radius: 0 !important;
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #000000 !important;
            font-family: 'Almarai', sans-serif;
            font-weight: 700;
        }

        .stButton > button:hover, .stDownloadButton > button:hover {
            background-color: #000000 !important;
            border: 1px solid #000000 !important;
            color: #ffffff !important;
        }

        /* Primary buttons: solid black */
        button[kind="primary"], button[kind="primaryFormSubmit"],
        [data-testid="stBaseButton-primary"] {
            border-radius: 0 !important;
            background-color: #000000 !important;
            color: #ffffff !important;
            border: 1px solid #000000 !important;
            font-family: 'Almarai', sans-serif;
            font-weight: 700;
        }

        button[kind="primary"]:hover,
        [data-testid="stBaseButton-primary"]:hover {
            background-color: var(--oppa-red) !important;
            border: 1px solid var(--oppa-red) !important;
        }

        /* Inputs: square corners */
        input, textarea, select {
            border-radius: 0 !important;
        }

        [data-testid="stFileUploaderDropzone"] {
            border-radius: 0 !important;
            background-color: #ffffff !important;
        }

        a, a:visited {
            color: var(--oppa-red) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ==========================================================================
# SUPABASE CLIENT SETUP
# ==========================================================================

def get_supabase_credentials():
    """Pull Supabase creds from st.secrets first, then env vars. Never raises."""
    url, key = None, None
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except Exception:
        pass
    if not url:
        url = os.environ.get("SUPABASE_URL")
    if not key:
        key = os.environ.get("SUPABASE_KEY")
    return url, key


@st.cache_resource(show_spinner=False)
def get_supabase_client(url, key):
    """Returns a Supabase client, or None if unavailable/misconfigured."""
    if not SUPABASE_SDK_AVAILABLE or not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


def is_demo_mode():
    return st.session_state.get("supabase_client") is None


# ==========================================================================
# SESSION STATE
# ==========================================================================

def init_session_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "user_email" not in st.session_state:
        st.session_state.user_email = None

    if "supabase_url" not in st.session_state or "supabase_key" not in st.session_state:
        url, key = get_supabase_credentials()
        st.session_state.supabase_url = url
        st.session_state.supabase_key = key

    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = get_supabase_client(
            st.session_state.supabase_url, st.session_state.supabase_key
        )

    if "audit_meta" not in st.session_state:
        st.session_state.audit_meta = {
            "audit_title": "",
            "client_name": "",
            "auditor_name": "",
            "audit_date": date.today(),
            "audit_phase": AUDIT_PHASES[0],
        }

    if "categories" not in st.session_state:
        st.session_state.categories = {
            cat: {
                "client_score": 1,
                "auditor_score": 1,
                "severity": "Normal",
                "notes": "",
                # "photos" holds MULTIPLE photos: a list of dicts, each
                # {"hash": ..., "bytes": ..., "captured_at": datetime, "url": None}
                "photos": [],
                "audio_bytes": None,
                "audio_hash": None,
                "audio_captured_at": None,
                "audio_url": None,
            }
            for cat in CATEGORIES
        }

    if "last_saved_audit_id" not in st.session_state:
        st.session_state.last_saved_audit_id = None

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = None


def _bytes_hash(b):
    if not b:
        return None
    return hashlib.md5(b).hexdigest()


def format_ts(ts):
    if not ts:
        return None
    return ts.strftime("%b %d, %Y • %I:%M:%S %p")


def display_name_from_email(email):
    """Turns an email like jane.doe@company.com into 'Jane Doe'."""
    if not email:
        return ""
    local_part = email.split("@")[0]
    cleaned = local_part.replace(".", " ").replace("_", " ").replace("-", " ")
    return cleaned.title()


# ==========================================================================
# DELETE CONFIRMATION DIALOG
# ==========================================================================

@st.dialog("Delete photo")
def confirm_delete_photo_dialog(cat_name, photo_index):
    st.write("Are you sure you want to delete this photo? This cannot be undone.")
    photos = st.session_state.categories[cat_name]["photos"]
    if photo_index < len(photos):
        st.image(photos[photo_index]["bytes"], use_container_width=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.session_state.confirm_delete = None
            st.rerun()
    with col2:
        if st.button("Delete", type="primary", use_container_width=True):
            if photo_index < len(photos):
                del photos[photo_index]
            st.session_state.confirm_delete = None
            st.rerun()


# ==========================================================================
# AUTHENTICATION
# ==========================================================================

def login_screen():
    st.markdown(
        "<p style='text-align:center; color:#A10D29; font-weight:700; "
        "letter-spacing:2px; text-transform:uppercase; font-size:12px; "
        "margin-bottom:20px;'>Internal OPPA</p>"
        "<h1 style='text-align:center; font-size:44px; line-height:1.2; "
        f"margin:0 0 20px;'>{APP_TITLE}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:#666; font-size:17px; "
        "margin:0 0 32px;'>Uncover the gap between what clients feel "
        "and what the floor shows.</p>",
        unsafe_allow_html=True,
    )
    st.write("")

    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        with st.container(border=True):
            if is_demo_mode():
                st.info(
                    "**Demo Mode.** No Supabase keys detected. "
                    "You can explore the full app, but sign-in and cloud "
                    "save/export are disabled. Add `SUPABASE_URL` / "
                    "`SUPABASE_KEY` to `.streamlit/secrets.toml` to enable "
                    "full functionality."
                )
                if st.button("Continue in Demo Mode", use_container_width=True, type="primary"):
                    st.session_state.authenticated = True
                    st.session_state.user_email = "demo@local"
                    st.rerun()
            else:
                st.subheader("Sign In")
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                col_a, col_b = st.columns(2)
                with col_a:
                    login_clicked = st.button("Log In", use_container_width=True, type="primary")
                with col_b:
                    demo_clicked = st.button("Use Demo Mode", use_container_width=True)

                if login_clicked:
                    if not email or not password:
                        st.error("Please enter both email and password.")
                    else:
                        try:
                            client = st.session_state.supabase_client
                            result = client.auth.sign_in_with_password(
                                {"email": email, "password": password}
                            )
                            if result and result.user:
                                st.session_state.authenticated = True
                                st.session_state.user_email = email
                                st.rerun()
                            else:
                                st.error("Invalid credentials.")
                        except Exception as e:
                            st.error(f"Login failed: {e}")

                if demo_clicked:
                    st.session_state.authenticated = True
                    st.session_state.user_email = "demo@local"
                    st.rerun()


# ==========================================================================
# HEADER & METADATA BAR
# ==========================================================================

def render_header():
    left, right = st.columns([4, 1])
    with left:
        st.markdown(
            "<p style='color:#A10D29; font-weight:700; letter-spacing:2px; "
            "text-transform:uppercase; font-size:11px; margin:0 0 4px;'>"
            "Internal OPPA</p>"
            f"<h1 style='font-size:32px; margin:0;'>{APP_TITLE}</h1>",
            unsafe_allow_html=True,
        )
    with right:
        if is_demo_mode():
            st.markdown(
                "<div style='text-align:right; color:#A10D29; font-weight:700;'>"
                "Demo Mode</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div style='text-align:right; color:#888; font-size:0.85em;'>"
            f"{st.session_state.user_email or ''}</div>",
            unsafe_allow_html=True,
        )
        if st.button("Log Out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_email = None
            st.rerun()
    st.divider()


def render_metadata_bar():
    meta = st.session_state.audit_meta

    # Auto-fill the auditor name from whoever is logged in, the first time
    # the field is empty. The person can still edit it if it's wrong.
    if not meta["auditor_name"] and st.session_state.user_email:
        meta["auditor_name"] = display_name_from_email(st.session_state.user_email)

    with st.container(border=True):
        st.markdown("##### Audit Details")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            meta["audit_title"] = st.text_input(
                "Audit Title / ID", value=meta["audit_title"], key="meta_title"
            )
        with c2:
            meta["client_name"] = st.text_input(
                "Client Name", value=meta["client_name"], key="meta_client"
            )
        with c3:
            meta["auditor_name"] = st.text_input(
                "Auditor Name", value=meta["auditor_name"], key="meta_auditor"
            )
        with c4:
            meta["audit_date"] = st.date_input(
                "Date", value=meta["audit_date"], key="meta_date"
            )
        with c5:
            meta["audit_phase"] = st.selectbox(
                "Audit Phase",
                AUDIT_PHASES,
                index=AUDIT_PHASES.index(meta["audit_phase"]),
                key="meta_phase",
            )


# ==========================================================================
# CATEGORY CARD
# ==========================================================================

def render_category_card(cat_name, index):
    data = st.session_state.categories[cat_name]
    gap = abs(data["client_score"] - data["auditor_score"])
    flag_label = "  [CRITICAL DISCONNECT]" if gap >= CRITICAL_GAP_THRESHOLD else ""

    with st.expander(f"**{index}. {cat_name}**{flag_label}", expanded=(index == 1)):
        c1, c2 = st.columns(2)
        with c1:
            data["client_score"] = st.slider(
                "Client Score (1 = Low Pain/Friction, 5 = Severe Pain/Friction)",
                1, 5, data["client_score"], key=f"client_{cat_name}",
            )
        with c2:
            data["auditor_score"] = st.slider(
                "Auditor Score (1 = Low Pain/Friction, 5 = Severe Pain/Friction)",
                1, 5, data["auditor_score"], key=f"auditor_{cat_name}",
            )

        data["severity"] = st.selectbox(
            "Severity Flag",
            SEVERITY_OPTIONS,
            index=SEVERITY_OPTIONS.index(data["severity"]),
            key=f"severity_{cat_name}",
        )

        data["notes"] = st.text_area(
            "Field Observations / Root-Cause Notes",
            value=data["notes"],
            placeholder="Quick notes from the floor: what's causing the pain point, "
                        "who flagged it, any immediate fix ideas...",
            key=f"notes_{cat_name}",
            height=90,
        )

        m1, m2 = st.columns(2)
        with m1:
            st.markdown(f"**Photo Evidence** ({len(data['photos'])} attached)")

            existing_hashes = {p["hash"] for p in data["photos"]}

            photo = st.camera_input("Take a photo", key=f"camera_{cat_name}", label_visibility="collapsed")
            if photo is not None:
                photo_bytes = photo.getvalue()
                new_hash = _bytes_hash(photo_bytes)
                # Only append when this is genuinely a new capture, not a
                # rerun replaying the same widget value.
                if new_hash not in existing_hashes:
                    data["photos"].append({
                        "hash": new_hash,
                        "bytes": photo_bytes,
                        "captured_at": datetime.now(),
                        "url": None,
                    })
                    st.rerun()

            uploads = st.file_uploader(
                "Or upload one or more images",
                type=["png", "jpg", "jpeg"],
                key=f"upload_{cat_name}",
                accept_multiple_files=True,
            )
            if uploads:
                added_any = False
                for up in uploads:
                    up_bytes = up.getvalue()
                    up_hash = _bytes_hash(up_bytes)
                    if up_hash not in existing_hashes:
                        data["photos"].append({
                            "hash": up_hash,
                            "bytes": up_bytes,
                            "captured_at": datetime.now(),
                            "url": None,
                        })
                        existing_hashes.add(up_hash)
                        added_any = True
                if added_any:
                    st.rerun()

            for i, p in enumerate(data["photos"]):
                st.image(p["bytes"], use_container_width=True)
                cap_col, del_col = st.columns([3, 1])
                with cap_col:
                    st.caption(f"Captured: {format_ts(p['captured_at'])}")
                with del_col:
                    if st.button("Delete", key=f"del_photo_{cat_name}_{i}", use_container_width=True):
                        confirm_delete_photo_dialog(cat_name, i)

        with m2:
            st.markdown("**Voice Note**")
            audio = st.audio_input("Record a voice note", key=f"audio_{cat_name}", label_visibility="collapsed")
            if audio is not None:
                audio_bytes = audio.getvalue()
                new_hash = _bytes_hash(audio_bytes)
                # Same auto-timestamp rule as photos above: only stamp
                # when the recording itself actually changes.
                if new_hash != data["audio_hash"]:
                    data["audio_hash"] = new_hash
                    data["audio_bytes"] = audio_bytes
                    data["audio_captured_at"] = datetime.now()
            if data["audio_bytes"]:
                st.audio(data["audio_bytes"])
                st.caption(f"Recorded: {format_ts(data['audio_captured_at'])}")

        if gap >= CRITICAL_GAP_THRESHOLD:
            st.warning(
                f"Perception gap of {gap} points. Flagged as a critical disconnect."
            )


# ==========================================================================
# COMPLETION SECTION (end of the 12 categories)
# ==========================================================================

def render_completion_section():
    cats = st.session_state.categories
    notes_count = sum(1 for c in cats.values() if c["notes"].strip())
    photo_count = sum(len(c["photos"]) for c in cats.values())
    audio_count = sum(1 for c in cats.values() if c["audio_bytes"])
    critical_count = sum(
        1 for c in cats.values() if abs(c["client_score"] - c["auditor_score"]) >= CRITICAL_GAP_THRESHOLD
    )

    st.success("**You've reached the end of the 12 categories.**")
    with st.container(border=True):
        st.markdown("#### Assessment Snapshot")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Categories with Notes", f"{notes_count} / {len(CATEGORIES)}")
        s2.metric("Photos Attached", photo_count)
        s3.metric("Voice Notes Attached", audio_count)
        s4.metric("Critical Disconnects", critical_count)

        st.markdown("#### What To Do Next")
        st.markdown(
            f"""
1. **Double-check the Audit Details** metadata bar at the top of the page is correct.
2. **Review the Gap Analysis Dashboard** tab for the radar chart and overall risk level.
3. **Check the Media Gallery** tab to confirm every photo/voice note landed in the right category.
4. **Go to Save & Export** to save this audit to Supabase and/or export the CSV.
            """
        )


# ==========================================================================
# METRICS / GAP ANALYSIS
# ==========================================================================

def compute_metrics():
    cats = st.session_state.categories
    total_client = sum(c["client_score"] for c in cats.values())
    total_auditor = sum(c["auditor_score"] for c in cats.values())
    overall_gap = abs(total_client - total_auditor)

    if overall_gap <= 8:
        risk_level = "Low Risk"
    elif overall_gap <= 16:
        risk_level = "Moderate Risk"
    else:
        risk_level = "High Risk"

    critical = [
        {
            "category": name,
            "client_score": c["client_score"],
            "auditor_score": c["auditor_score"],
            "gap": abs(c["client_score"] - c["auditor_score"]),
            "severity": c["severity"],
        }
        for name, c in cats.items()
        if abs(c["client_score"] - c["auditor_score"]) >= CRITICAL_GAP_THRESHOLD
    ]
    critical.sort(key=lambda x: x["gap"], reverse=True)

    return total_client, total_auditor, overall_gap, risk_level, critical


def render_dashboard():
    total_client, total_auditor, overall_gap, risk_level, critical = compute_metrics()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Client Score", total_client)
    m2.metric("Total Auditor Score", total_auditor)
    m3.metric("Overall Perception Gap", overall_gap)
    m4.metric("Risk Level", risk_level)

    st.write("")
    cats = st.session_state.categories
    client_vals = [cats[c]["client_score"] for c in CATEGORIES]
    auditor_vals = [cats[c]["auditor_score"] for c in CATEGORIES]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=client_vals + [client_vals[0]],
        theta=CATEGORIES + [CATEGORIES[0]],
        fill="toself",
        name="Client (Perception)",
        line_color="#4C78A8",
    ))
    fig.add_trace(go.Scatterpolar(
        r=auditor_vals + [auditor_vals[0]],
        theta=CATEGORIES + [CATEGORIES[0]],
        fill="toself",
        name="Auditor (Floor Reality)",
        line_color="#E45756",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
        showlegend=True,
        title="Client Perception vs. Auditor Floor Reality",
        height=550,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(color="#1a1a1a"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Critical Disconnects (gap >= 2)")
    if critical:
        st.dataframe(pd.DataFrame(critical), use_container_width=True, hide_index=True)
    else:
        st.info("No critical disconnects. Client and auditor scores are aligned (gap < 2 everywhere).")


# ==========================================================================
# MEDIA GALLERY
# ==========================================================================

def render_media_gallery():
    cats = st.session_state.categories
    any_media = any(c["photos"] or c["audio_bytes"] for c in cats.values())
    if not any_media:
        st.info("No photos or voice notes have been captured yet.")
        return

    for name, c in cats.items():
        if not (c["photos"] or c["audio_bytes"]):
            continue
        with st.container(border=True):
            st.markdown(f"**{name}**")
            col1, col2 = st.columns(2)
            with col1:
                if c["photos"]:
                    for p in c["photos"]:
                        st.image(p["bytes"], use_container_width=True)
                        st.caption(f"Captured: {format_ts(p['captured_at'])}")
                else:
                    st.caption("No photo")
            with col2:
                if c["audio_bytes"]:
                    st.audio(c["audio_bytes"])
                    st.caption(f"Recorded: {format_ts(c['audio_captured_at'])}")
                else:
                    st.caption("No voice note")


# ==========================================================================
# SAVE & EXPORT
# ==========================================================================

def upload_media_to_supabase(client, bucket, file_bytes, path):
    """Uploads bytes to a Supabase storage bucket and returns a public URL. Never raises."""
    try:
        client.storage.from_(bucket).upload(
            path, file_bytes, {"upsert": "true"}
        )
        return client.storage.from_(bucket).get_public_url(path)
    except Exception as e:
        st.warning(f"Could not upload to `{bucket}`: {e}")
        return None


def save_audit_to_supabase():
    client = st.session_state.supabase_client
    if client is None:
        st.error("Supabase is not configured. Running in Demo Mode, so save is disabled.")
        return

    meta = st.session_state.audit_meta
    total_client, total_auditor, overall_gap, risk_level, _ = compute_metrics()

    try:
        audit_row = {
            "audit_title": meta["audit_title"],
            "client_name": meta["client_name"],
            "auditor_name": meta["auditor_name"],
            "audit_date": str(meta["audit_date"]),
            "audit_phase": meta["audit_phase"],
            "total_client_score": total_client,
            "total_auditor_score": total_auditor,
            "overall_gap": overall_gap,
            "risk_level": risk_level,
            "created_by": st.session_state.user_email,
        }
        audit_resp = client.table("audits").insert(audit_row).execute()
        audit_id = audit_resp.data[0]["id"]
        st.session_state.last_saved_audit_id = audit_id

        for name, c in st.session_state.categories.items():
            photo_urls = []
            photo_timestamps = []
            for i, p in enumerate(c["photos"]):
                path = f"{audit_id}/{name.replace(' ', '_')}_{i}.png"
                url = upload_media_to_supabase(client, "oppa-photos", p["bytes"], path)
                p["url"] = url
                if url:
                    photo_urls.append(url)
                    photo_timestamps.append(p["captured_at"].isoformat())

            audio_url = c["audio_url"]
            if c["audio_bytes"]:
                path = f"{audit_id}/{name.replace(' ', '_')}.wav"
                audio_url = upload_media_to_supabase(client, "oppa-audio", c["audio_bytes"], path)
                c["audio_url"] = audio_url

            cat_row = {
                "audit_id": audit_id,
                "category": name,
                "client_score": c["client_score"],
                "auditor_score": c["auditor_score"],
                "gap": abs(c["client_score"] - c["auditor_score"]),
                "severity_flag": c["severity"],
                "notes": c["notes"],
                "photo_url": "|".join(photo_urls) if photo_urls else None,
                "audio_url": audio_url,
                "photo_captured_at": "|".join(photo_timestamps) if photo_timestamps else None,
                "audio_captured_at": c["audio_captured_at"].isoformat() if c["audio_captured_at"] else None,
            }
            client.table("audit_categories").insert(cat_row).execute()

        st.success(f"Audit saved to Supabase (id: {audit_id}).")
    except Exception as e:
        st.error(f"Failed to save audit to Supabase: {e}")


def build_export_dataframe():
    meta = st.session_state.audit_meta
    rows = []
    for name, c in st.session_state.categories.items():
        photo_timestamps = [format_ts(p["captured_at"]) for p in c["photos"]]
        rows.append({
            "audit_title": meta["audit_title"],
            "client_name": meta["client_name"],
            "auditor_name": meta["auditor_name"],
            "audit_date": meta["audit_date"],
            "audit_phase": meta["audit_phase"],
            "category": name,
            "client_score": c["client_score"],
            "auditor_score": c["auditor_score"],
            "gap": abs(c["client_score"] - c["auditor_score"]),
            "severity_flag": c["severity"],
            "notes": c["notes"],
            "photo_count": len(c["photos"]),
            "photo_captured_at": " | ".join(photo_timestamps),
            "audio_captured_at": format_ts(c["audio_captured_at"]) or "",
            "has_photo": len(c["photos"]) > 0,
            "has_audio": bool(c["audio_bytes"]),
        })
    return pd.DataFrame(rows)


def render_save_export():
    st.markdown("#### Save Audit")
    if is_demo_mode():
        st.info(
            "Running in **Demo Mode**. Connect Supabase (see the top of `app.py` "
            "or `secrets.toml.example`) to enable saving."
        )
    st.button(
        "Save Audit to Supabase",
        type="primary",
        disabled=is_demo_mode(),
        on_click=save_audit_to_supabase,
    )

    st.divider()
    st.markdown("#### Export CSV")
    df = build_export_dataframe()
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button(
        "Export Assessment Summary (CSV)",
        data=csv_buffer.getvalue(),
        file_name=f"oppa_audit_{date.today().isoformat()}.csv",
        mime="text/csv",
    )


# ==========================================================================
# MAIN APP
# ==========================================================================

def main():
    st.set_page_config(
        page_title="Internal OPPA",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_custom_css()
    init_session_state()

    if not st.session_state.authenticated:
        login_screen()
        return

    render_header()
    render_metadata_bar()
    st.write("")

    tab_assess, tab_dashboard, tab_gallery, tab_export = st.tabs(
        ["Assessment", "Gap Analysis Dashboard", "Media Gallery", "Save & Export"]
    )

    with tab_assess:
        for i, cat in enumerate(CATEGORIES, start=1):
            render_category_card(cat, i)
        st.divider()
        render_completion_section()

    with tab_dashboard:
        render_dashboard()

    with tab_gallery:
        render_media_gallery()

    with tab_export:
        render_save_export()


if __name__ == "__main__":
    main()
