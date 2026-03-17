"""
main.py

Streamlit entry point for the GCP Role Lookup tool.
Handles page config, global CSS, session state init, data loading,
sidebar navigation, and dispatch to active page modules.
"""

import logging

import streamlit as st
import streamlit.components.v1

from app.role_loader import load_roles, load_permissions, clear_all_caches, refresh_roles_from_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="GCP Role Lookup",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS
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

      .stTextArea textarea {
        background: #161b22 !important; color: #e6edf3 !important;
        border: 1px solid #30363d !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.83rem !important; border-radius: 6px !important;
        resize: vertical !important;
      }
      .stTextArea textarea:focus {
        border-color: #388bfd !important;
        box-shadow: 0 0 0 3px rgba(56,139,253,0.12) !important;
      }

      .hcl-placeholder {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 6px; min-height: 300px; display: flex;
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

      /* Keep Streamlit's header visible so the collapsed-sidebar toggle remains usable. */
      #MainMenu, footer { visibility: hidden; }
      hr { border-color: #21262d; }

      /* Suppress the 1px gap from the Ctrl+Enter JS component */
      .stCustomComponentV1 { line-height: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Ctrl+Enter → click active primary button
# ---------------------------------------------------------------------------
st.components.v1.html(
    """
    <script>
      const doc = window.parent.document;
      doc.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          const candidates = doc.querySelectorAll('button[kind="primary"]:not([disabled])');
          for (const btn of candidates) {
            if (!btn.closest('[data-testid="stSidebar"]')) {
              btn.click();
              break;
            }
          }
        }
      });
    </script>
    """,
    height=1,
)

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "page": "resolve",
    "resolve_input": "",
    "inspect_role_a": "",
    "inspect_role_b": "",
    "inspect_diff_mode": False,
    "permission_search_query": "",
    "resolve_output_format": "HCL",
    "find_role_input": "",
    "resolve_results": None,
    "roles_load_error": None,
}
for _key, _val in _DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

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


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
try:
    roles_data: list[dict] = get_roles()
    st.session_state["roles_load_error"] = None
except (FileNotFoundError, ValueError) as exc:
    roles_data = []
    st.session_state["roles_load_error"] = str(exc)

try:
    permissions_data: dict[str, set[str]] = get_permissions()
except Exception as exc:  # noqa: BLE001
    logger.warning("Unexpected error loading permissions: %s", exc)
    permissions_data = {}

# ---------------------------------------------------------------------------
# Sidebar: brand header + nav buttons
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

    page = st.session_state["page"]

    if st.button(
        "Resolve Titles",
        type="primary" if page == "resolve" else "secondary",
        use_container_width=True,
    ):
        st.session_state["page"] = "resolve"
        st.rerun()

    if st.button(
        "Role Inspector",
        type="primary" if page == "inspect" else "secondary",
        use_container_width=True,
    ):
        st.session_state["page"] = "inspect"
        st.rerun()

    if st.button(
        "Permission Search",
        type="primary" if page == "permissions" else "secondary",
        use_container_width=True,
    ):
        st.session_state["page"] = "permissions"
        st.rerun()

    if st.button(
        "Find Smallest Role",
        type="primary" if page == "find_role" else "secondary",
        use_container_width=True,
    ):
        st.session_state["page"] = "find_role"
        st.rerun()

    if st.button(
        "Help",
        type="primary" if page == "help" else "secondary",
        use_container_width=True,
    ):
        st.session_state["page"] = "help"
        st.rerun()

    st.divider()

    st.markdown(
        "<div class='section-label'>Data Source</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.get("roles_load_error"):
        st.error(st.session_state["roles_load_error"])
    else:
        st.success(f"✓ {len(roles_data)} roles loaded")

    if permissions_data:
        st.success(f"✓ Permissions loaded for {len(permissions_data)} roles")
    else:
        st.warning(
            "⚠️ role_permissions.json not found. "
            "Supersession checking disabled. "
            "Run `python scripts/refresh_roles.py` to enable it."
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
            st.success(msg)
            clear_all_caches()
            st.rerun()
        else:
            st.error(msg)

# ---------------------------------------------------------------------------
# Dispatch to active page
# ---------------------------------------------------------------------------
if st.session_state["page"] == "resolve":
    from app.page_views.resolve import render as render_resolve
    render_resolve(roles_data, permissions_data)
elif st.session_state["page"] == "inspect":
    from app.page_views.inspect import render as render_inspect
    render_inspect(roles_data, permissions_data)
elif st.session_state["page"] == "permissions":
    from app.page_views.permissions import render as render_permissions
    render_permissions(roles_data, permissions_data)
elif st.session_state["page"] == "find_role":
    from app.page_views.find_role import render as render_find_role
    render_find_role(roles_data, permissions_data)
elif st.session_state["page"] == "help":
    from app.page_views.help import render as render_help
    render_help()
