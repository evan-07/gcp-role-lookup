# Permission Search Enhancement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Permission Search with substring matching — exact matches shown first in their own section, partial (substring) matches shown below, with a 3-character minimum and 100-row cap.

**Architecture:** Extract two pure module-level functions (`find_exact_matches`, `find_partial_matches`) from the existing inline logic in `render()`, then update `render()` to call them and display both result sections. All changes isolated to `app/page_views/permissions.py` and `tests/test_permissions_logic.py`.

**Tech Stack:** Streamlit 1.55.0, pandas 2.3.3, pytest 8.3.4.

---

## Chunk 1: Pure search functions + tests

### Task 1: Add find_exact_matches() and find_partial_matches() with tests

**Files:**
- Modify: `app/page_views/permissions.py` (add two functions after `sort_key`)
- Modify: `tests/test_permissions_logic.py` (append 8 new tests)

**Context:** The existing test file adds `app/` to `sys.path` and imports via `from page_views.permissions import ...`. Follow that same pattern for new tests.

- [ ] **Step 1: Write the 8 failing tests**

Append to `tests/test_permissions_logic.py`:

```python
def test_find_exact_matches_hit():
    from page_views.permissions import find_exact_matches
    perms = {
        "roles/bigquery.dataEditor": {"bigquery.tables.create", "bigquery.tables.delete"},
        "roles/bigquery.dataViewer": {"bigquery.tables.get"},
    }
    assert find_exact_matches("bigquery.tables.create", perms) == ["roles/bigquery.dataEditor"]


def test_find_exact_matches_miss():
    from page_views.permissions import find_exact_matches
    perms = {"roles/viewer": {"resourcemanager.projects.get"}}
    assert find_exact_matches("nonexistent.permission", perms) == []


def test_find_exact_matches_case_insensitive():
    from page_views.permissions import find_exact_matches
    perms = {"roles/viewer": {"BigQuery.Tables.Get"}}
    assert find_exact_matches("bigquery.tables.get", perms) == ["roles/viewer"]


def test_find_partial_matches_substring():
    from page_views.permissions import find_partial_matches
    perms = {
        "roles/a": {"bigquery.tables.create", "bigquery.tables.delete"},
        "roles/b": {"bigquery.tables.get"},
    }
    rows, total = find_partial_matches("bigquery", perms)
    perm_names = [r[0] for r in rows]
    assert "bigquery.tables.create" in perm_names
    assert "bigquery.tables.delete" in perm_names
    assert "bigquery.tables.get" in perm_names
    assert total == 3


def test_find_partial_matches_excludes_exact():
    from page_views.permissions import find_partial_matches
    perms = {"roles/a": {"bigquery.tables.create"}}
    rows, total = find_partial_matches("bigquery.tables.create", perms)
    assert rows == []
    assert total == 0


def test_find_partial_matches_sorted_by_role_count():
    from page_views.permissions import find_partial_matches
    perms = {
        "roles/a": {"bigquery.tables.create", "bigquery.tables.get"},
        "roles/b": {"bigquery.tables.create"},
    }
    rows, _ = find_partial_matches("bigquery", perms)
    # bigquery.tables.create appears in 2 roles, bigquery.tables.get in 1
    assert rows[0] == ("bigquery.tables.create", 2)
    assert rows[1] == ("bigquery.tables.get", 1)


def test_find_partial_matches_limit():
    from page_views.permissions import find_partial_matches
    # Build 5 distinct permissions all containing "svc"
    perms = {"roles/x": {f"svc.resource.action{i}" for i in range(5)}}
    rows, total = find_partial_matches("svc", perms, limit=3)
    assert len(rows) == 3
    assert total == 5


def test_find_partial_matches_empty():
    from page_views.permissions import find_partial_matches
    perms = {"roles/viewer": {"resourcemanager.projects.get"}}
    rows, total = find_partial_matches("zzznomatch", perms)
    assert rows == []
    assert total == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "c:/Users/e.d.buenaventura/OneDrive - Sysco Corporation/Documents/gcp-role-lookup"
.venv/Scripts/python -m pytest tests/test_permissions_logic.py::test_find_exact_matches_hit -v
```

Expected: `FAILED` — `ImportError: cannot import name 'find_exact_matches'`

- [ ] **Step 3: Add find_exact_matches() and find_partial_matches() to permissions.py**

Insert after `sort_key()` (after line 24, before `def render`):

```python
def find_exact_matches(
    query: str, permissions: dict[str, set[str]]
) -> list[str]:
    """Return sorted role IDs whose permission set contains query exactly (case-insensitive)."""
    q = query.lower()
    return sorted(
        [rid for rid, perms in permissions.items() if q in {p.lower() for p in perms}],
        key=sort_key,
    )


def find_partial_matches(
    query: str, permissions: dict[str, set[str]], limit: int = 100
) -> tuple[list[tuple[str, int]], int]:
    """Return (rows, total_count) for permission strings containing query as substring.

    Excludes exact match. Rows are (permission_string, role_count) sorted by
    role_count descending then alphabetically, capped at limit.
    All permission strings are lowercased (case variants merged).
    """
    q = query.lower()
    counts: dict[str, int] = {}
    for perms in permissions.values():
        for p in perms:
            pl = p.lower()
            if q in pl and pl != q:
                counts[pl] = counts.get(pl, 0) + 1
    results = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return results[:limit], len(counts)
```

- [ ] **Step 4: Run all 8 new tests**

```bash
.venv/Scripts/python -m pytest tests/test_permissions_logic.py -v
```

Expected: all 16 tests PASS (8 original + 8 new)

- [ ] **Step 5: Commit**

```bash
git add app/page_views/permissions.py tests/test_permissions_logic.py
git commit -m "feat: add find_exact_matches() and find_partial_matches() to permissions.py"
```

---

## Chunk 2: Update render() to use new functions and display both sections

### Task 2: Rewrite render() search logic and output

**Files:**
- Modify: `app/page_views/permissions.py` (render function body only)

**Context:** The current `render()` has inline search logic (lines 61–94). Replace it with calls to the new functions and a two-section display. The guards at the top (lines 31–43) and the text input (lines 45–52) stay unchanged.

- [ ] **Step 1: Replace the search and display block**

Current block to replace (lines 54–94):

```python
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

    import pandas as pd
    df = pd.DataFrame(sorted_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown(
        "<div class='section-label'>Terraform Role Strings</div>",
        unsafe_allow_html=True,
    )
    st.code("\n".join(sorted_terraform_strings), language=None)
```

Replace with:

```python
    query = st.session_state["permission_search_query"].strip().lower()

    if not query:
        return

    if len(query) < 3:
        st.info("Enter at least 3 characters to search.")
        return

    role_title_map = {r["name"]: r["title"] for r in roles}
    exact_matches = find_exact_matches(query, permissions)
    partial_rows, partial_total = find_partial_matches(query, permissions)

    if not exact_matches and not partial_rows:
        st.info(f"No permissions or roles found for: {query}")
        return

    import pandas as pd

    # --- Exact Matches section ---
    if exact_matches:
        st.markdown(
            "<div class='section-label'>Exact Matches</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{len(exact_matches)} role(s) grant this permission exactly.")
        exact_rows = [
            {
                "Role ID": rid,
                "Role Title": role_title_map.get(rid, "(custom role)"),
                "Terraform String": f'"{rid}"',
            }
            for rid in exact_matches
        ]
        df_exact = pd.DataFrame(exact_rows)
        st.dataframe(df_exact, use_container_width=True, hide_index=True)
        st.markdown(
            "<div class='section-label'>Terraform Role Strings</div>",
            unsafe_allow_html=True,
        )
        st.code("\n".join(row["Terraform String"] for row in exact_rows), language=None)

    # --- Partial Matches section ---
    if partial_rows:
        st.markdown(
            "<div class='section-label'>Partial Matches</div>",
            unsafe_allow_html=True,
        )
        truncation_note = (
            f" Showing first {len(partial_rows)} — refine your query to narrow results."
            if partial_total > len(partial_rows) else ""
        )
        st.caption(
            f"{partial_total} permission string(s) contain '{query}'.{truncation_note}"
        )
        df_partial = pd.DataFrame(
            [{"Permission": perm, "# Roles": count} for perm, count in partial_rows]
        )
        st.dataframe(df_partial, use_container_width=True, hide_index=True)
```

- [ ] **Step 2: Run full test suite**

```bash
.venv/Scripts/python -m pytest tests/ -v
```

Expected: all 19 tests PASS (14 original + 5 existing permissions tests + the 8 new ones — wait, 14 original were from before; now we have 14 + 8 = 22 total)

Actually expected count: 14 existing (inspect + role_loader) + 8 existing permissions tests + 8 new permissions tests = wait, let me recount.

Before this plan: 14 tests total (5 inspect_logic + 8 permissions_logic + 1 role_loader).
After Task 1: 14 + 8 = 22 tests.
After Task 2: still 22 tests (render() changes have no new unit tests).

```bash
.venv/Scripts/python -m pytest tests/ -v
```

Expected: **22 tests PASS**

- [ ] **Step 3: Smoke-test in browser**

```bash
streamlit run app/main.py
```

Verify in the Permission Search page:
- Typing 1-2 characters shows "Enter at least 3 characters to search."
- Typing `bigquery.tables.create` (exact) shows **Exact Matches** section with roles + Terraform block
- Typing `bigquery` (partial) shows **Partial Matches** table with Permission + # Roles columns
- Typing a full permission that also has partial matches (e.g. `bigquery.tables.create`) shows both sections
- Typing a string with no matches shows "No permissions or roles found for: ..."

- [ ] **Step 4: Commit**

```bash
git add app/page_views/permissions.py
git commit -m "feat: add exact and partial match sections to Permission Search"
```
