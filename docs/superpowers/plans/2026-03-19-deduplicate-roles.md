# Deduplicate Roles Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Deduplicate Roles" page that accepts predefined GCP role IDs and returns the minimal set by removing any role whose permissions are a strict subset of another role in the input.

**Architecture:** New logic lives in three places: `supersession.py` gains `deduplicate_role_ids()` with clean dataclasses, `formatter.py` gains two output formatters (HCL + JSON, annotated and clean modes), and a self-contained `page_views/deduplicate.py` wires the UI. `main.py` is updated last to add navigation.

**Tech Stack:** Python 3.12+, Streamlit, pytest. No new dependencies.

---

## Branch Setup

Before any code changes, create and switch to a feature branch:

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
git checkout -b feature/deduplicate-roles
```

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `app/supersession.py` | Modify | Add `RemovedRole`, `DeduplicationResult`, `deduplicate_role_ids()` |
| `app/formatter.py` | Modify | Add `format_dedup_as_hcl()`, `format_dedup_as_json()` |
| `app/page_views/deduplicate.py` | Create | Full self-contained page view |
| `app/main.py` | Modify | Add nav button, session state keys, dispatch case |
| `tests/test_supersession_dedup.py` | Create | Unit tests for `deduplicate_role_ids()` |
| `tests/test_formatter_dedup.py` | Create | Unit tests for the two formatter functions |

---

## Chunk 1: Logic Layer — `deduplicate_role_ids()`

Add dataclasses and the deduplication function to `app/supersession.py`. Tests first.

### Task 1: Create test file with failing tests for `deduplicate_role_ids()`

**Files:**
- Create: `tests/test_supersession_dedup.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_supersession_dedup.py` with this content:

```python
"""Tests for deduplicate_role_ids() in supersession.py."""

import pytest

from app.supersession import DeduplicationResult, RemovedRole, deduplicate_role_ids

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROLES = [
    {"name": "roles/storage.admin", "title": "Storage Admin"},
    {"name": "roles/storage.objectViewer", "title": "Storage Object Viewer"},
    {"name": "roles/storage.objectCreator", "title": "Storage Object Creator"},
    {"name": "roles/bigquery.dataEditor", "title": "BigQuery Data Editor"},
    {"name": "roles/bigquery.dataViewer", "title": "BigQuery Data Viewer"},
]

# storage.admin has all perms of objectViewer and more → objectViewer superseded
# bigquery.dataEditor has all perms of dataViewer and more → dataViewer superseded
PERMISSIONS = {
    "roles/storage.admin": {"storage.buckets.create", "storage.objects.create", "storage.objects.get", "storage.objects.list"},
    "roles/storage.objectViewer": {"storage.objects.get", "storage.objects.list"},
    "roles/storage.objectCreator": {"storage.objects.create"},
    "roles/bigquery.dataEditor": {"bigquery.tables.create", "bigquery.tables.delete", "bigquery.tables.get"},
    "roles/bigquery.dataViewer": {"bigquery.tables.get"},
}


# ---------------------------------------------------------------------------
# Basic supersession
# ---------------------------------------------------------------------------

def test_subset_role_is_removed():
    """roles/storage.objectViewer ⊂ roles/storage.admin → objectViewer removed."""
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/storage.objectViewer"],
        PERMISSIONS,
        ROLES,
    )
    assert result.kept == ["roles/storage.admin"]
    assert len(result.removed) == 1
    assert result.removed[0].role_id == "roles/storage.objectViewer"
    assert result.removed[0].superseded_by_id == "roles/storage.admin"
    assert result.unknown == []


def test_removed_role_includes_titles():
    """RemovedRole contains both the superseded title and the superseder title."""
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/storage.objectViewer"],
        PERMISSIONS,
        ROLES,
    )
    removed = result.removed[0]
    assert removed.role_title == "Storage Object Viewer"
    assert removed.superseded_by_title == "Storage Admin"


def test_multiple_supersessions():
    """Two pairs — each smaller role is removed."""
    result = deduplicate_role_ids(
        [
            "roles/storage.admin",
            "roles/storage.objectViewer",
            "roles/bigquery.dataEditor",
            "roles/bigquery.dataViewer",
        ],
        PERMISSIONS,
        ROLES,
    )
    assert set(result.kept) == {"roles/storage.admin", "roles/bigquery.dataEditor"}
    assert len(result.removed) == 2
    assert result.unknown == []


# ---------------------------------------------------------------------------
# No supersession
# ---------------------------------------------------------------------------

def test_disjoint_roles_all_kept():
    """Roles with no permission overlap — all kept."""
    result = deduplicate_role_ids(
        ["roles/storage.objectCreator", "roles/bigquery.dataViewer"],
        PERMISSIONS,
        ROLES,
    )
    assert set(result.kept) == {"roles/storage.objectCreator", "roles/bigquery.dataViewer"}
    assert result.removed == []
    assert result.unknown == []


def test_identical_permissions_both_kept():
    """Two roles with identical permissions — neither is a strict subset, both kept."""
    permissions = {
        "roles/storage.admin": {"storage.objects.get"},
        "roles/storage.objectViewer": {"storage.objects.get"},
    }
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/storage.objectViewer"],
        permissions,
        ROLES,
    )
    assert set(result.kept) == {"roles/storage.admin", "roles/storage.objectViewer"}
    assert result.removed == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_single_role_is_kept():
    """Single input role — nothing to compare, returned as kept."""
    result = deduplicate_role_ids(
        ["roles/storage.admin"],
        PERMISSIONS,
        ROLES,
    )
    assert result.kept == ["roles/storage.admin"]
    assert result.removed == []
    assert result.unknown == []


def test_empty_input():
    """Empty input list — empty result."""
    result = deduplicate_role_ids([], PERMISSIONS, ROLES)
    assert result.kept == []
    assert result.removed == []
    assert result.unknown == []


def test_unknown_role_id():
    """Role ID not in permissions map → collected as unknown."""
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/nonexistent.role"],
        PERMISSIONS,
        ROLES,
    )
    assert result.kept == ["roles/storage.admin"]
    assert result.unknown == ["roles/nonexistent.role"]
    assert result.removed == []


def test_empty_permissions_map():
    """Empty permissions dict — all roles unknown (no data to compare)."""
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/storage.objectViewer"],
        {},
        ROLES,
    )
    assert result.kept == []
    assert result.removed == []
    assert set(result.unknown) == {"roles/storage.admin", "roles/storage.objectViewer"}


def test_all_unknown_roles():
    """All inputs missing from permissions — all collected as unknown."""
    result = deduplicate_role_ids(
        ["roles/fake.one", "roles/fake.two"],
        PERMISSIONS,
        ROLES,
    )
    assert result.kept == []
    assert result.removed == []
    assert set(result.unknown) == {"roles/fake.one", "roles/fake.two"}
```

- [ ] **Step 2: Run tests to confirm they fail (function not yet defined)**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
pytest tests/test_supersession_dedup.py -v
```

Expected: `ImportError` — `cannot import name 'deduplicate_role_ids'`

---

### Task 2: Implement `RemovedRole`, `DeduplicationResult`, and `deduplicate_role_ids()`

**Files:**
- Modify: `app/supersession.py`

- [ ] **Step 1: Add dataclasses and function to `app/supersession.py`**

Append the following to the end of `app/supersession.py` (after the existing `check_supersessions` function):

```python


# ---------------------------------------------------------------------------
# Deduplicate role IDs
# ---------------------------------------------------------------------------

@dataclass
class RemovedRole:
    """A role removed from the minimal set because it is superseded."""

    role_id: str             # e.g. "roles/storage.objectViewer"
    role_title: str          # e.g. "Storage Object Viewer"
    superseded_by_id: str    # e.g. "roles/storage.admin"
    superseded_by_title: str  # e.g. "Storage Admin"


@dataclass
class DeduplicationResult:
    """Result of deduplicating a list of role IDs."""

    kept: list[str]             # Role IDs in the minimal set
    removed: list[RemovedRole]  # Roles eliminated as redundant
    unknown: list[str]          # Role IDs not found in permissions map


def deduplicate_role_ids(
    role_ids: list[str],
    permissions: dict[str, set[str]],
    roles: list[dict],
) -> DeduplicationResult:
    """
    Return the minimal set of role IDs by removing strict-subset roles.

    Receives only pre-validated ``roles/``-prefixed IDs — prefix validation
    is the caller's responsibility. Role IDs not present in ``permissions``
    are collected as unknown and excluded from comparison.

    For every pair (A, B):
      - If perms(A) ⊂ perms(B)  →  A is superseded by B.
      - Roles with identical permissions: neither is a strict subset; both kept.

    Args:
        role_ids:    Pre-validated ``roles/`` prefixed role IDs.
        permissions: Dict mapping role_id → set of permission strings.
        roles:       Full roles list; used to look up titles by role_id.
                     Each dict must have ``"name"`` and ``"title"`` keys.

    Returns:
        DeduplicationResult with kept, removed, and unknown lists.
    """
    if not role_ids:
        return DeduplicationResult(kept=[], removed=[], unknown=[])

    # Build title lookup: role_id → display title
    id_to_title: dict[str, str] = {
        r["name"]: r["title"]
        for r in roles
        if r.get("name") and r.get("title")
    }

    # Split into known (have permissions data) and unknown
    known: list[str] = []
    unknown: list[str] = []
    for role_id in role_ids:
        if role_id in permissions:
            known.append(role_id)
        else:
            unknown.append(role_id)

    if len(known) < 2:
        return DeduplicationResult(kept=known, removed=[], unknown=unknown)

    # Pairwise strict-subset check — O(N²), N is typically small (≤20)
    superseded_ids: set[str] = set()
    removed: list[RemovedRole] = []

    for i, role_a in enumerate(known):
        if role_a in superseded_ids:
            continue
        perms_a = permissions[role_a]

        for j, role_b in enumerate(known):
            if i == j or role_b in superseded_ids:
                continue
            perms_b = permissions[role_b]

            if perms_a < perms_b:  # strict subset
                superseded_ids.add(role_a)
                removed.append(
                    RemovedRole(
                        role_id=role_a,
                        role_title=id_to_title.get(role_a, role_a),
                        superseded_by_id=role_b,
                        superseded_by_title=id_to_title.get(role_b, role_b),
                    )
                )
                logger.info("Deduplicate: %s ⊂ %s", role_a, role_b)
                break  # One superseder is enough per role

    kept = [r for r in known if r not in superseded_ids]
    return DeduplicationResult(kept=kept, removed=removed, unknown=unknown)
```

- [ ] **Step 2: Run tests to confirm they pass**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
pytest tests/test_supersession_dedup.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
git add app/supersession.py tests/test_supersession_dedup.py
git commit -m "feat: add deduplicate_role_ids() to supersession.py"
```

---

## Chunk 2: Formatter Functions

Add `format_dedup_as_hcl()` and `format_dedup_as_json()` to `app/formatter.py`. Tests first.

### Task 3: Create failing formatter tests

**Files:**
- Create: `tests/test_formatter_dedup.py`

- [ ] **Step 1: Write failing formatter tests**

Create `tests/test_formatter_dedup.py`:

```python
"""Tests for format_dedup_as_hcl() and format_dedup_as_json()."""

import json

import pytest

from app.formatter import format_dedup_as_hcl, format_dedup_as_json
from app.supersession import DeduplicationResult, RemovedRole

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RESULT_WITH_REMOVAL = DeduplicationResult(
    kept=["roles/storage.admin"],
    removed=[
        RemovedRole(
            role_id="roles/storage.objectViewer",
            role_title="Storage Object Viewer",
            superseded_by_id="roles/storage.admin",
            superseded_by_title="Storage Admin",
        )
    ],
    unknown=[],
)

RESULT_NO_REMOVAL = DeduplicationResult(
    kept=["roles/storage.admin", "roles/bigquery.dataViewer"],
    removed=[],
    unknown=[],
)

RESULT_EMPTY = DeduplicationResult(kept=[], removed=[], unknown=[])

RESULT_WITH_UNKNOWN = DeduplicationResult(
    kept=["roles/storage.admin"],
    removed=[],
    unknown=["roles/fake.role"],
)


# ---------------------------------------------------------------------------
# format_dedup_as_hcl — annotated mode
# ---------------------------------------------------------------------------

def test_hcl_annotated_kept_role_appears():
    output = format_dedup_as_hcl(RESULT_WITH_REMOVAL, clean=False)
    assert '"roles/storage.admin",' in output


def test_hcl_annotated_removed_role_commented_out():
    output = format_dedup_as_hcl(RESULT_WITH_REMOVAL, clean=False)
    assert '# "roles/storage.objectViewer"' in output


def test_hcl_annotated_removed_role_includes_superseder():
    output = format_dedup_as_hcl(RESULT_WITH_REMOVAL, clean=False)
    assert "Storage Admin" in output


def test_hcl_annotated_no_removal_clean_output():
    output = format_dedup_as_hcl(RESULT_NO_REMOVAL, clean=False)
    assert '"roles/storage.admin",' in output
    assert '"roles/bigquery.dataViewer",' in output
    assert "#" not in output.replace("# Storage Admin", "").replace("# BigQuery Data Viewer", "")


def test_hcl_annotated_empty_result():
    output = format_dedup_as_hcl(RESULT_EMPTY, clean=False)
    assert output == ""


# ---------------------------------------------------------------------------
# format_dedup_as_hcl — clean mode
# ---------------------------------------------------------------------------

def test_hcl_clean_kept_role_appears():
    output = format_dedup_as_hcl(RESULT_WITH_REMOVAL, clean=True)
    assert '"roles/storage.admin",' in output


def test_hcl_clean_no_comments_for_removed():
    output = format_dedup_as_hcl(RESULT_WITH_REMOVAL, clean=True)
    assert "objectViewer" not in output


def test_hcl_clean_empty_result():
    output = format_dedup_as_hcl(RESULT_EMPTY, clean=True)
    assert output == ""


# ---------------------------------------------------------------------------
# format_dedup_as_json — annotated mode
# ---------------------------------------------------------------------------

def test_json_annotated_is_valid_json():
    output = format_dedup_as_json(RESULT_WITH_REMOVAL, clean=False)
    parsed = json.loads(output)
    assert isinstance(parsed, dict)


def test_json_annotated_kept_array():
    output = format_dedup_as_json(RESULT_WITH_REMOVAL, clean=False)
    parsed = json.loads(output)
    assert parsed["kept"] == ["roles/storage.admin"]


def test_json_annotated_superseded_array():
    output = format_dedup_as_json(RESULT_WITH_REMOVAL, clean=False)
    parsed = json.loads(output)
    assert len(parsed["superseded"]) == 1
    entry = parsed["superseded"][0]
    assert entry["role"] == "roles/storage.objectViewer"
    assert entry["superseded_by"] == "roles/storage.admin"
    assert "reason" in entry


def test_json_annotated_no_removal_no_superseded_key():
    output = format_dedup_as_json(RESULT_NO_REMOVAL, clean=False)
    parsed = json.loads(output)
    assert parsed["kept"] == ["roles/storage.admin", "roles/bigquery.dataViewer"]
    assert parsed.get("superseded", []) == []


def test_json_annotated_empty_result():
    output = format_dedup_as_json(RESULT_EMPTY, clean=False)
    parsed = json.loads(output)
    assert parsed["kept"] == []


# ---------------------------------------------------------------------------
# format_dedup_as_json — clean mode
# ---------------------------------------------------------------------------

def test_json_clean_is_plain_array():
    output = format_dedup_as_json(RESULT_WITH_REMOVAL, clean=True)
    parsed = json.loads(output)
    assert isinstance(parsed, list)
    assert parsed == ["roles/storage.admin"]


def test_json_clean_no_removal_returns_full_array():
    output = format_dedup_as_json(RESULT_NO_REMOVAL, clean=True)
    parsed = json.loads(output)
    assert set(parsed) == {"roles/storage.admin", "roles/bigquery.dataViewer"}


def test_json_clean_empty_result():
    output = format_dedup_as_json(RESULT_EMPTY, clean=True)
    parsed = json.loads(output)
    assert parsed == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
pytest tests/test_formatter_dedup.py -v
```

Expected: `ImportError` — `cannot import name 'format_dedup_as_hcl'`

---

### Task 4: Implement formatter functions

**Files:**
- Modify: `app/formatter.py`

- [ ] **Step 1: Add imports and functions to `app/formatter.py`**

First, add `import json` at the top of `app/formatter.py` (after the existing imports). Then append the following to the end of the file:

```python


# ---------------------------------------------------------------------------
# Deduplicate Roles output formatters
# ---------------------------------------------------------------------------

def format_dedup_as_hcl(
    result: "DeduplicationResult",
    clean: bool = False,
) -> str:
    """
    Format a DeduplicationResult as Terraform HCL list entries.

    Annotated mode (clean=False):
        "roles/storage.admin",          # Storage Admin
        # "roles/storage.objectViewer", # [Superseded by Storage Admin]

    Clean mode (clean=True):
        "roles/storage.admin",          # Storage Admin

    Args:
        result: DeduplicationResult from deduplicate_role_ids().
        clean:  If True, omit comments for superseded roles.

    Returns:
        Formatted multi-line string ready to paste into Terraform.
    """
    from app.supersession import DeduplicationResult  # local import avoids circular

    if not result.kept and not result.removed:
        return ""

    # Build title lookup from removed list for annotated comments
    removed_lookup: dict[str, "RemovedRole"] = {r.role_id: r for r in result.removed}

    lines: list[str] = []

    for role_id in result.kept:
        # Title not available from DeduplicationResult — use role_id as fallback
        # The page view passes roles list; formatter receives result only.
        # Titles for kept roles are not stored in DeduplicationResult.
        # Use bare role_id with no title comment to stay self-contained.
        lines.append(f'"{role_id}",')

    if not clean:
        for removed in result.removed:
            lines.append(
                f'# "{removed.role_id}", '
                f"# {removed.role_title} "
                f"[Superseded by {removed.superseded_by_title}]"
            )

    return "\n".join(lines)


def format_dedup_as_json(
    result: "DeduplicationResult",
    clean: bool = False,
) -> str:
    """
    Format a DeduplicationResult as JSON.

    Clean mode (clean=True): plain array of kept role IDs.
    Annotated mode (clean=False): structured object with ``kept`` and
    ``superseded`` arrays so no invalid ``//`` comments are needed.

    Args:
        result: DeduplicationResult from deduplicate_role_ids().
        clean:  If True, return a plain JSON array of kept role IDs.

    Returns:
        JSON string.
    """
    if clean:
        return json.dumps(result.kept, indent=2)

    payload: dict = {"kept": result.kept}
    if result.removed:
        payload["superseded"] = [
            {
                "role": r.role_id,
                "superseded_by": r.superseded_by_id,
                "reason": (
                    f"{r.role_title} is a strict subset of {r.superseded_by_title}"
                ),
            }
            for r in result.removed
        ]
    else:
        payload["superseded"] = []

    return json.dumps(payload, indent=2)
```

Note: `format_dedup_as_hcl` uses only the `role_id` for kept roles (no title) because `DeduplicationResult.kept` is a list of strings. The page can pass a title lookup if desired, but the formatter stays self-contained.

- [ ] **Step 2: Add `import json` at the top of `app/formatter.py` if not already present**

Check line 1-10 of `app/formatter.py`. If `import json` is not there, add it after the docstring.

- [ ] **Step 3: Run formatter tests**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
pytest tests/test_formatter_dedup.py -v
```

Expected: All tests PASS.

- [ ] **Step 4: Run full test suite to check no regressions**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
pytest -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
git add app/formatter.py tests/test_formatter_dedup.py
git commit -m "feat: add format_dedup_as_hcl() and format_dedup_as_json() to formatter.py"
```

---

## Chunk 3: Page View

Create the self-contained `app/page_views/deduplicate.py`. No unit tests for Streamlit UI — validate manually by running the app.

### Task 5: Create `app/page_views/deduplicate.py`

**Files:**
- Create: `app/page_views/deduplicate.py`

- [ ] **Step 1: Create the page view file**

Create `app/page_views/deduplicate.py`:

```python
"""
deduplicate.py

Deduplicate Roles page — accepts predefined GCP role IDs and returns the
minimal set by removing any role whose permissions are a strict subset of
another role in the input (least-privilege deduplication).

Imports only from app.supersession and app.formatter.
No dependency on resolve.py or matcher.py.
"""

import pandas as pd
import streamlit as st

from app.formatter import format_dedup_as_hcl, format_dedup_as_json
from app.supersession import DeduplicationResult, deduplicate_role_ids


def _validate_lines(raw_text: str) -> tuple[list[str], list[str]]:
    """
    Parse textarea input into valid role IDs and invalid lines.

    Args:
        raw_text: Multi-line string from the textarea.

    Returns:
        (valid_ids, invalid_lines) where valid_ids start with "roles/"
        and invalid_lines do not.
    """
    valid: list[str] = []
    invalid: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("roles/"):
            valid.append(stripped)
        else:
            invalid.append(stripped)
    return valid, invalid


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Deduplicate Roles page."""

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
            <h1>Deduplicate Roles</h1>
            <p>Paste predefined GCP role IDs to remove redundant roles.
            Any role whose permissions are fully covered by another role in the
            list is removed, enforcing least privilege.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_input, col_output = st.columns([1, 2], gap="large")

    with col_input:
        st.markdown(
            "<div class='section-label'>Role IDs — one per line</div>",
            unsafe_allow_html=True,
        )
        input_text = st.text_area(
            label="Role IDs Input",
            placeholder=(
                "roles/storage.admin\n"
                "roles/storage.objectViewer\n"
                "roles/bigquery.dataEditor\n"
                "roles/bigquery.dataViewer"
            ),
            label_visibility="collapsed",
            key="deduplicate_input",
            height=300,
        )

        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            deduplicate_clicked = st.button(
                "Deduplicate →",
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
            st.session_state["deduplicate_input"] = ""
            st.session_state["deduplicate_results"] = None
            st.rerun()

    # Run deduplication when button clicked; cache result in session state
    # so format/mode toggles don't re-run the logic.
    pre_validation_unknowns: list[str] = []

    if deduplicate_clicked and input_text.strip() and roles:
        valid_ids, pre_validation_unknowns = _validate_lines(input_text)

        if not permissions:
            # No permissions data — can't deduplicate, store empty result
            result = DeduplicationResult(kept=valid_ids, removed=[], unknown=[])
            st.session_state["deduplicate_pre_unknowns"] = pre_validation_unknowns
            st.session_state["deduplicate_results"] = result
            st.session_state["deduplicate_no_permissions"] = True
        else:
            result = deduplicate_role_ids(valid_ids, permissions, roles)
            st.session_state["deduplicate_pre_unknowns"] = pre_validation_unknowns
            st.session_state["deduplicate_results"] = result
            st.session_state["deduplicate_no_permissions"] = False
    else:
        result = st.session_state.get("deduplicate_results")
        pre_validation_unknowns = st.session_state.get("deduplicate_pre_unknowns", [])

    with col_output:
        fmt = st.session_state.get("deduplicate_output_format", "HCL")
        mode = st.session_state.get("deduplicate_output_mode", "Annotated")
        label = "Terraform HCL Output" if fmt == "HCL" else "JSON Output"
        st.markdown(
            f"<div class='section-label'>{label}</div>",
            unsafe_allow_html=True,
        )

        if result is not None:
            all_unknowns = pre_validation_unknowns + result.unknown
            total_valid = len(result.kept) + len(result.removed)

            st.markdown(
                f"""
                <div class="stat-row">
                  <span class="stat-badge badge-total">{total_valid} inputs</span>
                  <span class="stat-badge badge-exact">✓ {len(result.kept)} kept</span>
                  <span class="stat-badge badge-superseded">⛔ {len(result.removed)} superseded</span>
                  <span class="stat-badge badge-miss">✗ {len(all_unknowns)} unknown</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.session_state.get("deduplicate_no_permissions"):
                st.warning(
                    "⚠️ Permissions data not loaded — supersession check disabled. "
                    "Run `python scripts/refresh_roles.py` to enable it."
                )

            col_fmt, col_mode = st.columns([1, 1])
            with col_fmt:
                st.radio(
                    "Output format",
                    ["HCL", "JSON"],
                    horizontal=True,
                    key="deduplicate_output_format",
                    label_visibility="collapsed",
                )
            with col_mode:
                st.radio(
                    "Output mode",
                    ["Annotated", "Clean"],
                    horizontal=True,
                    key="deduplicate_output_mode",
                    label_visibility="collapsed",
                )

            is_clean = mode == "Clean"
            if fmt == "HCL":
                output = format_dedup_as_hcl(result, clean=is_clean)
                st.code(output if output else "(no roles to display)", language="hcl")
            else:
                output = format_dedup_as_json(result, clean=is_clean)
                st.code(output, language="json")

        elif deduplicate_clicked and not roles:
            st.error(
                "Roles data could not be loaded. "
                "Check the sidebar for details."
            )
        else:
            st.markdown(
                "<div class='hcl-placeholder'>"
                "← Enter role IDs and click Deduplicate"
                "</div>",
                unsafe_allow_html=True,
            )

    # --- Unknown IDs table (full-width, below columns) ---
    if result is not None:
        all_unknowns = pre_validation_unknowns + result.unknown
        if all_unknowns:
            unknown_rows = []
            for uid in pre_validation_unknowns:
                unknown_rows.append({
                    "Role ID": uid,
                    "Reason": "Does not start with roles/ (not a predefined GCP role)",
                })
            for uid in result.unknown:
                unknown_rows.append({
                    "Role ID": uid,
                    "Reason": "Not found in loaded roles data or permissions map",
                })

            with st.expander(
                f"✗ Unknown — {len(all_unknowns)} item(s)",
                expanded=False,
            ):
                df = pd.DataFrame(unknown_rows)
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Role ID": st.column_config.TextColumn(width="medium"),
                        "Reason": st.column_config.TextColumn(width="large"),
                    },
                )
```

- [ ] **Step 2: Verify the file has no import errors**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
python -c "from app.page_views.deduplicate import render; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
git add app/page_views/deduplicate.py
git commit -m "feat: add Deduplicate Roles page view"
```

---

## Chunk 4: Wire Up Navigation

Update `main.py` to register the new page: session state defaults, sidebar button, and dispatch.

### Task 6: Update `main.py`

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add session state defaults**

In `app/main.py`, find the `_DEFAULTS` dict (around line 153). Add these six keys (four for user-facing state, two for internal page flags):

```python
    "deduplicate_input": "",
    "deduplicate_results": None,
    "deduplicate_output_format": "HCL",
    "deduplicate_output_mode": "Annotated",
    "deduplicate_pre_unknowns": [],   # lines that failed prefix validation
    "deduplicate_no_permissions": False,  # flag for missing permissions data
```

The full `_DEFAULTS` dict should look like:

```python
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
    "deduplicate_input": "",
    "deduplicate_results": None,
    "deduplicate_output_format": "HCL",
    "deduplicate_output_mode": "Annotated",
    "deduplicate_pre_unknowns": [],
    "deduplicate_no_permissions": False,
}
```

- [ ] **Step 2: Add sidebar nav button**

In `app/main.py`, find the "Find Smallest Role" button block (around line 247). Add the "Deduplicate Roles" button **after** "Find Smallest Role" and **before** "Help":

```python
    if st.button(
        "Deduplicate Roles",
        type="primary" if page == "deduplicate" else "secondary",
        use_container_width=True,
    ):
        st.session_state["page"] = "deduplicate"
        st.rerun()
```

- [ ] **Step 3: Add dispatch case**

In `app/main.py`, find the dispatch block at the bottom (around line 308). Add the new `elif` case after `find_role` and before `help`:

```python
elif st.session_state["page"] == "deduplicate":
    from app.page_views.deduplicate import render as render_deduplicate
    render_deduplicate(roles_data, permissions_data)
```

- [ ] **Step 4: Verify no import errors and run full test suite**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
python -c "import app.main" 2>&1 | head -5
pytest -v
```

Expected: No import errors. All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
git add app/main.py
git commit -m "feat: wire Deduplicate Roles page into main nav"
```

---

## Final Verification

- [ ] **Manual smoke test**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
streamlit run app/main.py
```

In the browser:
1. Click "Deduplicate Roles" in the sidebar
2. Paste:
   ```
   roles/storage.admin
   roles/storage.objectViewer
   roles/bigquery.dataEditor
   roles/bigquery.dataViewer
   notarole
   ```
3. Click "Deduplicate →"
4. Verify:
   - Stat badges show: `4 inputs · ✓ 2 kept · ⛔ 2 superseded · ✗ 1 unknown`
   - HCL annotated mode: `roles/storage.admin` and `roles/bigquery.dataEditor` active; others commented
   - HCL clean mode: only the two kept roles
   - JSON annotated: structured object with `kept` and `superseded` arrays
   - JSON clean: plain array of 2 role IDs
   - Unknown expander shows `notarole` with "Does not start with roles/" reason
5. Test clear button resets the form

- [ ] **Run full test suite one final time**

```bash
cd "/Users/erivanbuenaventura/VS Code/gcp-role-lookup"
pytest -v
```

Expected: All tests PASS.
