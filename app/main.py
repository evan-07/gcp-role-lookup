"""
main.py

Streamlit entry point for the GCP Role Lookup tool.
Provides a UI for resolving GCP role titles to role IDs,
with fuzzy matching, supersession detection, and Terraform HCL output.
"""

import sys
import logging
from pathlib import Path

import streamlit as st

# Allow running from repo root or app/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.role_loader import load_roles, load_permissions, refresh_roles_from_api
from app.matcher import match_titles_bulk, MatchResult
from app.supersession import check_supersessions
from app.formatter import format_as_terraform, format_results_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="GCP Role Lookup",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

      html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

      .stApp { background: #0d1117; color: #e6edf3; }

      .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

      .app-header {
        display: flex; align-items: center; gap: 1rem;
        margin-bottom: 1rem; padding-bottom: 1rem;
        border-bottom: 1px solid #21262d;
      }
      .app-header h1 {
        font-family: 'Inter', sans-serif; font-size: 1.6rem;
        font-weight: 800; color: #e6edf3; margin: 0;
        letter-spacing: -0.02em;
      }
      .app-header p { font-size: 0.82rem; color: #7d8590; margin: 0; }

      .stat-row {
        display: flex; gap: 0.6rem; margin-bottom: 0.75rem;
        flex-wrap: wrap;
      }
      .stat-badge {
        display: inline-flex; align-items: center; gap: 0.4rem;
        padding: 0.25rem 0.65rem; border-radius: 20px;
        font-size: 0.76rem; font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
      }
      .badge-exact      { background:#0d2b1a; color:#3fb950; border:1px solid #238636; }
      .badge-fuzzy      { background:#2b1f0a; color:#d29922; border:1px solid #9e6a03; }
      .badge-miss       { background:#2b0a0a; color:#f85149; border:1px solid #8b2020; }
      .badge-total      { background:#161b22; color:#8b949e; border:1px solid #30363d; }
      .badge-superseded { background:#1a0d2b; color:#bc8cff; border:1px solid #6e40c9; }

      /* Viewport-fill textarea */
      .stTextArea textarea {
        background: #161b22 !important; color: #e6edf3 !important;
        border: 1px solid #30363d !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.83rem !important; border-radius: 6px !important;
        height: calc(100vh - 260px) !important;
        min-height: 400px !important; resize: none !important;
      }
      .stTextArea textarea:focus {
        border-color: #388bfd !important;
        box-shadow: 0 0 0 3px rgba(56,139,253,0.12) !important;
      }

      .hcl-placeholder {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 6px; height: calc(100vh - 260px);
        min-height: 400px; display: flex;
        align-items: center; justify-content: center;
        color: #484f58; font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
      }


      .section-label {
        font-size: 0.70rem; font-weight: 600; letter-spacing: 0.1em;
        text-transform: uppercase; color: #7d8590;
        margin-bottom: 0.4rem; margin-top: 1rem;
      }

      [data-testid="stSidebar"] {
        background: #010409 !important;
        border-right: 1px solid #21262d;
      }
      [data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }

      .stButton > button {
        background: #21262d; color: #e6edf3;
        border: 1px solid #30363d; border-radius: 6px;
        font-family: 'Inter', sans-serif; font-weight: 600;
        font-size: 0.83rem; padding: 0.4rem 1.1rem;
        transition: all 0.15s ease;
      }
      .stButton > button:hover { background:#30363d; border-color:#8b949e; }
      .stButton > button[kind="primary"] {
        background: #238636; border-color: #2ea043; color: #ffffff;
      }
      .stButton > button[kind="primary"]:hover { background: #2ea043; }

      #MainMenu, footer, header { visibility: hidden; }
      hr { border-color: #21262d; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_roles() -> list[dict]:
    """Load and cache roles from disk."""
    return load_roles()


@st.cache_data(show_spinner=False)
def get_permissions() -> dict[str, set[str]]:
    """Load and cache role permissions. Returns {} if missing."""
    return load_permissions()


def clear_all_caches() -> None:
    """Clear both Streamlit caches to force reload."""
    get_roles.clear()
    get_permissions.clear()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        "<div style='font-family:Inter;font-weight:800;"
        "font-size:1.1rem;color:#e6edf3;margin-bottom:0.25rem'>"
        "🔐 GCP Role Lookup</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:0.75rem;color:#7d8590;"
        "margin-bottom:1.25rem'>"
        "IAM Role Title → Role ID Resolver</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown(
        "<div class='section-label'>Data Source</div>",
        unsafe_allow_html=True,
    )

    roles_data: list[dict] = []
    try:
        roles_data = get_roles()
        st.success(f"✓ {len(roles_data)} roles loaded")
    except FileNotFoundError as exc:
        st.error(str(exc))
    except ValueError as exc:
        st.error(str(exc))

    permissions_data: dict[str, set[str]] = get_permissions()
    if permissions_data:
        st.success(
            f"✓ Permissions loaded for {len(permissions_data)} roles"
        )
    else:
        st.warning(
            "⚠️ role_permissions.json not found. "
            "Supersession checking disabled. "
            "Run `refresh_roles.sh` to enable it."
        )

    st.divider()

    st.markdown(
        "<div class='section-label'>Live Refresh</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Requires GCP credentials via ADC. "
        "Service account needs `roles/iam.roleViewer`."
    )

    if st.button("↻ Refresh from GCP API", use_container_width=True):
        with st.spinner("Calling GCP IAM API…"):
            success, msg = refresh_roles_from_api()
        if success:
            clear_all_caches()
            roles_data = get_roles()
            permissions_data = get_permissions()
            st.success(msg)
        else:
            st.error(msg)

    st.divider()
    st.caption(
        "💡 Match thresholds: ≥85% High · 60–84% Medium · <60% Low\n\n"
        "⛔ Superseded = another role in your batch fully contains "
        "this role's permissions."
    )


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="app-header">
      <div>
        <h1>🔐 GCP Role Lookup</h1>
        <p>
          Resolve GCP IAM role titles to role IDs ·
          Supersession detection · Terraform HCL output
        </p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col_input, col_output = st.columns([1, 2], gap="large")

with col_input:
    st.markdown(
        "<div class='section-label'>Role Titles — one per line</div>",
        unsafe_allow_html=True,
    )
    input_text = st.text_area(
        label="Role Titles Input",
        placeholder=(
            "BigQuery Connection User\n"
            "BigQuery Data Editor\n"
            "BigQuery Data Viewer\n"
            "BigQuery Job User\n"
            "Storage Admin"
        ),
        label_visibility="collapsed",
    )

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        resolve_clicked = st.button(
            "Resolve Roles →",
            type="primary",
            use_container_width=True,
            disabled=not roles_data,
        )
    with col_btn2:
        clear_clicked = st.button(
            "Clear",
            use_container_width=True,
        )

    if clear_clicked:
        st.rerun()


# ---------------------------------------------------------------------------
# Output column
# ---------------------------------------------------------------------------
with col_output:
    st.markdown(
        "<div class='section-label'>Terraform HCL Output</div>",
        unsafe_allow_html=True,
    )

    if resolve_clicked and input_text.strip() and roles_data:

        # 1. Match
        results: list[MatchResult] = match_titles_bulk(
            input_text, roles_data
        )

        # 2. Supersession (skipped gracefully if permissions missing)
        if permissions_data:
            check_supersessions(results, permissions_data, roles_data)

        # 3. Format + summarise
        summary = format_results_summary(results)
        hcl_output = format_as_terraform(results)

        # Stat badges
        total = sum(v for k, v in summary.items() if k != "empty")
        fuzzy = summary["high"] + summary["medium"]
        missed = summary["low"] + summary["not_found"]

        st.markdown(
            f"""
            <div class="stat-row">
              <span class="stat-badge badge-total">{total} inputs</span>
              <span class="stat-badge badge-exact">✓ {summary['exact']} exact</span>
              <span class="stat-badge badge-fuzzy">~ {fuzzy} fuzzy</span>
              <span class="stat-badge badge-miss">✗ {missed} unresolved</span>
              <span class="stat-badge badge-superseded">⛔ {summary['superseded']} superseded</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # HCL output — st.code provides syntax highlighting + copy button
        st.code(hcl_output, language="hcl")

    elif resolve_clicked and not roles_data:
        st.error(
            "Roles data could not be loaded. "
            "Check the sidebar for details."
        )

    else:
        st.markdown(
            "<div class='hcl-placeholder'>"
            "← Enter role titles and click Resolve Roles"
            "</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Review Required — full-width collapsible table, rendered after columns
# Only shown when there is something to review from the last resolve run
# ---------------------------------------------------------------------------
if resolve_clicked and input_text.strip() and roles_data and 'results' in dir():
    import pandas as pd

    review_rows = []
    for r in results:
        if r.status in ("exact", "empty") and not r.supersession:
            continue

        if r.supersession:
            status_label = "⛔ Superseded"
            note = f"Covered by: {r.supersession.superseded_by_title}"
        elif r.status == "high":
            status_label = "~ High confidence"
            note = f"Matched: {r.matched_title}"
        elif r.status == "medium":
            status_label = "~ Medium confidence"
            note = f"Matched: {r.matched_title}"
        elif r.status == "low":
            status_label = "✗ Low confidence"
            suggestions = "; ".join(
                f"{s['title']} ({s['confidence']}%)"
                for s in (r.suggestions or [])
            )
            note = f"Suggestions: {suggestions}" if suggestions else "No suggestions"
        else:
            status_label = "✗ Not found"
            note = ""

        review_rows.append({
            "Status":        status_label,
            "Input Title":   r.input_title,
            "Matched Title": r.matched_title or "—",
            "Confidence":    f"{r.confidence}%" if r.confidence else "—",
            "Note":          note,
        })

    if review_rows:
        with st.expander(
            f"⚠️ Review Required — {len(review_rows)} item(s)",
            expanded=False,
        ):
            df = pd.DataFrame(review_rows)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Status":        st.column_config.TextColumn(width="medium"),
                    "Input Title":   st.column_config.TextColumn(width="medium"),
                    "Matched Title": st.column_config.TextColumn(width="medium"),
                    "Confidence":    st.column_config.TextColumn(width="small"),
                    "Note":          st.column_config.TextColumn(width="large"),
                },
            )