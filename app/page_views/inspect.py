"""
inspect.py

Role Inspector page — given a GCP role ID, shows its title and full
permission list. Optionally diffs two roles side-by-side.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Role Inspector page."""

    # Global unavailability guard — runs before any role-specific lookup
    if not permissions:
        st.warning(
            "Permission data is not loaded. "
            "Please use the Refresh button on the Resolve Titles page."
        )
        return

    if st.session_state.get("roles_load_error"):
        st.error(
            "Roles data could not be loaded: "
            + st.session_state["roles_load_error"]
        )
        return

    role_title_map = {r["name"]: r["title"] for r in roles}

    col_input, col_output = st.columns([1, 2], gap="large")

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

    with col_output:
        role_a_id = st.session_state["inspect_role_a"].strip()
        diff_mode = st.session_state["inspect_diff_mode"]

        # No Role A input — nothing to show
        if not role_a_id:
            st.markdown(
                "<div class='hcl-placeholder'>"
                "← Enter a Role ID to inspect"
                "</div>",
                unsafe_allow_html=True,
            )
            return

        # Role A not found anywhere
        if role_a_id not in permissions and role_a_id not in role_title_map:
            st.error(f"Role ID not found: {role_a_id}")
            return

        # Role A known but has no permission data (partial data)
        if role_a_id not in permissions:
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.warning(
                "Permission data unavailable for this role. Try refreshing."
            )
            return

        perms_a: set[str] = permissions[role_a_id]

        if not diff_mode:
            # Single-role output
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            return

        # Diff mode — Role B evaluation
        role_b_id = st.session_state["inspect_role_b"].strip()

        if not role_b_id:
            # Diff on but Role B empty — show Role A only
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            return

        # Role B not found anywhere
        if role_b_id not in permissions and role_b_id not in role_title_map:
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            st.error(f"Role ID not found: {role_b_id}")
            return

        # Role B known but has no permission data (partial data)
        if role_b_id not in permissions:
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            st.code("\n".join(sorted(perms_a)), language=None)
            st.warning("Permission data unavailable for Role B.")
            return

        perms_b: set[str] = permissions[role_b_id]

        # Both roles resolve — render three-column diff
        only_a = perms_a - perms_b
        in_both = perms_a & perms_b
        only_b = perms_b - perms_a

        title_a = role_title_map.get(role_a_id, "(custom role)")
        title_b = role_title_map.get(role_b_id, "(custom role)")

        diff_col_a, diff_col_both, diff_col_b = st.columns([1, 1, 1])

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
