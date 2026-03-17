"""
resolve.py

Resolve Titles page — matches GCP role titles to role IDs,
shows Terraform HCL output, supersession detection, and review table.
"""

import pandas as pd
import streamlit as st

from app.formatter import format_as_terraform, format_results_summary
from app.matcher import MatchResult, match_titles_bulk
from app.supersession import check_supersessions


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Resolve Titles page."""

    # --- Main panel ---
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
            <h1>Resolve Titles</h1>
            <p>Paste GCP role titles to look up their canonical role IDs.
            Includes fuzzy matching, supersession detection, and Terraform HCL or JSON output.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_input, col_output = st.columns([1, 2], gap="large")

    with col_input:
        st.markdown(
            "<div class='section-label'>Role Titles — one per line</div>",
            unsafe_allow_html=True,
        )
        input_text = st.text_area(
            label="Role Titles Input",
            placeholder=(
                "BigQuery Connection User\n"
                "BigQuery Data Editor\n"
                "BigQuery Data Viewer\n"
                "BigQuery Job User\n"
                "Storage Admin"
            ),
            label_visibility="collapsed",
            key="resolve_input",
        )

        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            resolve_clicked = st.button(
                "Resolve Roles →",
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
            st.session_state["resolve_input"] = ""
            st.session_state["resolve_results"] = None
            st.rerun()

    # Compute results before col_output so they're accessible for the
    # full-width review table rendered outside the columns block.
    # Results are stored in session state so the format toggle rerun
    # doesn't lose them.
    if resolve_clicked and input_text.strip() and roles:
        results = match_titles_bulk(input_text, roles)
        if permissions:
            check_supersessions(results, permissions, roles)
        st.session_state["resolve_results"] = results
    else:
        results = st.session_state.get("resolve_results")

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

    # --- Review Required table (full-width, below columns) ---
    if results is not None:
        review_rows = []
        for r in results:
            if r.status in ("exact", "empty") and not r.supersession:
                continue

            if r.supersession:
                status_label = "⛔ Superseded"
                note = f"Covered by: {r.supersession.superseded_by_title}"
            elif r.status == "high":
                status_label = "~ High confidence"
                note = f"Matched: {r.matched_title}"
            elif r.status == "medium":
                status_label = "~ Medium confidence"
                note = f"Matched: {r.matched_title}"
            elif r.status == "low":
                status_label = "✗ Low confidence"
                suggestions = "; ".join(
                    f"{s['title']} ({s['confidence']}%)"
                    for s in (r.suggestions or [])
                )
                note = (
                    f"Suggestions: {suggestions}" if suggestions else "No suggestions"
                )
            else:
                status_label = "✗ Not found"
                note = ""

            review_rows.append(
                {
                    "Status": status_label,
                    "Input Title": r.input_title,
                    "Matched Title": r.matched_title or "—",
                    "Confidence": f"{r.confidence}%" if r.confidence else "—",
                    "Note": note,
                }
            )

        if review_rows:
            with st.expander(
                f"⚠️ Review Required — {len(review_rows)} item(s)",
                expanded=False,
            ):
                df = pd.DataFrame(review_rows)
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Status": st.column_config.TextColumn(width="medium"),
                        "Input Title": st.column_config.TextColumn(width="medium"),
                        "Matched Title": st.column_config.TextColumn(width="medium"),
                        "Confidence": st.column_config.TextColumn(width="small"),
                        "Note": st.column_config.TextColumn(width="large"),
                    },
                )
