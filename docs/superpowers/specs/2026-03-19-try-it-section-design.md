# "Try it!" Section Implementation Design

**Goal:** Add a collapsible "Try it!" expander to the Resolve Titles and Deduplicate Roles pages that provides example inputs users can load into the textarea in one click.

**Architecture:** Pure UI addition — no new files, no new modules. Changes confined to `app/page_views/resolve.py` and `app/page_views/deduplicate.py`. Each file defines its own `_EXAMPLES` constant and its own copy of the `_render_try_it` helper (intentional duplication — the function is 10 lines, page-specific, and extracting it to a shared module would add indirection with no benefit at this scale).

**Tech Stack:** Streamlit (`st.expander`, `st.code`, `st.button`, `st.session_state`, `st.rerun`)

**Tests:** No automated tests are required for this UI-only change. The helper contains no logic beyond setting session state and calling `st.rerun()`.

---

## Components

### Example Data

Each page defines a module-level constant `_EXAMPLES: list[dict]` with entries shaped as:

```python
{
    "name": str,         # Bold heading shown above code block
    "description": str,  # Caption text describing what the example demonstrates
    "text": str,         # Raw input text that will be loaded into the textarea
}
```

**Resolve Titles examples (`resolve.py`):**

```python
_EXAMPLES = [
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

**Deduplicate Roles examples (`deduplicate.py`):**

```python
_EXAMPLES = [
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

---

### Rendering Helper

Each page file defines its own `_render_try_it` function (not shared):

```python
def _render_try_it(examples: list[dict], state_key: str) -> None:
    with st.expander("💡 Try it!", expanded=False):
        for i, ex in enumerate(examples):
            st.markdown(f"**{ex['name']}**")
            st.caption(ex["description"])
            st.code(ex["text"], language="text")
            if st.button("Load", key=f"try_{state_key}_{i}"):
                st.session_state[state_key] = ex["text"]
                st.rerun()
```

- `language="text"` is passed explicitly to prevent Streamlit's auto-detection from applying syntax highlighting.
- Button keys are formed as `f"try_{state_key}_{i}"` where `i` is the zero-based index from `enumerate`. This produces globally unique keys (`try_resolve_input_0`, `try_deduplicate_input_0`, etc.) because the two pages use different `state_key` values and are never rendered simultaneously under the current single-page navigation model.
- **Contract:** `state_key` must exactly match the `key=` argument on the `st.text_area` in the same page. A mismatch would write to session state silently but be ignored by the widget.
  - `resolve.py` call site: `_render_try_it(_EXAMPLES, "resolve_input")` — matches `key="resolve_input"` on the textarea.
  - `deduplicate.py` call site: `_render_try_it(_EXAMPLES, "deduplicate_input")` — matches `key="deduplicate_input"` on the textarea.

---

### Placement

`_render_try_it` is added as the **last line of the `with col_input:` block body** in both files, after the `if clear_clicked:` branch. The `if clear_clicked:` branch calls `st.rerun()` and exits only when the Clear button was clicked; on all other renders the block falls through to `_render_try_it` normally.

**In `resolve.py`** — insert after line 78 (`st.rerun()` inside the `if clear_clicked:` block), still inside `with col_input:`:

```python
with col_input:
    # ... section label, text_area, col_btn1/col_btn2 buttons ...

    if clear_clicked:
        st.session_state["resolve_input"] = ""
        st.session_state["resolve_results"] = None
        st.rerun()

    _render_try_it(_EXAMPLES, "resolve_input")   # ← last line of with col_input: body
```

**In `deduplicate.py`** — insert after the `if clear_clicked:` block, still inside `with col_input:`:

```python
with col_input:
    # ... section label, text_area, col_btn1/col_btn2 buttons ...

    if clear_clicked:
        st.session_state["deduplicate_input"] = ""
        st.session_state["deduplicate_results"] = None
        st.rerun()

    _render_try_it(_EXAMPLES, "deduplicate_input")   # ← last line of with col_input: body
```

The expander is always shown (the `roles_load_error` early return at the top of `render()` already gates both pages before the column layout is reached).

---

## Behaviour

- Expander starts **collapsed** — zero visual impact until the user opens it.
- Clicking **Load** sets `st.session_state[state_key]` to the example text and calls `st.rerun()`. It does not modify any results key, `deduplicate_pre_unknowns`, or `deduplicate_no_permissions` — those are recomputed when the user next clicks the action button.
- After Load, the output panel continues showing previous results (if any) until the user re-runs. No stale-result indicator is added — the newly populated textarea is the visual cue.
- The Load button and the Clear button cannot both fire in the same Streamlit render cycle; no ordering conflict exists.

---

## Out of Scope

- Auto-running the action on load (user explicitly declined).
- Shared example data module or shared helper (YAGNI).
- Editable or user-saved examples.
- Updating the existing Clear handler to reset `deduplicate_pre_unknowns` / `deduplicate_no_permissions` (pre-existing behaviour, not introduced by this change).
