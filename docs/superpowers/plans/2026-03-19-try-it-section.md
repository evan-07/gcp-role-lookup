# "Try it!" Section Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible "💡 Try it!" expander with example inputs to the Resolve Titles and Deduplicate Roles pages so users can load pre-filled examples into the textarea in one click.

**Architecture:** Pure UI addition — no new files, no new modules. Each page file gets a module-level `_EXAMPLES` constant and a `_render_try_it()` helper function. The helper is duplicated intentionally (10 lines, page-specific). No automated tests needed — the helper contains no logic beyond setting session state.

**Tech Stack:** Streamlit (`st.expander`, `st.code`, `st.button`, `st.session_state`, `st.rerun`), Python 3.12+

**Spec:** `docs/superpowers/specs/2026-03-19-try-it-section-design.md`

---

## Chunk 1: Resolve Titles page

### Task 1: Add "Try it!" to Resolve Titles (`resolve.py`)

**Files:**
- Modify: `app/page_views/resolve.py` (lines 1–9 for imports area, after line 78 for call site)

#### Step 1: Add `_EXAMPLES` constant

Open `app/page_views/resolve.py`. After the imports block (after line 14, before `def render`), insert the following module-level constant:

```python
_EXAMPLES: list[dict] = [
    {
        "name": "Common roles",
        "description": "Exact matches for frequently used roles across BigQuery, Storage, Pub/Sub, and Cloud Run.",
        "text": (
            "BigQuery Data Editor\n"
            "BigQuery Data Viewer\n"
            "Storage Admin\n"
            "Pub/Sub Publisher\n"
            "Cloud Run Invoker"
        ),
    },
    {
        "name": "Fuzzy matches",
        "description": "Near-typos — load this and click Resolve Roles to see confidence scoring and the Review Required table.",
        "text": (
            "BigQuery Data Editer\n"
            "Stoarge Admin\n"
            "PubSub Publishr\n"
            "Cloud Run Invokr"
        ),
    },
    {
        "name": "Superseded roles",
        "description": (
            "Includes roles whose permissions are fully covered by another role in the batch. "
            "Requires role_permissions.json to be loaded (see sidebar) to show supersession markers; "
            "otherwise resolves normally without them."
        ),
        "text": (
            "BigQuery Data Editor\n"
            "BigQuery Data Viewer\n"
            "Storage Admin\n"
            "Storage Object Viewer"
        ),
    },
]
```

- [ ] Insert `_EXAMPLES` at module level in `app/page_views/resolve.py`, between the imports and `def render`.

#### Step 2: Add `_render_try_it` helper

Immediately after `_EXAMPLES`, insert:

```python
def _render_try_it(examples: list[dict], state_key: str) -> None:
    """Render a collapsible expander with example inputs the user can load."""
    with st.expander("💡 Try it!", expanded=False):
        for i, ex in enumerate(examples):
            st.markdown(f"**{ex['name']}**")
            st.caption(ex["description"])
            st.code(ex["text"], language="text")
            if st.button("Load", key=f"try_{state_key}_{i}"):
                st.session_state[state_key] = ex["text"]
                st.rerun()
```

- [ ] Insert `_render_try_it` immediately after `_EXAMPLES` in `app/page_views/resolve.py`.

#### Step 3: Call `_render_try_it` at the end of `col_input`

In `render()`, locate the `with col_input:` block. The block currently ends after the `if clear_clicked:` handler (line 78). Add the call as the **last line** inside `with col_input:`:

Before (lines 75–79):
```python
        if clear_clicked:
            st.session_state["resolve_input"] = ""
            st.session_state["resolve_results"] = None
            st.rerun()

```

After:
```python
        if clear_clicked:
            st.session_state["resolve_input"] = ""
            st.session_state["resolve_results"] = None
            st.rerun()

        _render_try_it(_EXAMPLES, "resolve_input")
```

- [ ] Add `_render_try_it(_EXAMPLES, "resolve_input")` as the last line of `with col_input:` in `resolve.py`.

#### Step 4: Manual smoke test

- [ ] Run the app: `streamlit run app/main.py`
- [ ] Navigate to **Resolve Titles**.
- [ ] Confirm the expander "💡 Try it!" appears below the Clear button, collapsed by default.
- [ ] Open it. Confirm 3 examples each show a bold name, caption, code block, and "Load" button.
- [ ] Click **Load** on "Common roles". Confirm the textarea fills with the 5 role titles.
- [ ] Click **Resolve Roles →**. Confirm output appears with all exact matches.
- [ ] Click **Load** on "Fuzzy matches". Confirm textarea updates. Run — confirm Review Required table appears.
- [ ] Click **Load** on "Superseded roles". Run — confirm supersession markers appear (if `role_permissions.json` is loaded).

#### Step 5: Commit

```bash
git add app/page_views/resolve.py
git commit -m "feat: add Try it! expander to Resolve Titles page"
```

- [ ] Commit.

---

## Chunk 2: Deduplicate Roles page

### Task 2: Add "Try it!" to Deduplicate Roles (`deduplicate.py`)

**Files:**
- Modify: `app/page_views/deduplicate.py` (module level for constants/helper, after line 113 for call site)

#### Step 1: Add `_EXAMPLES` constant

Open `app/page_views/deduplicate.py`. After the imports block (after line 16, before `def _validate_lines`), insert:

```python
_EXAMPLES: list[dict] = [
    {
        "name": "Storage redundancy",
        "description": "storage.admin covers storage.objectViewer and storage.objectCreator — they will be removed.",
        "text": (
            "roles/storage.admin\n"
            "roles/storage.objectViewer\n"
            "roles/storage.objectCreator"
        ),
    },
    {
        "name": "BigQuery redundancy",
        "description": "bigquery.admin covers the narrower roles — they will be removed.",
        "text": (
            "roles/bigquery.admin\n"
            "roles/bigquery.dataEditor\n"
            "roles/bigquery.dataViewer\n"
            "roles/bigquery.jobUser"
        ),
    },
    {
        "name": "Terraform HCL format",
        "description": "Shows that quoted Terraform syntax is accepted directly as input alongside plain role IDs.",
        "text": (
            '"roles/storage.admin",\n'
            '"roles/storage.objectViewer",\n'
            '"roles/bigquery.dataEditor",\n'
            '"roles/bigquery.dataViewer",'
        ),
    },
]
```

- [ ] Insert `_EXAMPLES` at module level in `app/page_views/deduplicate.py`, between the imports and `def _validate_lines`.

#### Step 2: Add `_render_try_it` helper

Immediately after `_EXAMPLES`, insert the same helper (duplicated by design — see spec):

```python
def _render_try_it(examples: list[dict], state_key: str) -> None:
    """Render a collapsible expander with example inputs the user can load."""
    with st.expander("💡 Try it!", expanded=False):
        for i, ex in enumerate(examples):
            st.markdown(f"**{ex['name']}**")
            st.caption(ex["description"])
            st.code(ex["text"], language="text")
            if st.button("Load", key=f"try_{state_key}_{i}"):
                st.session_state[state_key] = ex["text"]
                st.rerun()
```

- [ ] Insert `_render_try_it` immediately after `_EXAMPLES` in `app/page_views/deduplicate.py`.

#### Step 3: Call `_render_try_it` at the end of `col_input`

In `render()`, locate the `with col_input:` block. It currently ends after the `if clear_clicked:` handler (line 113). Add the call as the **last line** inside `with col_input:`:

Before (lines 110–114):
```python
        if clear_clicked:
            st.session_state["deduplicate_input"] = ""
            st.session_state["deduplicate_results"] = None
            st.rerun()

```

After:
```python
        if clear_clicked:
            st.session_state["deduplicate_input"] = ""
            st.session_state["deduplicate_results"] = None
            st.rerun()

        _render_try_it(_EXAMPLES, "deduplicate_input")
```

- [ ] Add `_render_try_it(_EXAMPLES, "deduplicate_input")` as the last line of `with col_input:` in `deduplicate.py`.

#### Step 4: Manual smoke test

- [ ] Run the app: `streamlit run app/main.py`
- [ ] Navigate to **Deduplicate Roles**.
- [ ] Confirm "💡 Try it!" appears below the Clear button, collapsed by default.
- [ ] Open it. Confirm 3 examples with bold name, caption, code block, and "Load" button.
- [ ] Click **Load** on "Storage redundancy". Confirm textarea fills with the 3 role IDs.
- [ ] Click **Deduplicate →**. Confirm only `roles/storage.admin` is kept; the other two are superseded.
- [ ] Click **Load** on "BigQuery redundancy". Run — confirm only `roles/bigquery.admin` is kept.
- [ ] Click **Load** on "Terraform HCL format". Run — confirm all 4 quoted role IDs are parsed correctly (storage.admin kept, objectViewer superseded; both BigQuery roles kept or one superseded depending on permissions data).

#### Step 5: Commit

```bash
git add app/page_views/deduplicate.py
git commit -m "feat: add Try it! expander to Deduplicate Roles page"
```

- [ ] Commit.
