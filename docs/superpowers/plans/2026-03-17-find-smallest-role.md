# Find Smallest Role Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new "Find Smallest Role" page that accepts a list of required permissions and returns the least-privilege role(s) that grant all of them, with partial coverage fallback when no exact match exists.

**Architecture:** New `app/page_views/find_role.py` with three module-level pure functions (`parse_permissions_input`, `_tier`, `find_smallest_roles`) plus a `render()` entry point. New test file `tests/test_find_role_logic.py` with 16 tests. `app/main.py` gets one new session state key, a fourth nav button, and a dispatch clause.

**Tech Stack:** Streamlit 1.55.0, pandas 2.3.3, pytest 8.3.4.

---

## Chunk 1: Pure functions + tests

### Task 1: Create find_role.py with pure functions and their tests

**Files:**
- Create: `app/page_views/find_role.py`
- Create: `tests/test_find_role_logic.py`

---

- [ ] **Step 1: Create test file with 16 failing tests**

Create `tests/test_find_role_logic.py`:

```python
"""Tests for Find Smallest Role pure logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


# --- parse_permissions_input ---

def test_parse_trims_whitespace():
    from page_views.find_role import parse_permissions_input
    assert parse_permissions_input("  a.b.c  ") == {"a.b.c"}


def test_parse_lowercases():
    from page_views.find_role import parse_permissions_input
    assert parse_permissions_input("BigQuery.Tables.Get") == {"bigquery.tables.get"}


def test_parse_discards_blank_lines():
    from page_views.find_role import parse_permissions_input
    assert parse_permissions_input("a.b\n\n\nc.d") == {"a.b", "c.d"}


def test_parse_deduplicates():
    from page_views.find_role import parse_permissions_input
    assert parse_permissions_input("a.b\na.b") == {"a.b"}


# --- _tier ---

def test_tier_predefined():
    from page_views.find_role import _tier
    assert _tier("roles/bigquery.dataEditor") == 0


def test_tier_project():
    from page_views.find_role import _tier
    assert _tier("projects/my-project/roles/customRole") == 1


def test_tier_org():
    from page_views.find_role import _tier
    assert _tier("organizations/123/roles/customRole") == 2


def test_tier_other():
    from page_views.find_role import _tier
    assert _tier("unknown/role") == 3


# --- find_smallest_roles ---

def test_exact_match_found():
    from page_views.find_role import find_smallest_roles
    perms = {"roles/a": {"x.y.z", "a.b.c"}}
    exact, partial = find_smallest_roles({"x.y.z"}, perms, {})
    assert len(exact) == 1
    assert exact[0]["role_id"] == "roles/a"
    assert exact[0]["covered"] == 1
    assert partial == []


def test_exact_match_sorted_by_size():
    from page_views.find_role import find_smallest_roles
    # Both roles/a and roles/b grant the required perm; roles/a is larger
    perms = {
        "roles/a": {"x.y.z", "extra.a", "extra.b"},   # 3 perms
        "roles/b": {"x.y.z", "extra.c"},               # 2 perms
    }
    exact, _ = find_smallest_roles({"x.y.z"}, perms, {})
    assert exact[0]["role_id"] == "roles/b"  # smaller first


def test_exact_match_tier_before_size():
    from page_views.find_role import find_smallest_roles
    # projects/ role is smaller but roles/ tier ranks first
    perms = {
        "projects/p/roles/small": {"x.y.z"},               # 1 perm, tier 1
        "roles/big": {"x.y.z", "extra.a", "extra.b"},      # 3 perms, tier 0
    }
    exact, _ = find_smallest_roles({"x.y.z"}, perms, {})
    assert exact[0]["role_id"] == "roles/big"  # tier 0 before tier 1


def test_no_exact_returns_partial():
    from page_views.find_role import find_smallest_roles
    perms = {
        "roles/a": {"x.y.z"},           # covers 1 of 2
        "roles/b": {"x.y.z", "a.b.c"},  # covers 2 of 2 — wait, this is exact
    }
    # Use 3 required perms so no role covers all
    perms = {
        "roles/a": {"x.y.z", "a.b.c"},  # covers 2 of 3
        "roles/b": {"x.y.z"},           # covers 1 of 3
    }
    exact, partial = find_smallest_roles({"x.y.z", "a.b.c", "m.n.o"}, perms, {})
    assert exact == []
    assert partial[0]["role_id"] == "roles/a"  # higher coverage first
    assert partial[0]["covered"] == 2


def test_partial_limit():
    from page_views.find_role import find_smallest_roles
    # 15 roles each covering 1 of 2 required perms
    perms = {f"roles/r{i}": {"x.y.z"} for i in range(15)}
    exact, partial = find_smallest_roles({"x.y.z", "a.b.c"}, perms, {}, partial_limit=10)
    assert exact == []
    assert len(partial) == 10


def test_empty_required():
    from page_views.find_role import find_smallest_roles
    perms = {"roles/a": {"x.y.z"}}
    exact, partial = find_smallest_roles(set(), perms, {})
    assert exact == []
    assert partial == []


def test_no_coverage():
    from page_views.find_role import find_smallest_roles
    perms = {"roles/a": {"x.y.z"}}
    exact, partial = find_smallest_roles({"a.b.c"}, perms, {})
    assert exact == []
    assert partial == []


def test_exact_suppresses_partial():
    from page_views.find_role import find_smallest_roles
    perms = {
        "roles/full": {"x.y.z", "a.b.c"},   # exact
        "roles/partial": {"x.y.z"},          # partial
    }
    exact, partial = find_smallest_roles({"x.y.z", "a.b.c"}, perms, {})
    assert len(exact) == 1
    assert partial == []
```

- [ ] **Step 2: Run tests to verify they all fail**

```bash
cd "c:/Users/e.d.buenaventura/OneDrive - Sysco Corporation/Documents/gcp-role-lookup"
.venv/Scripts/python -m pytest tests/test_find_role_logic.py -v
```

Expected: all 16 `FAILED` — `ModuleNotFoundError: No module named 'page_views.find_role'`

- [ ] **Step 3: Create app/page_views/find_role.py with pure functions**

Create `app/page_views/find_role.py`:

```python
"""
find_role.py

Find Smallest Role page — given a list of required GCP permissions,
finds the role(s) that grant all of them with the fewest extra permissions.
Falls back to top partial matches when no exact match exists.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def parse_permissions_input(raw: str) -> set[str]:
    """Parse raw text area input into a set of lowercased permission strings.

    Strips whitespace, lowercases, discards blank lines and duplicates.
    """
    return {line.strip().lower() for line in raw.splitlines() if line.strip()}


def _tier(role_id: str) -> int:
    """Return sort tier for a role ID: predefined=0, project=1, org=2, other=3."""
    if role_id.startswith("roles/"):
        return 0
    if role_id.startswith("projects/"):
        return 1
    if role_id.startswith("organizations/"):
        return 2
    return 3


def find_smallest_roles(
    required: set[str],
    permissions: dict[str, set[str]],
    role_title_map: dict[str, str],
    partial_limit: int = 10,
) -> tuple[list[dict], list[dict]]:
    """Find roles that grant all (or most) of the required permissions.

    Returns (exact_matches, partial_matches) as lists of dicts:
      {"role_id": str, "title": str, "total_perms": int, "covered": int}

    exact_matches: roles where required ⊆ role_perms, sorted by (tier, total_perms, role_id)
    partial_matches: top partial_limit roles by covered count (only when exact is empty),
                     sorted by (-covered, tier, total_perms, role_id)
    """
    if not required:
        return [], []

    exact: list[dict] = []
    partial: list[dict] = []

    for role_id, perms in permissions.items():
        covered = len(required & perms)
        if covered == 0:
            continue
        entry = {
            "role_id": role_id,
            "title": role_title_map.get(role_id, "(custom role)"),
            "total_perms": len(perms),
            "covered": covered,
        }
        if required.issubset(perms):
            exact.append(entry)
        else:
            partial.append(entry)

    exact.sort(key=lambda x: (_tier(x["role_id"]), x["total_perms"], x["role_id"]))

    if exact:
        return exact, []

    partial.sort(key=lambda x: (-x["covered"], _tier(x["role_id"]), x["total_perms"], x["role_id"]))
    return [], partial[:partial_limit]


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Find Smallest Role page."""
    pass  # implemented in Task 2
```

- [ ] **Step 4: Run all 16 tests**

```bash
.venv/Scripts/python -m pytest tests/test_find_role_logic.py -v
```

Expected: all 16 PASS

- [ ] **Step 5: Commit**

```bash
git add app/page_views/find_role.py tests/test_find_role_logic.py
git commit -m "feat: add find_smallest_roles() and helpers to find_role.py"
```

---

## Chunk 2: render() + navigation

### Task 2: Implement render() and wire up navigation

**Files:**
- Modify: `app/page_views/find_role.py` (replace `pass` in `render()`)
- Modify: `app/main.py` (session state key, nav button, dispatch)

---

- [ ] **Step 1: Implement render() in find_role.py**

Replace the `render()` stub (the `pass` line) with the full implementation:

```python
def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Find Smallest Role page."""

    if not permissions:
        st.warning(
            "Permission data is not loaded. "
            "Please use the Refresh button on the Resolve Titles page."
        )
        return

    role_title_map = {r["name"]: r["title"] for r in roles}

    st.markdown(
        "<div class='section-label'>Required Permissions — one per line</div>",
        unsafe_allow_html=True,
    )
    st.text_area(
        "Required permissions",
        placeholder="bigquery.tables.create\nbigquery.tables.delete\nbigquery.datasets.get",
        label_visibility="collapsed",
        key="find_role_input",
    )

    find_clicked = st.button("Find Role →", type="primary")

    if not find_clicked:
        return

    required = parse_permissions_input(st.session_state["find_role_input"])

    if not required:
        st.info("Enter at least one permission to search.")
        return

    exact, partial = find_smallest_roles(required, permissions, role_title_map)

    if not exact and not partial:
        st.info("No roles found granting any of the required permissions.")
        return

    import pandas as pd  # deferred to avoid module-level Streamlit dependency in tests

    if exact:
        st.markdown(
            "<div class='section-label'>Exact Matches</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{len(exact)} role(s) grant all {len(required)} required permissions.")
        df_exact = pd.DataFrame([
            {
                "Role ID": e["role_id"],
                "Title": e["title"],
                "Total Permissions": e["total_perms"],
            }
            for e in exact
        ])
        st.dataframe(df_exact, use_container_width=True, hide_index=True)

    if partial:
        st.markdown(
            "<div class='section-label'>Partial Matches</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"No single role grants all {len(required)} permissions. "
            "Top partial matches:"
        )
        df_partial = pd.DataFrame([
            {
                "Role ID": p["role_id"],
                "Title": p["title"],
                "Covers": f"{p['covered']} / {len(required)}",
                "Total Permissions": p["total_perms"],
            }
            for p in partial
        ])
        st.dataframe(df_partial, use_container_width=True, hide_index=True)
```

- [ ] **Step 2: Update app/main.py — session state key**

Find `_DEFAULTS` (around line 132) and add `"find_role_input"`:

Old:
```python
_DEFAULTS: dict = {
    "page": "resolve",
    "resolve_input": "",
    "inspect_role_a": "",
    "inspect_role_b": "",
    "inspect_diff_mode": False,
    "permission_search_query": "",
    "roles_load_error": None,
}
```

New:
```python
_DEFAULTS: dict = {
    "page": "resolve",
    "resolve_input": "",
    "inspect_role_a": "",
    "inspect_role_b": "",
    "inspect_diff_mode": False,
    "permission_search_query": "",
    "find_role_input": "",
    "roles_load_error": None,
}
```

- [ ] **Step 3: Update app/main.py — nav button**

Find the three existing nav buttons in `with st.sidebar:` (around lines 199–221) and add a fourth:

```python
    if st.button(
        "Find Smallest Role",
        type="primary" if page == "find_role" else "secondary",
        use_container_width=True,
    ):
        st.session_state["page"] = "find_role"
        st.rerun()
```

Add it immediately after the "Permission Search" button block.

- [ ] **Step 4: Update app/main.py — dispatch**

Find the dispatch block at the bottom of `main.py` (around lines 226–234) and add:

```python
elif st.session_state["page"] == "find_role":
    from page_views.find_role import render as render_find_role
    render_find_role(roles_data, permissions_data)
```

- [ ] **Step 5: Run full test suite**

```bash
.venv/Scripts/python -m pytest tests/ -v
```

Expected: **43 tests PASS** (27 from plans A+B+C already implemented + 16 new)

- [ ] **Step 6: Smoke-test in browser**

```bash
streamlit run app/main.py
```

Verify:
- Sidebar shows "Find Smallest Role" as fourth nav button
- Clicking it navigates to the new page
- With no permissions loaded: warning shown
- Entering permissions that no single role grants all of: Partial Matches table appears
- Entering a single well-known permission (e.g. `bigquery.tables.create`): Exact Matches table appears with predefined roles ranked first by total permissions
- Empty input + click: "Enter at least one permission to search."
- Input with only blank lines + click: same

- [ ] **Step 7: Commit**

```bash
git add app/page_views/find_role.py app/main.py
git commit -m "feat: add Find Smallest Role page with nav and dispatch"
```
