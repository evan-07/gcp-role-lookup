# Output Format Toggle Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a HCL / JSON radio toggle to the Resolve Titles output column so users can switch between Terraform HCL and a clean JSON array of resolved role IDs.

**Architecture:** Two small changes — add one session state key to `main.py`, then update `resolve.py`'s `col_output` block to read the toggle and branch on HCL vs JSON rendering. No new files, no new tests (logic is trivial; verified by smoke test).

**Tech Stack:** Streamlit 1.55.0, Python `json` stdlib.

---

## Chunk 1: Session state key + toggle widget + JSON output

### Task 1: Add resolve_output_format to _DEFAULTS in main.py

**Files:**
- Modify: `app/main.py` (one line in `_DEFAULTS`)

- [ ] **Step 1: Add the new key to _DEFAULTS**

In `app/main.py`, find the `_DEFAULTS` dict (around line 132):

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

Add the new key:

```python
_DEFAULTS: dict = {
    "page": "resolve",
    "resolve_input": "",
    "inspect_role_a": "",
    "inspect_role_b": "",
    "inspect_diff_mode": False,
    "permission_search_query": "",
    "resolve_output_format": "HCL",
    "roles_load_error": None,
}
```

- [ ] **Step 2: Run full test suite to verify no regressions**

```bash
cd "c:/Users/e.d.buenaventura/OneDrive - Sysco Corporation/Documents/gcp-role-lookup"
.venv/Scripts/python -m pytest tests/ -v
```

Expected: **22 tests PASS**

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: add resolve_output_format session state key"
```

---

### Task 2: Update col_output in resolve.py with toggle and JSON branch

**Files:**
- Modify: `app/page_views/resolve.py` (col_output block only)

**Context:** The current `col_output` block (lines 146–187) has a static section label, computes `hcl_output` unconditionally, then renders `st.code(hcl_output, language="hcl")`. We need to:
1. Make the section label dynamic
2. Move `hcl_output = format_as_terraform(results)` inside the HCL branch (avoid computing it in JSON mode)
3. Add the radio toggle after stat badges
4. Branch on `fmt` for the code block

- [ ] **Step 1: Replace the col_output block**

Old block (lines 146–187):

```python
    with col_output:
        st.markdown(
            "<div class='section-label'>Terraform HCL Output</div>",
            unsafe_allow_html=True,
        )

        if results is not None:
            summary = format_results_summary(results)
            hcl_output = format_as_terraform(results)

            total = sum(v for k, v in summary.items() if k != "empty")
            fuzzy = summary["high"] + summary["medium"]
            missed = summary["low"] + summary["not_found"]

            st.markdown(
                f"""
                <div class="stat-row">
                  <span class="stat-badge badge-total">{total} inputs</span>
                  <span class="stat-badge badge-exact">✓ {summary['exact']} exact</span>
                  <span class="stat-badge badge-fuzzy">~ {fuzzy} fuzzy</span>
                  <span class="stat-badge badge-miss">✗ {missed} unresolved</span>
                  <span class="stat-badge badge-superseded">⛔ {summary['superseded']} superseded</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.code(hcl_output, language="hcl")

        elif resolve_clicked and not roles:
            st.error(
                "Roles data could not be loaded. "
                "Check the sidebar for details."
            )

        else:
            st.markdown(
                "<div class='hcl-placeholder'>"
                "← Enter role titles and click Resolve Roles"
                "</div>",
                unsafe_allow_html=True,
            )
```

New block:

```python
    with col_output:
        fmt = st.session_state.get("resolve_output_format", "HCL")
        label = "Terraform HCL Output" if fmt == "HCL" else "JSON Role Array"
        st.markdown(
            f"<div class='section-label'>{label}</div>",
            unsafe_allow_html=True,
        )

        if results is not None:
            summary = format_results_summary(results)

            total = sum(v for k, v in summary.items() if k != "empty")
            fuzzy = summary["high"] + summary["medium"]
            missed = summary["low"] + summary["not_found"]

            st.markdown(
                f"""
                <div class="stat-row">
                  <span class="stat-badge badge-total">{total} inputs</span>
                  <span class="stat-badge badge-exact">✓ {summary['exact']} exact</span>
                  <span class="stat-badge badge-fuzzy">~ {fuzzy} fuzzy</span>
                  <span class="stat-badge badge-miss">✗ {missed} unresolved</span>
                  <span class="stat-badge badge-superseded">⛔ {summary['superseded']} superseded</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.radio(
                "Output format",
                ["HCL", "JSON"],
                horizontal=True,
                key="resolve_output_format",
                label_visibility="collapsed",
            )

            if fmt == "HCL":
                hcl_output = format_as_terraform(results)
                st.code(hcl_output, language="hcl")
            else:
                import json
                role_ids = [r.role_id for r in results if r.role_id is not None]
                st.code(json.dumps(role_ids, indent=2), language="json")

        elif resolve_clicked and not roles:
            st.error(
                "Roles data could not be loaded. "
                "Check the sidebar for details."
            )

        else:
            st.markdown(
                "<div class='hcl-placeholder'>"
                "← Enter role titles and click Resolve Roles"
                "</div>",
                unsafe_allow_html=True,
            )
```

- [ ] **Step 2: Run full test suite**

```bash
.venv/Scripts/python -m pytest tests/ -v
```

Expected: **22 tests PASS**

- [ ] **Step 3: Smoke-test in browser**

```bash
streamlit run app/main.py
```

Verify on the Resolve Titles page:
- Before resolving: section label reads "Terraform HCL Output", no toggle visible
- After resolving with some titles: stat badges appear, toggle appears with "HCL" selected
- HCL mode: existing HCL output unchanged
- Switching to JSON: section label changes to "JSON Role Array", output shows a JSON array of role IDs
- All-unresolved input in JSON mode: `[]` shown
- Toggle selection persists when navigating to another page and back

- [ ] **Step 4: Commit**

```bash
git add app/page_views/resolve.py
git commit -m "feat: add HCL/JSON output format toggle to Resolve Titles page"
```
