# Deduplicate Roles — Design Spec

**Date:** 2026-03-19
**Status:** Approved

---

## Overview

A new Streamlit page — **Deduplicate Roles** — that accepts a list of predefined GCP role IDs and returns the minimal set needed by removing any role whose permissions are a strict subset of another role in the input. This enforces least-privilege by eliminating redundant roles.

Example: `roles/storage.admin` supersedes `roles/storage.objectViewer`, so only `roles/storage.admin` is kept.

---

## Scope

- Input: predefined GCP role IDs only (`roles/` prefix required)
- No title resolution or fuzzy matching — role IDs are taken directly
- Unknown IDs (not in loaded roles data) are flagged but do not block processing
- Custom/project-level roles (e.g. `projects/*/roles/*`) are out of scope

---

## Architecture

Three layers, each with a single clear purpose:

### 1. `app/supersession.py` — new public function

```python
@dataclass
class RemovedRole:
    role_id: str             # e.g. "roles/storage.objectViewer"
    role_title: str          # e.g. "Storage Object Viewer"
    superseded_by_id: str    # e.g. "roles/storage.admin"
    superseded_by_title: str # e.g. "Storage Admin"

@dataclass
class DeduplicationResult:
    kept: list[str]              # role IDs in the minimal set
    removed: list[RemovedRole]   # roles eliminated as redundant
    unknown: list[str]           # role IDs not found in roles data or permissions map

def deduplicate_role_ids(
    role_ids: list[str],
    permissions: dict[str, set[str]],
    roles: list[dict],
) -> DeduplicationResult:
    ...
```

- Receives only pre-validated `roles/` prefixed IDs (validation is the page view's responsibility)
- Builds `id_to_title` lookup using `r["name"]` and `r["title"]` fields from the roles dicts
- Collects IDs missing from `permissions` map into `unknown`
- Runs pairwise strict-subset check (`perms(A) ⊂ perms(B)` → A is superseded); uses Python `set.__lt__` which requires *strict* subset
- Roles with identical permissions: neither is a strict subset of the other, so both are kept
- Returns a clean `DeduplicationResult` — no `MatchResult` objects involved

### 2. `app/formatter.py` — two new functions

```python
def format_dedup_as_hcl(result: DeduplicationResult, clean: bool = False) -> str:
    ...

def format_dedup_as_json(result: DeduplicationResult, clean: bool = False) -> str:
    ...
```

**Annotated HCL (`clean=False`):**
```hcl
"roles/storage.admin",          # Storage Admin
# "roles/storage.objectViewer", # [Superseded by Storage Admin]
```

**Clean HCL (`clean=True`):**
```hcl
"roles/storage.admin",          # Storage Admin
```

**Annotated JSON (`clean=False`):** Returns a structured object (not a plain array) to avoid invalid `//` comments in JSON:
```json
{
  "kept": [
    "roles/storage.admin"
  ],
  "superseded": [
    {
      "role": "roles/storage.objectViewer",
      "superseded_by": "roles/storage.admin",
      "reason": "Storage Object Viewer is a strict subset of Storage Admin"
    }
  ]
}
```

**Clean JSON (`clean=True`):** Returns a plain array — drop-in for Terraform `var.roles`:
```json
[
  "roles/storage.admin"
]
```

### 3. `app/page_views/deduplicate.py` — page view

Self-contained page view. Imports only from `app.supersession` and `app.formatter`. No dependency on `resolve.py` or `matcher.py`.

Signature: `render(roles: list[dict], permissions: dict[str, set[str]]) -> None`

Responsibilities:
- Render header, input text area, action buttons
- **Validate** input lines: strip whitespace, ignore blank lines
  - Lines not starting with `roles/` → collected into a pre-validation unknown list
  - Pre-validated `roles/` IDs are passed to `deduplicate_role_ids()`
  - `deduplicate_role_ids()` itself does not perform this prefix check
- Call `deduplicate_role_ids()` and store `DeduplicationResult` in session state
- Render stat badges, format toggle (HCL/JSON), annotated/clean radio
- Output rendered via `st.code()` (provides built-in copy-to-clipboard button)
- Render "Unknown IDs" warning table (collapsible expander) when applicable

---

## UI Layout

```
┌─ Header ─────────────────────────────────────────────────────┐
│ Deduplicate Roles                                             │
│ Paste GCP role IDs to remove redundant roles...              │
└──────────────────────────────────────────────────────────────┘

┌─ Input (1/3) ──┐  ┌─ Output (2/3) ────────────────────────┐
│ roles/          │  │ [N inputs] [✓ K kept] [⛔ R superseded]│
│ storage.admin   │  │ [✗ U unknown]                          │
│ roles/storage.  │  │                                        │
│ objectViewer    │  │ ○ HCL  ○ JSON    ○ Annotated  ○ Clean  │
│                 │  │                                        │
│ [Deduplicate →] │  │ <code block>                           │
│ [Clear]         │  │                                        │
└─────────────────┘  └────────────────────────────────────────┘

┌─ Unknown IDs (full-width, collapsed) ─────────────────────┐
│ ✗ Unknown — 2 item(s)                                      │
│ role_id | reason                                           │
└────────────────────────────────────────────────────────────┘
```

---

## Session State

New keys added to `_DEFAULTS` in `main.py`:

| Key | Default | Purpose |
|-----|---------|---------|
| `deduplicate_input` | `""` | Persists textarea content |
| `deduplicate_results` | `None` | Cached `DeduplicationResult` |
| `deduplicate_output_format` | `"HCL"` | HCL or JSON toggle |
| `deduplicate_output_mode` | `"Annotated"` | Annotated or Clean toggle |

---

## Navigation

- New sidebar button: **"Deduplicate Roles"** added to `main.py` between "Find Smallest Role" and "Help"
- Page key: `"deduplicate"`
- Dispatch:
  ```python
  elif st.session_state["page"] == "deduplicate":
      from app.page_views.deduplicate import render as render_deduplicate
      render_deduplicate(roles_data, permissions_data)
  ```

---

## Stat Badges

Reuses existing CSS badge classes from `main.py`:

| Badge | Class | Meaning |
|-------|-------|---------|
| N inputs | `badge-total` | Total valid role IDs entered |
| ✓ K kept | `badge-exact` | Roles in minimal set |
| ⛔ R superseded | `badge-superseded` | Roles removed as redundant |
| ✗ U unknown | `badge-miss` | IDs not recognized |

---

## Error Handling

| Scenario | Behaviour | Responsibility |
|----------|-----------|----------------|
| Role ID doesn't start with `roles/` | Collected as unknown, shown in warning table | Page view (pre-validation) |
| Role ID starts with `roles/` but not in permissions data | Collected as unknown by `deduplicate_role_ids()` | `deduplicate_role_ids()` |
| `permissions_data` is empty | Show inline warning: supersession check disabled, all valid IDs returned as-is | Page view |
| Two roles with identical permissions | Neither is a strict subset (`set.__lt__` requires strict), both are kept | `deduplicate_role_ids()` |
| Single role input | Returned as-is in `kept`; nothing to compare against | `deduplicate_role_ids()` |
| Empty input | Empty `DeduplicationResult`, no output rendered | Page view |

---

## Files Changed

| File | Change |
|------|--------|
| `app/supersession.py` | Add `DeduplicationResult` dataclass + `deduplicate_role_ids()` |
| `app/formatter.py` | Add `format_dedup_as_hcl()` + `format_dedup_as_json()` |
| `app/page_views/deduplicate.py` | New file — full page view |
| `app/main.py` | Add nav button, session state keys, dispatch case |

---

## Testing

- Unit tests for `deduplicate_role_ids()` in `tests/test_supersession_dedup.py`:
  - Basic supersession (A ⊂ B → A removed)
  - No supersession (disjoint permissions → all kept)
  - Unknown role IDs
  - Empty input
  - Single role input
  - Permissions data missing
- Unit tests for `format_dedup_as_hcl` / `format_dedup_as_json` in `tests/test_formatter_dedup.py`:
  - Annotated mode includes comments for superseded roles
  - Clean mode excludes comments
