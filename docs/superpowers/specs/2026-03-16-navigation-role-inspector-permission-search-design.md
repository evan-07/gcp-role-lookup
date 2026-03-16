# Design: Sidebar Navigation + Role Inspector + Permission Search

**Date:** 2026-03-16
**Status:** Approved

---

## Overview

Adds two new modes to the GCP Role Lookup Streamlit app — **Role Inspector** and **Permission Search** — behind a sidebar navigation system. The existing "Resolve Titles" mode is preserved without functional changes.

---

## Architecture

### Navigation System

- `st.session_state["page"]` tracks the active mode. Valid values: `"resolve"`, `"inspect"`, `"permissions"`. Default: `"resolve"`.
- All session state keys are initialized in `main.py` using `if "key" not in st.session_state` guards to avoid overwriting user input on reruns.
- Nav buttons use this pattern in the main script body (not `on_click` callbacks):
  ```python
  if st.sidebar.button("Resolve Titles", type="primary" if page == "resolve" else "secondary"):
      st.session_state["page"] = "resolve"
      st.rerun()
  ```
  `st.rerun()` is called in the main script body immediately after setting session state.

### `main.py` Responsibilities

`main.py` is the Streamlit entry point. It executes in this order:

1. `sys.path.insert(0, str(Path(__file__).parent.parent))` — inserts the repo root so `from app.X import` works from any file.
2. `st.set_page_config()` — first Streamlit call.
3. Global CSS block via `st.markdown(unsafe_allow_html=True)` — shared styles, runs on every page.
4. Session state initialization (all keys, guarded with `if "key" not in st.session_state`).
5. Load data:
   ```python
   try:
       roles_data = get_roles()
       st.session_state["roles_load_error"] = None   # clear any prior error on success
   except (FileNotFoundError, ValueError) as exc:
       roles_data = []
       st.session_state["roles_load_error"] = str(exc)

   try:
       permissions_data = get_permissions()
   except Exception as exc:
       logger.warning("Unexpected error loading permissions: %s", exc)
       permissions_data = {}
   ```
   `get_permissions()` returns `{}` silently for missing files and never raises in normal operation. The `except Exception` wrapper is defensive; if it fires, the error is logged but not shown to the user (permissions simply become unavailable).
6. Render sidebar brand header ("🔐 GCP Role Lookup" title and subtitle, lines 160–171 of current `main.py`).
7. Call `st.sidebar.divider()` once — between the brand header and the nav buttons.
8. Render sidebar nav buttons.
9. Dispatch to active page's `render(roles_data, permissions_data)`. All pages receive `roles_data` even if it is `[]` due to a load error. `inspect.py` and `permissions.py` check `if st.session_state.get("roles_load_error"):` at the top of `render()` and display the error with `st.error(...)` before returning early — same pattern as `resolve.py`.

### Cached Loaders (remain in `main.py`, unchanged)

```python
@st.cache_data(show_spinner=False)
def get_roles() -> list[dict]:
    return load_roles()   # raises FileNotFoundError or ValueError on failure

@st.cache_data(show_spinner=False)
def get_permissions() -> dict[str, set[str]]:
    return load_permissions()   # returns {} silently if file is missing; never raises
```

### New File Structure

```
app/
├── main.py              # Entry point (unchanged responsibilities + new nav/dispatch)
├── pages/
│   ├── __init__.py      # Empty; makes pages/ a Python package
│   ├── resolve.py       # Existing "Resolve Titles" logic extracted from main.py
│   ├── inspect.py       # New: Role Inspector
│   └── permissions.py   # New: Permission Search
├── matcher.py           # Unchanged
├── formatter.py         # Unchanged
├── role_loader.py       # clear_all_caches() added; all other functions unchanged
└── supersession.py      # Unchanged
```

### Import Convention

Two `sys.path` entries are active when the app runs:
- **Repo root** (inserted by `main.py`): enables `from app.X import ...` for all modules under `app/`.
- **`app/` directory** (added by Python when running `streamlit run main.py` from `app/`): enables `from pages.X import ...` for modules under `app/pages/`.

These two entries are non-overlapping. All imports in `pages/` files use:
- `from app.role_loader import ...` — for existing `app/` modules
- `from pages.X import ...` — NOT needed within pages; pages import from `app.*` only

**Launch command:** `streamlit run main.py` executed from within the `app/` directory.

### Cache Invalidation

`clear_all_caches()` is added to `role_loader.py`. Since `get_roles` and `get_permissions` remain in `main.py` and cannot be referenced from `role_loader.py`, it uses the global form `st.cache_data.clear()`. This is a deliberate change from the current per-function `.clear()` calls. It is acceptable because there are only two caches in the app and the effect is identical.

```python
# In role_loader.py:
def clear_all_caches() -> None:
    import streamlit as st
    st.cache_data.clear()
```

`pages/resolve.py` imports it as `from app.role_loader import clear_all_caches`. The refresh flow in `resolve.py` is: call `refresh_roles_from_api()`, then `clear_all_caches()`, then `st.rerun()`. `resolve.py` does **not** re-fetch `roles_data` or `permissions_data` locally — `main.py` handles that on the next rerun. The sidebar success counts displayed after a refresh reflect the data passed in at the start of the current rerun (which is stale); they will update correctly on the subsequent rerun triggered by `st.rerun()`.

### `refresh_roles_from_api`

Already exists in `role_loader.py`. Imported by `resolve.py` as `from app.role_loader import refresh_roles_from_api`. No changes needed to this function.

### Shared Data Types

```python
def render(roles: list[dict], permissions: dict[str, set[str]]) -> None
```

- `roles`: list of dicts with keys `"title"` (str) and `"name"` (str).
- `permissions`: dict mapping role ID → **set** of permission strings. May be `{}` if `role_permissions.json` is unavailable. Pages detect unavailability with `not permissions` (falsy check).

Inside each page's `render()`, the parameter is named `permissions` (not `permissions_data`). The variable `permissions_data` is used only in `main.py` before dispatch.

### Session State Keys (all initialized in `main.py`)

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `"page"` | str | `"resolve"` | Active nav page |
| `"inspect_role_a"` | str | `""` | Role Inspector: Role A input, persisted across nav |
| `"inspect_role_b"` | str | `""` | Role Inspector: Role B input, persisted across nav and diff toggle |
| `"inspect_diff_mode"` | bool | `False` | Role Inspector: diff checkbox state |
| `"permission_search_query"` | str | `""` | Permission Search: search input, persisted across nav |
| `"roles_load_error"` | str or None | `None` | Set to exception message if `get_roles()` failed |
| `"resolve_input"` | str | `""` | Resolve Titles: text area input, persisted across nav |

---

## Page 1: Resolve Titles (refactored, no functional changes)

The existing `main.py` sidebar/main-panel logic moves into `pages/resolve.py` as a `render(roles, permissions)` function.

- All current features remain: fuzzy matching, Terraform HCL output, supersession detection, review table, stat badges.
- Uses the `permissions` argument for supersession detection (passed to `check_supersessions()`). Does not re-load data internally.
- The text area uses `key="resolve_input"` for session state persistence across page navigation.
- The `app-header` block (currently lines 234–247 of `main.py`) moves into `resolve.py` — it is Resolve Titles-specific. Other pages render their own headers if needed.
- Imports: `from app.role_loader import refresh_roles_from_api, clear_all_caches`
- Sidebar: the first sidebar call in `resolve.py`'s `render()` is `st.sidebar.divider()`, then all existing sidebar controls including section labels ("Data Source", "Live Refresh"), the ADC caption, role count badge, permission status badge, refresh button, and match threshold legend — all preserved as-is from `main.py`.
- Refresh button flow (preserves the spinner and success message from the current implementation):
  ```python
  with st.spinner("Calling GCP IAM API…"):
      success, msg = refresh_roles_from_api()
  if success:
      st.success(msg)
      clear_all_caches()
      st.rerun()
  else:
      st.error(msg)
  ```
  Sidebar stat counts are stale for the one rerun cycle after a successful refresh and update automatically on the next run — no additional intermediate message is needed.
- Check `if st.session_state.get("roles_load_error"):` (truthy check). If true, display the error message in the main panel and return early.
- No user-facing changes when data loads successfully.

---

## Page 2: Role Inspector

**Purpose:** Given a GCP role ID, show its title and full permission list. Optionally diff two roles side-by-side.

### Layout

```python
col_input, col_output = st.columns([1, 2], gap="large")
```

Left panel (`col_input`): input controls. Right panel (`col_output`): output.

### Sidebar

`inspect.py` has no sidebar controls and does **not** call `st.sidebar.divider()`. The divider rendered by `main.py` between the nav buttons and the page content is sufficient.

### Input Binding

Uses `key=` parameter for all widgets (Streamlit-managed session state):

```python
st.text_input("Role ID", key="inspect_role_a")
st.checkbox("Compare two roles", key="inspect_diff_mode")
st.text_input("Role B ID", key="inspect_role_b")  # only when inspect_diff_mode is True
```

### Lookup Trigger

Results computed on every rerun when Role A input is non-empty. No submit button, no debouncing.

### Data Lookups

`role_title_map = {r["name"]: r["title"] for r in roles}`

A role **resolves** if its ID is a key in `permissions`. `role_title_map` is used only for title display.

### Global Unavailability Check

If `not permissions` (empty dict): show `st.warning("Permission data is not loaded. Please use the Refresh button on the Resolve Titles page.")` and return immediately. This check runs before any role-specific lookup. The per-role "partial data" edge cases below only apply when `permissions` is non-empty but does not contain the specific role ID.

### Input Normalization

All role ID inputs are stripped of leading/trailing whitespace before lookups: `role_a_id = st.session_state["inspect_role_a"].strip()`. Use the stripped value in both lookups and error messages.

### Single Role Mode Output

```python
st.subheader(role_title_map.get(role_a_id, "(custom role)"))
st.caption(f"{len(perms)} permissions")
st.code("\n".join(sorted(perms)), language=None)
```

### Diff Mode

When `inspect_diff_mode` is True and both roles resolve:
- `st.columns([1,1,1])` with:
  - Column 1: "Only in A" — `perms_a - perms_b`
  - Column 2: "In both" — `perms_a & perms_b`
  - Column 3: "Only in B" — `perms_b - perms_a`
- Each column: count as subheader + `st.code("\n".join(sorted(col_perms)) if col_perms else "(none)", language=None)`

**Role A is always the primary input. Role B is never shown independently.** If Role A is empty, no output is rendered regardless of Role B's value. This asymmetry is intentional.

### Edge Cases

| Condition | Behavior |
|-----------|----------|
| `not permissions` | `st.warning(...)` — no lookup attempted |
| Role A empty | No output rendered |
| Role A empty, Role B filled, diff on | No output rendered |
| Role A non-empty, not in `permissions` AND not in `role_title_map` (single-role or diff mode) | `st.error(f"Role ID not found: {role_a_id}")` — short-circuit, no further output |
| Role A not in `permissions` but IS in `role_title_map` (partial data, permissions non-empty) | Show title + `st.warning("Permission data unavailable for this role. Try refreshing.")` |
| Diff on, Role A not in `permissions` but IS in `role_title_map` (partial data) | Show title + warning for Role A; short-circuit — do not evaluate Role B; no diff columns |
| Role A in `permissions`, not in `role_title_map` | Show `"(custom role)"` as title, then permission list |
| Diff on, Role B empty | Single-role output for Role A only |
| Diff on, Role A resolves, Role B not in `permissions` and not in `role_title_map` | Single-role output for Role A + `st.error("Role ID not found: <Role B id>")` below; no diff columns |
| Diff on, Role A resolves, Role B not in `permissions` but IS in `role_title_map` | Single-role output for Role A + `st.warning("Permission data unavailable for Role B.")` below; no diff columns |

---

## Page 3: Permission Search

**Purpose:** Given an exact permission string, find every GCP role that grants it.

### Layout

- Single search input at top
- Results rendered only when input is non-empty

### Sidebar

`permissions.py` has no sidebar controls and does **not** call `st.sidebar.divider()`.

### Input Binding

```python
st.text_input("Permission", key="permission_search_query")
```

### Lookup Trigger

The `not permissions` check runs unconditionally at the top of `render()`, before checking if the query is non-empty. If permissions are unavailable, the warning is shown regardless of query state. Results are only rendered when the query is non-empty AND permissions are available.

### Search Logic

The search is an **exact set-membership check** — it answers "is this permission string a member of this role's permission set?" not a substring search. GCP permission strings are lowercase by convention (e.g. `bigquery.tables.create`). Both query and stored strings are lowercased before the membership test as a safety measure.

```python
query = st.session_state["permission_search_query"].strip().lower()
role_title_map = {r["name"]: r["title"] for r in roles}

def sort_key(role_id):
    if role_id.startswith("roles/"): return (0, role_id)
    if role_id.startswith("projects/"): return (1, role_id)
    if role_id.startswith("organizations/"): return (2, role_id)
    return (3, role_id)

matches = sorted(
    [rid for rid, perms in permissions.items() if query in {p.lower() for p in perms}],  # set membership, not substring
    key=sort_key
)

sorted_rows = [
    {
        "Role ID": rid,
        "Role Title": role_title_map.get(rid, "(custom role)"),
        "Terraform String": f'"{rid}"',
    }
    for rid in matches
]
sorted_terraform_strings = [row["Terraform String"] for row in sorted_rows]
```

The same `sorted_rows` list is used for the dataframe. `sorted_terraform_strings` is used for the `st.code()` bulk-copy block below the table.

### Output Table

`st.dataframe(df, use_container_width=True)` with columns:

| Column | Cell value | Notes |
|--------|-----------|-------|
| Role ID | `roles/bigquery.dataEditor` (no quotes) | |
| Role Title | `BigQuery Data Editor` or `(custom role)` | |
| Terraform String | `"roles/bigquery.dataEditor"` (literal double-quote chars in string) | |

The dataframe is rendered with default Streamlit interactivity (sortable columns). The spec's defined sort order is the **initial** sort; users may re-sort via column headers. This is acceptable behavior.

A `st.code()` block below the table:
```python
st.code("\n".join(sorted_terraform_strings), language=None)
```
Shows a Terraform-ready list for bulk copy. The initial order of this block follows the spec's defined sort order (not affected by user column sorting).

### Sort Order (for initial render and bulk-copy block)

Applied via `str.startswith()`, alphabetical within each bucket:

1. `"roles/"` — e.g. `roles/bigquery.dataEditor`
2. `"projects/"` — e.g. `projects/my-project/roles/customRole`
3. `"organizations/"` — e.g. `organizations/123456789/roles/customRole`
4. All other — alphabetical, placed last

### Edge Cases

| Condition | Behavior |
|-----------|----------|
| `not permissions` | `st.warning("Permission data is not loaded. Please use the Refresh button on the Resolve Titles page.")` |
| No roles match | `st.info(f"No roles found granting permission: {query}")` where `query` is the stripped, lowercased search term |
| Role ID in `permissions` but not in `role_title_map` | `"(custom role)"` in Role Title column |

---

## Sidebar Navigation Design

```
┌─────────────────────────┐
│  🔐 GCP Role Lookup      │  ← brand header (main.py, preserved)
│  IAM Role Title → ID     │
│  ─────────────────────  │  ← st.sidebar.divider() in main.py
│  [Resolve Titles]   ←   │  type="primary" (active)
│  [Role Inspector]        │  type="secondary"
│  [Permission Search]     │  type="secondary"
│  ─────────────────────  │  ← st.sidebar.divider() in resolve.py only
│  (Resolve Titles:        │
│   data source controls,  │
│   refresh button, legend)│
│                          │
│  (inspect/permissions:   │
│   no sidebar content)    │
└─────────────────────────┘
```

`main.py` renders: brand header → `st.sidebar.divider()` → nav buttons.
`resolve.py` renders: `st.sidebar.divider()` → sidebar controls.
`inspect.py` and `permissions.py`: no sidebar calls at all (no divider, no controls). This means no visual separator appears below the nav buttons on those pages — intentional.

---

## Implementation Notes

- Use a **git worktree** before any code changes.
- Only `role_loader.py` is modified among existing modules (adding `clear_all_caches()`). The `clear_all_caches()` definition is **deleted** from `main.py`, along with any call sites in `main.py` (the existing refresh button block moves to `resolve.py`). It must not exist in both files.
- `matcher.py`, `formatter.py`, `supersession.py` are unchanged.
- All session state keys use `if "key" not in st.session_state` guards.
- `st.code()` blocks use `language=None` (no syntax highlighting) and newline-separated content.
- `st.cache_data.clear()` clears caches for all active server sessions — same behavior as the current implementation. This is intentional and acceptable.

---

## Out of Scope

- Output format options (JSON, YAML, Pulumi)
- Workflow integration with Terraform files
- Mobile/responsive layout improvements
