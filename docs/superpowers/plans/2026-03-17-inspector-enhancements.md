# Role Inspector Enhancements Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add searchable role ID selectboxes and collapsible service-grouped permission display to the Role Inspector page.

**Architecture:** All changes are isolated to `app/page_views/inspect.py` and `tests/test_inspect_logic.py`. A module-level `group_permissions()` pure function handles grouping logic (testable independently of Streamlit). A private `_render_grouped()` helper encapsulates the expander rendering pattern used in 6 places throughout the file.

**Tech Stack:** Streamlit 1.55.0 (`st.selectbox` with `format_func`, `st.expander`), pytest 8.3.4.

---

## Chunk 1: group_permissions() helper + tests

### Task 1: Add group_permissions() and its tests

**Files:**
- Modify: `app/page_views/inspect.py` (add helper before `render()`)
- Modify: `tests/test_inspect_logic.py` (append 5 new tests)

- [ ] **Step 1: Write the 5 failing tests**

Append to `tests/test_inspect_logic.py`:

```python
def test_group_permissions_basic():
    from app.page_views.inspect import group_permissions
    result = group_permissions({"bigquery.tables.create", "bigquery.tables.delete"})
    assert result == {"bigquery": ["bigquery.tables.create", "bigquery.tables.delete"]}


def test_group_permissions_multiple_services():
    from app.page_views.inspect import group_permissions
    result = group_permissions({"bigquery.tables.get", "compute.instances.list"})
    assert list(result.keys()) == ["bigquery", "compute"]


def test_group_permissions_no_dot():
    from app.page_views.inspect import group_permissions
    result = group_permissions({"nodotpermission"})
    assert "other" in result
    assert result["other"] == ["nodotpermission"]


def test_group_permissions_other_is_last():
    from app.page_views.inspect import group_permissions
    result = group_permissions({"nodot", "bigquery.tables.get", "compute.instances.list"})
    keys = list(result.keys())
    assert keys[-1] == "other"
    assert keys[0] == "bigquery"
    assert keys[1] == "compute"


def test_group_permissions_empty():
    from app.page_views.inspect import group_permissions
    assert group_permissions(set()) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "c:/Users/e.d.buenaventura/OneDrive - Sysco Corporation/Documents/gcp-role-lookup"
.venv/Scripts/python -m pytest tests/test_inspect_logic.py::test_group_permissions_basic -v
```

Expected: `FAILED` — `ImportError: cannot import name 'group_permissions'`

- [ ] **Step 3: Add group_permissions() to inspect.py**

Insert after line 13 (`sys.path.insert(...)`) and before line 16 (`def render(...)`):

```python
from collections import defaultdict


def group_permissions(perms: set[str]) -> dict[str, list[str]]:
    """Group permissions by service prefix (part before first dot).

    Permissions with no dot go into 'other', which always sorts last.
    Within each group, permissions are sorted alphabetically.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for p in perms:
        service = p.split(".")[0] if "." in p else "other"
        groups[service].append(p)
    for service in groups:
        groups[service].sort()
    return dict(sorted(groups.items(), key=lambda x: (x[0] == "other", x[0])))
```

- [ ] **Step 4: Run all 5 new tests to verify they pass**

```bash
.venv/Scripts/python -m pytest tests/test_inspect_logic.py -v
```

Expected: all 10 tests PASS (5 original + 5 new)

- [ ] **Step 5: Commit**

```bash
git add app/page_views/inspect.py tests/test_inspect_logic.py
git commit -m "feat: add group_permissions() helper to inspect.py"
```

---

## Chunk 2: Replace flat permission blocks with grouped expanders

### Task 2: Add _render_grouped() and replace all st.code permission blocks

**Files:**
- Modify: `app/page_views/inspect.py` (add `_render_grouped()` helper; replace 6 `st.code` blocks)

**Context:** There are 6 places in `inspect.py` that render a flat permission list with `st.code`. All must be replaced with grouped expanders. We introduce a private helper to avoid repeating the pattern.

- [ ] **Step 1: Add _render_grouped() helper after group_permissions()**

Insert after `group_permissions()` (around line 30, before `def render`):

```python
def _render_grouped(perms: set[str]) -> None:
    """Render permissions as collapsed expanders grouped by service.

    Shows plain '(none)' text if the set is empty.
    """
    if not perms:
        st.text("(none)")
        return
    for service, plist in group_permissions(perms).items():
        with st.expander(f"{service} ({len(plist)})", expanded=False):
            st.code("\n".join(plist), language=None)
```

- [ ] **Step 2: Replace all 6 flat permission code blocks**

Replace each occurrence of a flat permission `st.code` block with `_render_grouped(...)`.

**Block 1 — Single-role view (line ~90):**

Old:
```python
        st.subheader(role_title_map.get(role_a_id, "(custom role)"))
        st.caption(f"{len(perms_a)} permissions")
        st.code("\n".join(sorted(perms_a)), language=None)
        return
```

New:
```python
        st.subheader(role_title_map.get(role_a_id, "(custom role)"))
        st.caption(f"{len(perms_a)} permissions")
        _render_grouped(perms_a)
        return
```

**Block 2 — Diff mode, Role B empty (line ~98-101):**

Old:
```python
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            return
```

New:
```python
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            _render_grouped(perms_a)
            return
```

**Block 3 — Diff mode, Role B not found (line ~105-108):**

Old:
```python
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            st.error(f"Role ID not found: {role_b_id}")
            return
```

New:
```python
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            _render_grouped(perms_a)
            st.error(f"Role ID not found: {role_b_id}")
            return
```

**Block 4 — Diff mode, Role B no permission data (line ~113-116):**

Old:
```python
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            st.warning("Permission data unavailable for Role B.")
            return
```

New:
```python
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            _render_grouped(perms_a)
            st.warning("Permission data unavailable for Role B.")
            return
```

**Blocks 5, 6, 7 — Three-column diff (lines ~131-153):**

Old:
```python
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

New:
```python
        with diff_col_a:
            st.subheader("Only in A")
            st.caption(f"{title_a} · {len(only_a)} permissions")
            _render_grouped(only_a)

        with diff_col_both:
            st.subheader("In both")
            st.caption(f"{len(in_both)} permissions")
            _render_grouped(in_both)

        with diff_col_b:
            st.subheader("Only in B")
            st.caption(f"{title_b} · {len(only_b)} permissions")
            _render_grouped(only_b)
```

- [ ] **Step 3: Run full test suite**

```bash
.venv/Scripts/python -m pytest tests/ -v
```

Expected: 14 tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/page_views/inspect.py
git commit -m "feat: replace flat permission lists with grouped expanders in inspector"
```

---

## Chunk 3: Replace text inputs with searchable selectboxes

### Task 3: Swap st.text_input → st.selectbox for Role A and Role B

**Files:**
- Modify: `app/page_views/inspect.py` (input block + value retrieval lines)

**Context:** `st.selectbox` with `format_func` stores the raw role ID in session state while displaying a human-readable label. We must guard against stale session state values before rendering.

- [ ] **Step 1: Replace the input block (lines ~38-55)**

Old:
```python
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
```

New:
```python
    role_options = [""] + sorted(role_title_map.keys())

    def _fmt(rid: str) -> str:
        return "Select a role..." if rid == "" else f"{rid} — {role_title_map.get(rid, rid)}"

    # Guard against stale session state values not present in current options
    # Use .get() to avoid KeyError on first page load before Streamlit sets the key
    if st.session_state.get("inspect_role_a", "") not in role_options:
        st.session_state["inspect_role_a"] = ""
    if st.session_state.get("inspect_role_b", "") not in role_options:
        st.session_state["inspect_role_b"] = ""

    with col_input:
        st.markdown(
            "<div class='section-label'>Role ID</div>",
            unsafe_allow_html=True,
        )
        st.selectbox(
            "Role A",
            role_options,
            format_func=_fmt,
            key="inspect_role_a",
            label_visibility="collapsed",
        )
        st.checkbox("Compare two roles", key="inspect_diff_mode")
        if st.session_state["inspect_diff_mode"]:
            st.selectbox(
                "Role B",
                role_options,
                format_func=_fmt,
                key="inspect_role_b",
                label_visibility="collapsed",
            )
```

- [ ] **Step 2: Remove .strip() calls from value retrieval**

Old (line ~58):
```python
        role_a_id = st.session_state["inspect_role_a"].strip()
```

New:
```python
        role_a_id = st.session_state["inspect_role_a"]
```

Old (line ~94):
```python
        role_b_id = st.session_state["inspect_role_b"].strip()
```

New:
```python
        role_b_id = st.session_state["inspect_role_b"]
```

- [ ] **Step 3: Run full test suite**

```bash
.venv/Scripts/python -m pytest tests/ -v
```

Expected: 14 tests PASS

- [ ] **Step 4: Smoke-test in browser**

```bash
streamlit run app/main.py
```

Verify:
- Navigate to Role Inspector
- Role A selectbox shows searchable dropdown with `"roles/... — Title"` format
- Selecting a role shows grouped permission expanders
- Enable "Compare two roles" — Role B selectbox appears
- Selecting Role B shows three-column diff with grouped expanders in each column
- Empty set columns show `"(none)"` text

- [ ] **Step 5: Commit**

```bash
git add app/page_views/inspect.py
git commit -m "feat: replace text inputs with searchable selectboxes in inspector"
```
