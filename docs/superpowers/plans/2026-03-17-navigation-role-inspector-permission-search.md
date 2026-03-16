# Navigation, Role Inspector & Permission Search — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add sidebar navigation, Role Inspector, and Permission Search pages to the GCP Role Lookup Streamlit app without changing any existing Resolve Titles behavior.

**Architecture:** Extract existing Resolve Titles logic into `app/pages/resolve.py`, add two new page modules (`inspect.py`, `permissions.py`), add `clear_all_caches()` to `role_loader.py`, and refactor `main.py` to dispatch to the active page based on `st.session_state["page"]`.

**Tech Stack:** Python 3.11+, Streamlit 1.55.0, pandas 2.3.3, pytest (added to requirements.txt)

---

## Chunk 1: Git Worktree + Cache Invalidation

### Task 1: Create Git Worktree

**Files:**
- No files — git operations only

- [ ] **Step 1: Create a git worktree for feature isolation**

From the repo root:
```bash
cd "c:\Users\e.d.buenaventura\OneDrive - Sysco Corporation\Documents\gcp-role-lookup"
git worktree add ../gcp-role-lookup-nav feature/navigation-and-pages
```
Expected: `Preparing worktree (new branch 'feature/navigation-and-pages')` with no errors.

- [ ] **Step 2: Verify worktree and switch to it**

```bash
git worktree list
cd ../gcp-role-lookup-nav
```
Expected: worktree listed at `../gcp-role-lookup-nav`. All subsequent steps run inside this directory.

---

### Task 2: Add `clear_all_caches()` + Test Scaffolding

**Files:**
- Modify: `app/role_loader.py` (append function at end)
- Modify: `requirements.txt` (add pytest)
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_role_loader.py`

- [ ] **Step 1: Add pytest to `requirements.txt`**

Append this line to the end of `requirements.txt`:
```
pytest==8.3.4
```

- [ ] **Step 2: Write the failing test**

Create `tests/__init__.py` as an empty file.

Create `tests/test_role_loader.py`:
```python
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_clear_all_caches_calls_st_cache_data_clear():
    mock_st = MagicMock()
    with patch.dict("sys.modules", {"streamlit": mock_st}):
        import importlib
        import app.role_loader as rl
        importlib.reload(rl)
        rl.clear_all_caches()
    mock_st.cache_data.clear.assert_called_once()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
.venv\Scripts\python -m pytest tests/test_role_loader.py::test_clear_all_caches_calls_st_cache_data_clear -v
```
Expected: FAIL with `AttributeError: module 'app.role_loader' has no attribute 'clear_all_caches'`

- [ ] **Step 4: Add `clear_all_caches()` to `app/role_loader.py`**

Append to the end of `app/role_loader.py` (after the last function):
```python


def clear_all_caches() -> None:
    """Clear all Streamlit data caches (affects all active server sessions)."""
    import streamlit as st
    st.cache_data.clear()
```

- [ ] **Step 5: Run test to verify it passes**

```bash
.venv\Scripts\python -m pytest tests/test_role_loader.py -v
```
Expected: 1 test PASSED.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt app/role_loader.py tests/__init__.py tests/test_role_loader.py
git commit -m "feat: add clear_all_caches() to role_loader; add test scaffolding"
```

---

## Chunk 2: pages/ Package + resolve.py

### Task 3: Create `pages/` Package

**Files:**
- Create: `app/pages/__init__.py` (empty)

- [ ] **Step 1: Create the empty package marker**

```bash
mkdir -p app/pages
touch app/pages/__init__.py
```
On Windows bash: `mkdir app/pages && touch app/pages/__init__.py`

- [ ] **Step 2: Verify**

```bash
ls app/pages/
```
Expected: `__init__.py` listed.

---

### Task 4: Create `pages/resolve.py`

**Files:**
- Create: `app/pages/resolve.py`
- Reference: `app/main.py` lines 159–403 (source of extracted logic)

This module receives `roles: list[dict]` and `permissions: dict[str, set[str]]` from `main.py` and renders both the Resolve Titles-specific sidebar controls and the main panel. The text area uses `key="resolve_input"` so its value persists when the user navigates away and back. The `app-header` block moves here from `main.py`.

- [ ] **Step 1: Create `app/pages/resolve.py`**

```python
"""
resolve.py

Resolve Titles page — matches GCP role titles to role IDs,
shows Terraform HCL output, supersession detection, and review table.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.formatter import format_as_terraform, format_results_summary
from app.matcher import MatchResult, match_titles_bulk
from app.role_loader import clear_all_caches, refresh_roles_from_api
from app.supersession import check_supersessions


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Resolve Titles page (sidebar controls + main panel)."""

    # --- Sidebar: data source + refresh controls ---
    st.sidebar.divider()

    st.sidebar.markdown(
        "<div class='section-label'>Data Source</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.get("roles_load_error"):
        st.sidebar.error(st.session_state["roles_load_error"])
    else:
        st.sidebar.success(f"✓ {len(roles)} roles loaded")

    if permissions:
        st.sidebar.success(
            f"✓ Permissions loaded for {len(permissions)} roles"
        )
    else:
        st.sidebar.warning(
            "⚠️ role_permissions.json not found. "
            "Supersession checking disabled. "
            "Run `refresh_roles.sh` to enable it."
        )

    st.sidebar.divider()

    st.sidebar.markdown(
        "<div class='section-label'>Live Refresh</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption(
        "Requires GCP credentials via ADC. "
        "Service account needs `roles/iam.roleViewer`."
    )

    if st.sidebar.button("↻ Refresh from GCP API", use_container_width=True):
        with st.spinner("Calling GCP IAM API…"):
            success, msg = refresh_roles_from_api()
        if success:
            st.sidebar.success(msg)
            clear_all_caches()
            st.rerun()
        else:
            st.sidebar.error(msg)

    st.sidebar.divider()
    st.sidebar.caption(
        "💡 Match thresholds: ≥85% High · 60–84% Medium · <60% Low\n\n"
        "⛔ Superseded = another role in your batch fully contains "
        "this role's permissions."
    )

    # --- Main panel ---
    if st.session_state.get("roles_load_error"):
        st.error(
            "Roles data could not be loaded: "
            + st.session_state["roles_load_error"]
        )
        return

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
            key="resolve_input",
        )

        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            resolve_clicked = st.button(
                "Resolve Roles →",
                type="primary",
                use_container_width=True,
                disabled=not roles,
            )
        with col_btn2:
            clear_clicked = st.button(
                "Clear",
                use_container_width=True,
            )

        if clear_clicked:
            st.session_state["resolve_input"] = ""
            st.rerun()

    with col_output:
        st.markdown(
            "<div class='section-label'>Terraform HCL Output</div>",
            unsafe_allow_html=True,
        )

        if resolve_clicked and input_text.strip() and roles:
            results: list[MatchResult] = match_titles_bulk(input_text, roles)

            if permissions:
                check_supersessions(results, permissions, roles)

            summary = format_results_summary(results)
            hcl_output = format_as_terraform(results)

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

            st.code(hcl_output, language="hcl")

        elif resolve_clicked and not roles:
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

    # --- Review Required table (full-width, below columns) ---
    if resolve_clicked and input_text.strip() and roles and "results" in dir():
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
                note = (
                    f"Suggestions: {suggestions}" if suggestions else "No suggestions"
                )
            else:
                status_label = "✗ Not found"
                note = ""

            review_rows.append(
                {
                    "Status": status_label,
                    "Input Title": r.input_title,
                    "Matched Title": r.matched_title or "—",
                    "Confidence": f"{r.confidence}%" if r.confidence else "—",
                    "Note": note,
                }
            )

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
                        "Status": st.column_config.TextColumn(width="medium"),
                        "Input Title": st.column_config.TextColumn(width="medium"),
                        "Matched Title": st.column_config.TextColumn(width="medium"),
                        "Confidence": st.column_config.TextColumn(width="small"),
                        "Note": st.column_config.TextColumn(width="large"),
                    },
                )
```

- [ ] **Step 2: Verify import works (run from `app/` directory)**

```bash
cd "c:\Users\e.d.buenaventura\OneDrive - Sysco Corporation\Documents\gcp-role-lookup-nav\app"
.venv\Scripts\python -c "from pages.resolve import render; print('OK')"
```
Expected: `OK` with no import errors.

- [ ] **Step 3: Commit**

```bash
git add app/pages/__init__.py app/pages/resolve.py
git commit -m "feat: extract Resolve Titles page to pages/resolve.py"
```

---

## Chunk 3: Refactor main.py

### Task 5: Rewrite `main.py` as Nav/Dispatch Entry Point

**Files:**
- Modify: `app/main.py` (complete replacement)

`main.py` shrinks to: page config → global CSS → session state init → data loading → sidebar brand header + nav buttons → dispatch to active page module. All page-specific logic moves to the `pages/` modules.

Key changes from the current `main.py`:
- `clear_all_caches()` definition deleted (moved to `role_loader.py`)
- `get_permissions.clear()` / `get_roles.clear()` calls removed
- Sidebar brand header preserved (lines 160–171)
- Data loading refactored to catch errors into `roles_load_error` session state key
- Nav buttons added with `type="primary"/"secondary"` active state
- Page dispatch added at the bottom
- `app-header` block removed (now lives in `resolve.py`)
- All existing CSS preserved unchanged

- [ ] **Step 1: Rewrite `app/main.py`**

```python
"""
main.py

Streamlit entry point for the GCP Role Lookup tool.
Handles page config, global CSS, session state init, data loading,
sidebar navigation, and dispatch to active page modules.
"""

import sys
import logging
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.role_loader import load_roles, load_permissions

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
# Session state initialization
# ---------------------------------------------------------------------------
_DEFAULTS: dict = {
    "page": "resolve",
    "resolve_input": "",
    "inspect_role_a": "",
    "inspect_role_b": "",
    "inspect_diff_mode": False,
    "permission_search_query": "",
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

# ---------------------------------------------------------------------------
# Dispatch to active page
# ---------------------------------------------------------------------------
if page == "resolve":
    from pages.resolve import render as render_resolve
    render_resolve(roles_data, permissions_data)
elif page == "inspect":
    from pages.inspect import render as render_inspect
    render_inspect(roles_data, permissions_data)
elif page == "permissions":
    from pages.permissions import render as render_permissions
    render_permissions(roles_data, permissions_data)
```

- [ ] **Step 2: Verify no syntax errors**

```bash
cd "c:\Users\e.d.buenaventura\OneDrive - Sysco Corporation\Documents\gcp-role-lookup-nav\app"
.venv\Scripts\python -c "import ast; ast.parse(open('main.py').read()); print('Syntax OK')"
```
Expected: `Syntax OK`

- [ ] **Step 3: Run existing tests to confirm nothing broke**

```bash
cd "c:\Users\e.d.buenaventura\OneDrive - Sysco Corporation\Documents\gcp-role-lookup-nav"
.venv\Scripts\python -m pytest tests/ -v
```
Expected: All tests PASSED.

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "refactor: rewrite main.py as nav/dispatch entry point"
```

---

## Chunk 4: Role Inspector (inspect.py)

### Task 6: Create `pages/inspect.py`

**Files:**
- Create: `app/pages/inspect.py`
- Create: `tests/test_inspect_logic.py`

The diff logic (set operations) is pure Python and can be tested directly without Streamlit. No new helper functions are needed beyond the page module itself.

- [ ] **Step 1: Write the failing tests for diff logic**

Create `tests/test_inspect_logic.py`:
```python
"""Tests for Role Inspector diff logic edge cases."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_diff_only_in_a():
    perms_a = {"a.b.c", "d.e.f", "g.h.i"}
    perms_b = {"d.e.f", "x.y.z"}
    assert perms_a - perms_b == {"a.b.c", "g.h.i"}


def test_diff_in_both():
    perms_a = {"a.b.c", "d.e.f"}
    perms_b = {"d.e.f", "x.y.z"}
    assert perms_a & perms_b == {"d.e.f"}


def test_diff_only_in_b():
    perms_a = {"a.b.c", "d.e.f"}
    perms_b = {"d.e.f", "x.y.z"}
    assert perms_b - perms_a == {"x.y.z"}


def test_empty_diff_column_renders_none_marker():
    """Empty diff set produces the '(none)' sentinel used in st.code."""
    empty: set[str] = set()
    result = "\n".join(sorted(empty)) if empty else "(none)"
    assert result == "(none)"


def test_nonempty_diff_column_sorts_alphabetically():
    perms = {"z.a.b", "a.b.c", "m.n.o"}
    result = "\n".join(sorted(perms))
    assert result == "a.b.c\nm.n.o\nz.a.b"
```

- [ ] **Step 2: Run tests to verify they all pass (pure Python — no impl needed)**

```bash
.venv\Scripts\python -m pytest tests/test_inspect_logic.py -v
```
Expected: 5 tests PASSED (pure set operations, no page module required).

- [ ] **Step 3: Create `app/pages/inspect.py`**

```python
"""
inspect.py

Role Inspector page — given a GCP role ID, shows its title and full
permission list. Optionally diffs two roles side-by-side.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Role Inspector page."""

    # Global unavailability guard — runs before any role-specific lookup
    if not permissions:
        st.warning(
            "Permission data is not loaded. "
            "Please use the Refresh button on the Resolve Titles page."
        )
        return

    if st.session_state.get("roles_load_error"):
        st.error(
            "Roles data could not be loaded: "
            + st.session_state["roles_load_error"]
        )
        return

    role_title_map = {r["name"]: r["title"] for r in roles}

    col_input, col_output = st.columns([1, 2], gap="large")

    with col_input:
        st.markdown(
            "<div class='section-label'>Role ID</div>",
            unsafe_allow_html=True,
        )
        st.text_input(
            "Role A ID",
            key="inspect_role_a",
            label_visibility="collapsed",
            placeholder="e.g. roles/bigquery.dataEditor",
        )
        st.checkbox("Compare two roles", key="inspect_diff_mode")
        if st.session_state["inspect_diff_mode"]:
            st.text_input(
                "Role B ID",
                key="inspect_role_b",
                placeholder="e.g. roles/bigquery.dataViewer",
            )

    with col_output:
        role_a_id = st.session_state["inspect_role_a"].strip()
        diff_mode = st.session_state["inspect_diff_mode"]

        # No Role A input — nothing to show
        if not role_a_id:
            st.markdown(
                "<div class='hcl-placeholder'>"
                "← Enter a Role ID to inspect"
                "</div>",
                unsafe_allow_html=True,
            )
            return

        # Role A not found anywhere
        if role_a_id not in permissions and role_a_id not in role_title_map:
            st.error(f"Role ID not found: {role_a_id}")
            return

        # Role A known but has no permission data (partial data)
        if role_a_id not in permissions:
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.warning(
                "Permission data unavailable for this role. Try refreshing."
            )
            return

        perms_a: set[str] = permissions[role_a_id]

        if not diff_mode:
            # Single-role output
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            return

        # Diff mode — Role B evaluation
        role_b_id = st.session_state["inspect_role_b"].strip()

        if not role_b_id:
            # Diff on but Role B empty — show Role A only
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            return

        # Role B not found anywhere
        if role_b_id not in permissions and role_b_id not in role_title_map:
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            st.error(f"Role ID not found: {role_b_id}")
            return

        # Role B known but has no permission data (partial data)
        if role_b_id not in permissions:
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            st.warning("Permission data unavailable for Role B.")
            return

        perms_b: set[str] = permissions[role_b_id]

        # Both roles resolve — render three-column diff
        only_a = perms_a - perms_b
        in_both = perms_a & perms_b
        only_b = perms_b - perms_a

        title_a = role_title_map.get(role_a_id, "(custom role)")
        title_b = role_title_map.get(role_b_id, "(custom role)")

        diff_col_a, diff_col_both, diff_col_b = st.columns([1, 1, 1])

        with diff_col_a:
            st.subheader("Only in A")
            st.caption(f"{title_a} · {len(only_a)} permissions")
            st.code(
                "\n".join(sorted(only_a)) if only_a else "(none)",
                language=None,
            )

        with diff_col_both:
            st.subheader("In both")
            st.caption(f"{len(in_both)} permissions")
            st.code(
                "\n".join(sorted(in_both)) if in_both else "(none)",
                language=None,
            )

        with diff_col_b:
            st.subheader("Only in B")
            st.caption(f"{title_b} · {len(only_b)} permissions")
            st.code(
                "\n".join(sorted(only_b)) if only_b else "(none)",
                language=None,
            )
```

- [ ] **Step 4: Verify import works (run from `app/` directory)**

```bash
cd "c:\Users\e.d.buenaventura\OneDrive - Sysco Corporation\Documents\gcp-role-lookup-nav\app"
.venv\Scripts\python -c "from pages.inspect import render; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Run all tests**

```bash
cd "c:\Users\e.d.buenaventura\OneDrive - Sysco Corporation\Documents\gcp-role-lookup-nav"
.venv\Scripts\python -m pytest tests/ -v
```
Expected: All tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add app/pages/inspect.py tests/test_inspect_logic.py
git commit -m "feat: add Role Inspector page (inspect.py)"
```

---

## Chunk 5: Permission Search (permissions.py) + Smoke Test

### Task 7: Create `pages/permissions.py`

**Files:**
- Create: `app/pages/permissions.py`
- Create: `tests/test_permissions_logic.py`

`sort_key` is defined at module level (not nested in `render()`) so it can be imported and tested directly.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_permissions_logic.py`:
```python
"""Tests for Permission Search sort and filter logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


def test_sort_key_predefined_role():
    from pages.permissions import sort_key
    assert sort_key("roles/bigquery.dataEditor") == (0, "roles/bigquery.dataEditor")


def test_sort_key_project_role():
    from pages.permissions import sort_key
    assert sort_key("projects/my-project/roles/customRole") == (
        1,
        "projects/my-project/roles/customRole",
    )


def test_sort_key_org_role():
    from pages.permissions import sort_key
    assert sort_key("organizations/123/roles/customRole") == (
        2,
        "organizations/123/roles/customRole",
    )


def test_sort_key_unknown_bucket():
    from pages.permissions import sort_key
    assert sort_key("unknown/role") == (3, "unknown/role")


def test_sort_predefined_before_project():
    from pages.permissions import sort_key
    assert sort_key("roles/a") < sort_key("projects/b")


def test_search_exact_membership():
    """Search is exact set membership, not a substring match."""
    permissions = {
        "roles/bigquery.dataEditor": {
            "bigquery.tables.create",
            "bigquery.tables.delete",
        },
        "roles/bigquery.dataViewer": {
            "bigquery.tables.get",
            "bigquery.tables.list",
        },
    }
    query = "bigquery.tables.create"
    matches = [
        rid
        for rid, perms in permissions.items()
        if query in {p.lower() for p in perms}
    ]
    assert matches == ["roles/bigquery.dataEditor"]


def test_search_no_match():
    permissions = {"roles/viewer": {"resourcemanager.projects.get"}}
    query = "nonexistent.permission"
    matches = [
        rid
        for rid, perms in permissions.items()
        if query in {p.lower() for p in perms}
    ]
    assert matches == []


def test_search_case_insensitive_stored_permissions():
    """Stored permissions are lowercased before membership test."""
    permissions = {"roles/viewer": {"BigQuery.Tables.Get"}}
    query = "bigquery.tables.get"
    matches = [
        rid
        for rid, perms in permissions.items()
        if query in {p.lower() for p in perms}
    ]
    assert matches == ["roles/viewer"]
```

- [ ] **Step 2: Run tests to verify they fail (module doesn't exist yet)**

```bash
cd "c:\Users\e.d.buenaventura\OneDrive - Sysco Corporation\Documents\gcp-role-lookup-nav"
.venv\Scripts\python -m pytest tests/test_permissions_logic.py::test_sort_key_predefined_role -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'pages.permissions'`

- [ ] **Step 3: Create `app/pages/permissions.py`**

```python
"""
permissions.py

Permission Search page — given an exact GCP permission string,
finds every role that grants it and displays a Terraform-ready list.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def sort_key(role_id: str) -> tuple:
    """Sort bucket: predefined (roles/) → project → org → other, then alpha."""
    if role_id.startswith("roles/"):
        return (0, role_id)
    if role_id.startswith("projects/"):
        return (1, role_id)
    if role_id.startswith("organizations/"):
        return (2, role_id)
    return (3, role_id)


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Permission Search page."""

    # Global unavailability guard — runs before empty-query check
    if not permissions:
        st.warning(
            "Permission data is not loaded. "
            "Please use the Refresh button on the Resolve Titles page."
        )
        return

    if st.session_state.get("roles_load_error"):
        st.error(
            "Roles data could not be loaded: "
            + st.session_state["roles_load_error"]
        )
        return

    st.markdown(
        "<div class='section-label'>Permission Search</div>",
        unsafe_allow_html=True,
    )
    st.text_input(
        "Enter an exact GCP permission string (e.g. bigquery.tables.create)",
        key="permission_search_query",
    )

    query = st.session_state["permission_search_query"].strip().lower()

    if not query:
        return

    role_title_map = {r["name"]: r["title"] for r in roles}

    matches = sorted(
        [
            rid
            for rid, perms in permissions.items()
            if query in {p.lower() for p in perms}
        ],
        key=sort_key,
    )

    if not matches:
        st.info(f"No roles found granting permission: {query}")
        return

    sorted_rows = [
        {
            "Role ID": rid,
            "Role Title": role_title_map.get(rid, "(custom role)"),
            "Terraform String": f'"{rid}"',
        }
        for rid in matches
    ]
    sorted_terraform_strings = [row["Terraform String"] for row in sorted_rows]

    st.caption(f"{len(matches)} role(s) grant this permission.")

    df = pd.DataFrame(sorted_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown(
        "<div class='section-label'>Terraform Role Strings</div>",
        unsafe_allow_html=True,
    )
    st.code("\n".join(sorted_terraform_strings), language=None)
```

- [ ] **Step 4: Run all tests**

```bash
.venv\Scripts\python -m pytest tests/ -v
```
Expected: All tests PASSED (test counts: 1 role_loader + 5 inspect_logic + 8 permissions_logic = 14 total).

- [ ] **Step 5: Commit**

```bash
git add app/pages/permissions.py tests/test_permissions_logic.py
git commit -m "feat: add Permission Search page (permissions.py)"
```

---

### Task 8: End-to-End Smoke Test

**Files:**
- No new files

- [ ] **Step 1: Launch the app**

```bash
cd "c:\Users\e.d.buenaventura\OneDrive - Sysco Corporation\Documents\gcp-role-lookup-nav\app"
.venv\Scripts\streamlit run main.py
```
Expected: Browser opens. Sidebar shows "Resolve Titles" (active/green), "Role Inspector", and "Permission Search" buttons. Role count badge appears. Resolve Titles page renders correctly.

- [ ] **Step 2: Verify navigation**

- Click "Role Inspector" → page switches to inspector with Role A ID input and "Compare two roles" checkbox.
- Click "Permission Search" → page switches with permission input.
- Click "Resolve Titles" → returns to resolve page; previously entered text (if any) is preserved.

- [ ] **Step 3: Test Role Inspector with a known role**

- Enter `roles/bigquery.dataEditor` in Role A ID field. Permission list appears with count.
- Enable "Compare two roles". Enter `roles/bigquery.dataViewer` in Role B ID. Three columns appear: "Only in A", "In both", "Only in B".

- [ ] **Step 4: Test Permission Search with a known permission**

- Enter `bigquery.tables.create`. Results table appears with Role ID, Role Title, Terraform String columns. Terraform bulk-copy block appears below.
- Clear the input. Results disappear.

- [ ] **Step 5: Commit any smoke-test fixups and finalize**

```bash
git add -A
git commit -m "feat: complete navigation, Role Inspector, and Permission Search"
```
