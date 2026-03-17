# Output Format Toggle Design

## Goal

Add a HCL / JSON toggle to the Resolve Titles page so users can get a clean JSON array of resolved role IDs in addition to the existing Terraform HCL output.

## Scope

Changes confined to `app/page_views/resolve.py` and `app/main.py` (one new session state key). No new test files — the format extraction logic is simple enough to verify through the existing test suite and smoke testing.

---

## Toggle

A `st.radio` widget with options `["HCL", "JSON"]` rendered `horizontal=True`, placed inside `col_output` immediately after the stat badges and before the code block. Only rendered when `results is not None`.

Session state key: `resolve_output_format` (str, default `"HCL"`). Added to `_DEFAULTS` in `app/main.py`.

The section label above the output area changes dynamically:
- HCL mode: `"Terraform HCL Output"` (current label, unchanged)
- JSON mode: `"JSON Role Array"`

---

## HCL Mode

Unchanged. `format_as_terraform(results)` output rendered with `st.code(..., language="hcl")` exactly as today.

---

## JSON Mode

Output is a JSON array of all resolved role IDs — any result where `result.role_id is not None`. Empty inputs (`status == "empty"`) are excluded. Order matches the original input order.

```python
import json

role_ids = [r.role_id for r in results if r.role_id is not None]
st.code(json.dumps(role_ids, indent=2), language="json")
```

No comments, no confidence annotations, no supersession markers — just the clean list. The stat badges remain visible in JSON mode (unchanged).

---

## Session State

`resolve_output_format` is added to `_DEFAULTS` in `main.py`:

```python
_DEFAULTS: dict = {
    ...
    "resolve_output_format": "HCL",
}
```

The `st.radio` uses `key="resolve_output_format"` so Streamlit manages its value automatically. The value persists across page navigations (like all other session state keys).

---

## Updated col_output Block

The relevant portion of `col_output` becomes:

```python
    with col_output:
        fmt = st.session_state.get("resolve_output_format", "HCL")
        label = "Terraform HCL Output" if fmt == "HCL" else "JSON Role Array"
        st.markdown(
            f"<div class='section-label'>{label}</div>",
            unsafe_allow_html=True,
        )

        if results is not None:
            # ... stat badges (unchanged) ...

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
```

Note: `fmt` is read from session state *before* the radio widget is rendered, so it reflects the value from the previous render (Streamlit's standard widget update cycle). This is correct — the radio widget updates session state on interaction, then `st.rerun()` is triggered, and on the next render `fmt` picks up the new value.

---

## Files Modified

| File | Change |
|------|--------|
| `app/main.py` | Add `"resolve_output_format": "HCL"` to `_DEFAULTS` |
| `app/page_views/resolve.py` | Dynamic section label; add `st.radio` toggle; conditional HCL vs JSON code block |
