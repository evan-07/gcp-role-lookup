# Architecture

Technical reference for the GCP IAM Lookup application. Covers module responsibilities, data flow, session state design, key implementation decisions, and Streamlit-specific patterns used throughout the codebase.

---

## Table of Contents

- [High-Level Overview](#high-level-overview)
- [Module Responsibilities](#module-responsibilities)
- [Data Flow](#data-flow)
- [Session State Design](#session-state-design)
- [Page Architecture](#page-architecture)
- [Key Design Decisions](#key-design-decisions)
- [Streamlit Patterns](#streamlit-patterns)
- [Testing Strategy](#testing-strategy)
- [Deployment Notes](#deployment-notes)

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│  Streamlit Browser Client                               │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP (port 8501)
┌───────────────────────────▼─────────────────────────────┐
│  app/main.py                                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Global: CSS · session state · data loaders     │   │
│  │  Sidebar: brand · nav buttons · data source     │   │
│  │           status · live refresh button          │   │
│  └──────────────────┬──────────────────────────────┘   │
│                     │ dispatch on st.session_state.page  │
│       ┌──────────────┴───────────────────────────────┐    │
│       │              │              │               │    │
│  resolve.py   inspect.py  permissions.py  find_role.py  │
│                                          deduplicate.py  │
└─────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  Core logic modules                                     │
│  matcher.py · formatter.py · supersession.py            │
│  role_loader.py                                         │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  data/                                                  │
│  gcp_roles.json · role_permissions.json                 │
└─────────────────────────────────────────────────────────┘
```

The app is a single-process Streamlit server. There is no backend API, database, or message queue. All state lives in `st.session_state` within a single browser session. Data is read from local JSON files on startup and cached in memory via `@st.cache_data`.

---

## Module Responsibilities

### `app/main.py`

The Streamlit entry point. Owns everything that must be consistent across all pages:

- `st.set_page_config` — must be the first Streamlit call
- Global CSS injected via `st.markdown(..., unsafe_allow_html=True)`
- `_DEFAULTS` dict and the session state initialisation loop
- `@st.cache_data` wrappers around `load_roles()` and `load_permissions()`
- Data loading with error handling (populates `roles_load_error` in session state)
- Sidebar: brand header, navigation buttons, Data Source status, Live Refresh
- Page dispatch: `if/elif` block routing to each page module's `render()`

**Why all sidebar content lives here:** The sidebar was originally split across `main.py` (nav) and `resolve.py` (data status + refresh). Moving everything to `main.py` ensures the data source status and refresh button are visible regardless of which page is active.

---

### `app/matcher.py`

Fuzzy title-to-ID matching using rapidfuzz. Accepts a raw text block, splits it into lines, and returns a `list[MatchResult]`. Each `MatchResult` carries:

- `input_title` — the raw string the user typed
- `role_id` — the best matching canonical role ID (or `None`)
- `matched_title` — the title of the matched role
- `confidence` — integer 0–100
- `status` — one of `exact / high / medium / low / not_found / empty`
- `suggestions` — list of near-miss candidates for low-confidence results
- `supersession` — populated later by `supersession.py`

Thresholds: ≥85 = High, 60–84 = Medium, <60 = Low.

---

### `app/formatter.py`

Converts results into output strings for two different page flows:

**Resolve Titles flow (`list[MatchResult]`):**
- `format_as_terraform(results)` → multi-line HCL string with inline comments for fuzzy/superseded entries
- `format_results_summary(results)` → dict of status counts (`exact`, `high`, `medium`, `low`, `not_found`, `empty`, `superseded`) used for the stat badges

**Deduplicate Roles flow (`DeduplicationResult`):**
- `format_dedup_as_hcl(result, clean=False)` → HCL with superseded roles commented out (annotated mode) or only kept roles (clean mode)
- `format_dedup_as_json(result, clean=False)` → structured JSON object with `kept`, `superseded`, and `unknown` arrays (annotated mode) or a plain role ID array (clean mode)

---

### `app/supersession.py`

Two distinct functions for detecting role redundancy, serving different page flows:

**`check_supersessions(results, permissions, roles)`** — used by Resolve Titles. Given a resolved `list[MatchResult]` and the permissions map, identifies roles whose permission set is a strict subset of another role in the same batch. Mutates `MatchResult.supersession` in-place.

**`deduplicate_role_ids(role_ids, permissions, roles)`** — used by Deduplicate Roles. Accepts a pre-validated list of `roles/` prefixed role IDs directly (no `MatchResult` objects). Returns a `DeduplicationResult` dataclass with three lists: `kept` (minimal set), `removed` (list of `RemovedRole` with title metadata), and `unknown` (IDs not in the permissions map). Deduplicates inputs and uses the same strict-subset (`<`) check as `check_supersessions`.

**Why subset detection:** If role A's permissions ⊆ role B's permissions, granting both is redundant — role B already covers everything role A provides.

---

### `app/role_loader.py`

- `load_roles()` — reads `data/gcp_roles.json`, returns `list[dict]` with `name` and `title` keys
- `load_permissions()` — reads `data/role_permissions.json`, returns `dict[str, set[str]]`; returns `{}` if the file is missing (graceful degradation)
- `refresh_roles_from_api()` — calls the GCP IAM API, writes updated JSON files, returns `(success, message)`
- `clear_all_caches()` — clears `@st.cache_data` so the next render picks up refreshed data

---

### `app/page_views/deduplicate.py`

Renders the Deduplicate Roles page. Owns:

- `_validate_lines(raw_text)` — pure helper that splits textarea input into valid `roles/`-prefixed IDs and invalid lines (pre-validation unknowns)
- Two-column layout (`col_input` / `col_output`)
- Text area input with Deduplicate and Clear buttons
- Results computation: `_validate_lines` → `deduplicate_role_ids` → cached in `st.session_state["deduplicate_results"]`
- Stat badges (total inputs, kept, superseded, unknown), HCL/JSON format toggle, Annotated/Clean mode toggle
- Code output via `st.code()` (provides built-in copy-to-clipboard)
- Full-width Unknown IDs expander table below the columns, distinguishing pre-validation failures (non-`roles/` prefix) from data-lookup failures (not in permissions map)
- Graceful degradation when `permissions_data` is empty: shows a warning, passes all valid IDs through as-is

Imports only from `app.supersession` and `app.formatter` — no dependency on `resolve.py` or `matcher.py`.

---

### `app/page_views/resolve.py`

Renders the Resolve Titles page. Owns:

- Two-column layout (`col_input` / `col_output`)
- Text area input with Resolve and Clear buttons
- Results computation: `match_titles_bulk` + `check_supersessions`
- Result persistence in `st.session_state["resolve_results"]` (critical — see [Session State Design](#session-state-design))
- Stat badges, HCL/JSON toggle, code output
- Full-width Review Required expander table below the columns

---

### `app/page_views/inspect.py`

Renders the Role Inspector page. Module-level pure functions:

- `group_permissions(perms)` — groups a set of permission strings by service prefix (part before the first `.`), sorts within each group alphabetically, puts `other` last
- `_render_grouped(perms)` — renders grouped permissions as `st.expander` widgets; shows `(none)` for empty sets

The `render()` function uses `st.selectbox` with `format_func` to display `"role/id — Role Title"` while storing only the raw role ID in session state. Stale session state guards (`.get(..., "")`) run before the widget is rendered to prevent `StreamlitAPIException: Value not in options` on first load or after a data refresh.

---

### `app/page_views/permissions.py`

Renders the Permission Search page. Module-level pure functions:

- `sort_key(role_id)` — returns `(tier, role_id)` tuple for consistent role ordering (predefined → project → org → other)
- `find_exact_matches(query, permissions)` — returns sorted role IDs whose permission set contains the query exactly (case-insensitive)
- `find_partial_matches(query, permissions, limit)` — returns `(rows, total_count)` where `rows` is a list of `(permission_string, role_count)` tuples for permission strings that contain the query as a substring, excluding the exact match, sorted by role count descending then alphabetically

3-character minimum enforced before any search runs.

---

### `app/page_views/find_role.py`

Renders the Find Smallest Role page. Module-level pure functions:

- `parse_permissions_input(raw)` — parses multi-line text area input into a `set[str]`; strips whitespace, lowercases, discards blanks and duplicates
- `_tier(role_id)` — returns sort tier: `roles/` = 0, `projects/` = 1, `organizations/` = 2, other = 3
- `find_smallest_roles(required, permissions, role_title_map, partial_limit)` — returns `(exact, partial)` lists of dicts; exact list is sorted by `(tier, total_perms, role_id)`; partial list is sorted by `(-covered, tier, total_perms, role_id)` and capped at `partial_limit`; when exact results exist, partial is always `[]`

---

## Data Flow

### Startup

```
disk: data/gcp_roles.json
      data/role_permissions.json
         │
         ▼
  role_loader.load_roles()        → roles_data: list[dict]
  role_loader.load_permissions()  → permissions_data: dict[str, set[str]]
         │
         ▼ (@st.cache_data — loaded once, held in memory)
  main.py makes both available to all page render() calls
```

### Resolve Titles flow

```
user input (text area)
    │
    ▼
matcher.match_titles_bulk(input_text, roles_data)
    │
    ▼
supersession.check_supersessions(results, permissions_data, roles_data)
    │
    ▼
st.session_state["resolve_results"] = results   ← persisted across reruns
    │
    ├── formatter.format_results_summary(results)  → stat badges
    ├── formatter.format_as_terraform(results)     → HCL output
    └── [r.role_id for r in results if r.role_id]  → JSON output
```

### Permission Search flow

```
user query (text input, ≥3 chars)
    │
    ├── find_exact_matches(query, permissions_data)     → role list
    └── find_partial_matches(query, permissions_data)   → (rows, total)
```

### Find Smallest Role flow

```
user input (text area, one permission per line)
    │
    ▼
parse_permissions_input(raw)  → required: set[str]
    │
    ▼
find_smallest_roles(required, permissions_data, role_title_map)
    │
    ├── exact: list[dict]   (roles where required ⊆ role_perms)
    └── partial: list[dict] (top-N by coverage, only when exact is empty)
```

### Deduplicate Roles flow

```
user input (text area, one role ID per line)
    │
    ▼
_validate_lines(raw_text)
    │
    ├── valid_ids: list[str]           (start with "roles/")
    └── pre_validation_unknowns: list[str]  (anything else)
         │
         ▼
deduplicate_role_ids(valid_ids, permissions_data, roles_data)
    │
    ▼
DeduplicationResult
    ├── kept: list[str]         → minimal role set
    ├── removed: list[RemovedRole]  → superseded roles with title metadata
    └── unknown: list[str]      → roles/ IDs not in permissions map
         │
         ├── format_dedup_as_hcl(result, clean)   → HCL output
         └── format_dedup_as_json(result, clean)  → JSON output
```

---

## Session State Design

All keys are pre-initialised in `_DEFAULTS` in `main.py`. The initialisation loop uses `if key not in st.session_state` so that existing values (from user interaction) are never overwritten on rerun.

| Key | Type | Purpose |
|-----|------|---------|
| `page` | `str` | Active page identifier (`resolve`, `inspect`, `permissions`, `find_role`, `deduplicate`) |
| `resolve_input` | `str` | Persists role title text area content across reruns |
| `resolve_results` | `list[MatchResult] \| None` | Persists resolved results so the HCL/JSON toggle rerun does not re-run matching |
| `resolve_output_format` | `str` | HCL or JSON — bound to the `st.radio` widget key |
| `inspect_role_a` | `str` | Selected role ID for Role A (or `""` for blank) |
| `inspect_role_b` | `str` | Selected role ID for Role B (or `""` for blank) |
| `inspect_diff_mode` | `bool` | Whether the two-role diff is enabled |
| `permission_search_query` | `str` | Bound to the permission search text input |
| `find_role_input` | `str` | Persists the required-permissions text area content |
| `roles_load_error` | `str \| None` | Error message if role data failed to load; `None` on success |
| `deduplicate_input` | `str` | Persists role ID text area content across reruns |
| `deduplicate_results` | `DeduplicationResult \| None` | Persists deduplication result so format/mode toggles do not re-run the logic |
| `deduplicate_output_format` | `str` | HCL or JSON — bound to the format `st.radio` key |
| `deduplicate_output_mode` | `str` | Annotated or Clean — bound to the mode `st.radio` key |
| `deduplicate_pre_unknowns` | `list[str]` | Lines that failed prefix validation (non-`roles/`), stored for the unknown table |
| `deduplicate_no_permissions` | `bool` | `True` when permissions data was missing at deduplication time; controls the inline warning |

**Key pattern — `resolve_results` persistence:** Streamlit reruns the entire script on every widget interaction, including clicking the HCL/JSON radio button. Without persisting results, the output reverts to the placeholder because `resolve_clicked` is `False` on that rerun. Storing results in session state decouples the format toggle from the resolve action.

---

## Page Architecture

Each page follows this structure:

```
render(roles, permissions)
  1. Page header (app-header div with title + description)
  2. Guard checks (permissions empty → st.warning; roles_load_error → st.error)
  3. Main content (inputs, buttons, results)
```

The `render()` function in each module is the only public API. All helper functions are either module-level pure functions (testable without Streamlit) or private (`_`-prefixed) Streamlit rendering helpers.

**Why pure functions at module level:** Streamlit cannot be imported without starting a server, so any logic that imports `st` cannot be unit tested without mocking. Extracting pure logic into module-level functions (e.g. `group_permissions`, `find_exact_matches`, `find_smallest_roles`) keeps them independently testable and importable by the test suite via `sys.path` insertion.

**Why `import pandas as pd` is deferred inside `render()`:** Same reason — pandas is imported lazily inside the function body so the test suite can import the module's pure functions without triggering a full pandas import at module load time. This is a pragmatic pattern for keeping test imports fast and clean.

---

## Key Design Decisions

### Streamlit native multipage vs. session-state navigation

Streamlit 1.x auto-discovers a `pages/` directory adjacent to the entry script and overrides any custom navigation. The page view modules are placed in `app/page_views/` (not `pages/`) to disable this behaviour and retain full control over navigation via `st.session_state["page"]`.

### `st.selectbox` with `format_func` (Role Inspector)

The Role Inspector uses `st.selectbox` with `format_func` rather than storing the display string in the options list. This means `st.session_state["inspect_role_a"]` always holds the raw role ID (or `""`), not a formatted display string. The guard:

```python
if st.session_state.get("inspect_role_a", "") not in role_options:
    st.session_state["inspect_role_a"] = ""
```

prevents `StreamlitAPIException: Value not in options` when session state contains a role ID that is no longer present (e.g. after a data refresh that removed a role).

### Tier-based role sorting (Find Smallest Role, Permission Search)

GCP roles fall into three namespaces:
- `roles/` — Google-managed predefined roles
- `projects/<id>/roles/` — project-scoped custom roles
- `organizations/<id>/roles/` — org-scoped custom roles

Predefined roles are preferred in results because they are stable, well-documented, and broadly available. Custom roles are surfaced after predefined roles of the same size. Within a tier, roles are sorted by total permission count (ascending) to surface the least-privilege option first.

### Partial match suppression (Find Smallest Role)

When at least one role covers all required permissions, the partial list is always empty. This prevents a confusing UI where the user sees both an exact match and a partial match for the same required set.

### Data staleness and `@st.cache_data`

Role and permission data is cached with `@st.cache_data` (no TTL). The cache is invalidated explicitly by `clear_all_caches()` after a live API refresh. There is no automatic background refresh — data freshness is the user's responsibility via the Refresh button.

---

## Streamlit Patterns

### Widget update cycle

Streamlit reruns the entire script on every widget interaction. The implication for radio buttons and toggles:

```python
# Read BEFORE rendering the widget — gets the value from the PREVIOUS run
fmt = st.session_state.get("resolve_output_format", "HCL")

# Render the widget — updates session state for the NEXT run
st.radio("Output format", ["HCL", "JSON"], key="resolve_output_format")

# Use fmt (previous run's value) to decide what to render this run
if fmt == "HCL":
    ...
```

This is intentional and correct per Streamlit's execution model.

### `st.rerun()` after state mutation

Buttons that mutate session state (nav buttons, Clear button) call `st.rerun()` immediately after mutating state so the UI reflects the new state in the same user interaction rather than waiting for the next natural rerun.

### `st.sidebar` ownership

All sidebar content is owned by `main.py`. Page modules do not write to `st.sidebar`. This ensures the sidebar is consistent across all pages and avoids a page module accidentally overwriting sidebar content set by another.

---

## Testing Strategy

Tests live in `tests/` and cover the pure logic functions in each page module plus the role loader. They do not test `render()` functions (which require a running Streamlit context).

Each test file adds `app/` to `sys.path` and imports directly from the page module:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from page_views.find_role import find_smallest_roles
```

Test coverage by module:

| File | What is tested |
|------|---------------|
| `test_inspect_logic.py` | `group_permissions()` — grouping, sorting, edge cases |
| `test_permissions_logic.py` | `sort_key()`, `find_exact_matches()`, `find_partial_matches()` |
| `test_find_role_logic.py` | `parse_permissions_input()`, `_tier()`, `find_smallest_roles()` |
| `test_role_loader.py` | `clear_all_caches()` |
| `test_supersession_dedup.py` | `deduplicate_role_ids()` — supersession, no-supersession, edge cases (empty, single, unknown, identical permissions, duplicate inputs) |
| `test_formatter_dedup.py` | `format_dedup_as_hcl()` and `format_dedup_as_json()` — annotated and clean modes, empty results, unknown passthrough |

All tests are written test-first (failing before implementation). 71 tests total.

---

## Deployment Notes

### Container

The `ContainerFile` builds a minimal Python 3.12-slim image:

- Runs as non-root user `appuser` (UID 1001)
- Copies only `app/` and `data/` — no scripts, tests, or docs
- Does not include the `gcloud` CLI; credentials must be mounted at runtime
- Health check polls `/_stcore/health` every 30 seconds
- Telemetry and CORS disabled via environment variables

### Live refresh inside container

The Refresh from GCP API button calls `refresh_roles_from_api()` which uses `google-api-python-client`. Credentials must be provided at container runtime via volume mount (ADC file) and `GOOGLE_APPLICATION_CREDENTIALS` environment variable. The container itself has no gcloud CLI and cannot run `gcloud auth`.

### Windows development

The `setup_windows.ps1` script handles venv creation and dependency installation. The test runner and Streamlit entrypoint both use `.venv/Scripts/python` and `.venv/Scripts/streamlit` respectively. All file paths in the codebase use `pathlib.Path` to remain cross-platform.
