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
class DeduplicationResult:
    kept: list[str]                          # role IDs to keep
    removed: list[tuple[str, str, str]]      # (role_id, superseded_by_id, superseded_by_title)
    unknown: list[str]                       # role IDs not found in roles data

def deduplicate_role_ids(
    role_ids: list[str],
    permissions: dict[str, set[str]],
    roles: list[dict],
) -> DeduplicationResult:
    ...
```

- Validates each ID exists in `permissions` map
- Runs pairwise strict-subset check (`perms(A) ⊂ perms(B)` → A is superseded)
- Returns a clean `DeduplicationResult` — no `MatchResult` objects involved
- Unknown IDs (not in roles data or permissions map) collected separately

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

**Annotated JSON (`clean=False`):**
```json
[
  "roles/storage.admin",
  // "roles/storage.objectViewer"  // Superseded by Storage Admin
]
```

**Clean JSON (`clean=True`):**
```json
[
  "roles/storage.admin"
]
```

### 3. `app/page_views/deduplicate.py` — page view

Self-contained page view. Imports only from `app.supersession` and `app.formatter`. No dependency on `resolve.py` or `matcher.py`.

Responsibilities:
- Render header, input text area, action buttons
- Validate input lines: strip whitespace, ignore blank lines, warn on non-`roles/` entries
- Call `deduplicate_role_ids()` and store result in session state
- Render stat badges, format toggle (HCL/JSON), annotated/clean radio
- Render "Unknown IDs" warning table when applicable

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
- Dispatch: `from app.page_views.deduplicate import render as render_deduplicate`

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

| Scenario | Behaviour |
|----------|-----------|
| Role ID doesn't start with `roles/` | Collected as unknown, shown in warning table |
| Role ID starts with `roles/` but not in data | Collected as unknown, shown in warning table |
| `permissions_data` is empty | Show inline warning: supersession check disabled |
| All roles supersede each other (circular) | Not possible — strict subset is transitive; the largest role always wins |
| Single role input | Return it as-is (nothing to compare against) |

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
