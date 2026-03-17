"""
inspect.py

Role Inspector page — given a GCP role ID, shows its title and full
permission list. Optionally diffs two roles side-by-side.
"""

from collections import defaultdict

import streamlit as st


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


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Role Inspector page."""

    st.markdown(
        """
        <div class="app-header">
          <div>
            <h1>Role Inspector</h1>
            <p>Browse the full permission set of any GCP role, grouped by service.
            Enable "Compare two roles" to see a side-by-side diff of what each role adds or shares.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

    with col_output:
        role_a_id = st.session_state["inspect_role_a"]
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
            _render_grouped(perms_a)
            return

        # Diff mode — Role B evaluation
        role_b_id = st.session_state["inspect_role_b"]

        if not role_b_id:
            # Diff on but Role B empty — show Role A only
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            _render_grouped(perms_a)
            return

        # Role B not found anywhere
        if role_b_id not in permissions and role_b_id not in role_title_map:
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            _render_grouped(perms_a)
            st.error(f"Role ID not found: {role_b_id}")
            return

        # Role B known but has no permission data (partial data)
        if role_b_id not in permissions:
            st.subheader(role_title_map.get(role_a_id, "(custom role)"))
            st.caption(f"{len(perms_a)} permissions")
            _render_grouped(perms_a)
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
            _render_grouped(only_a)

        with diff_col_both:
            st.subheader("In both")
            st.caption(f"{len(in_both)} permissions")
            _render_grouped(in_both)

        with diff_col_b:
            st.subheader("Only in B")
            st.caption(f"{title_b} · {len(only_b)} permissions")
            _render_grouped(only_b)
