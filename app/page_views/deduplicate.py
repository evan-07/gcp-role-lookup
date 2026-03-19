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

    Handles plain role IDs and Terraform HCL-quoted format:
        roles/storage.admin
        "roles/storage.admin",
        "roles/storage.admin", "roles/storage.bucketViewer",

    Args:
        raw_text: Multi-line string from the textarea.

    Returns:
        (valid_ids, invalid_lines) where valid_ids start with "roles/"
        and invalid_lines do not.
    """
    valid: list[str] = []
    invalid: list[str] = []
    for line in raw_text.splitlines():
        # Split by comma to support multiple quoted entries on one line
        tokens = [t.strip(' ",') for t in line.split(',')]
        for token in tokens:
            if not token:
                continue
            if token.startswith("roles/"):
                valid.append(token)
            else:
                invalid.append(token)
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
            "<div class='section-label'>Role IDs — plain or Terraform HCL format</div>",
            unsafe_allow_html=True,
        )
        input_text = st.text_area(
            label="Role IDs Input",
            placeholder=(
                "roles/storage.admin\n"
                "roles/storage.objectViewer\n"
                "\n"
                "# or Terraform HCL format:\n"
                '"roles/bigquery.dataEditor",\n'
                '"roles/bigquery.dataViewer",'
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
            total_inputs = len(result.kept) + len(result.removed) + len(result.unknown) + len(pre_validation_unknowns)

            st.markdown(
                f"""
                <div class="stat-row">
                  <span class="stat-badge badge-total">{total_inputs} inputs</span>
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
