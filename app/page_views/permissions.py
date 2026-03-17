"""
permissions.py

Permission Search page — given an exact GCP permission string,
finds every role that grants it and displays a Terraform-ready list.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def sort_key(role_id: str) -> tuple:
    """Sort bucket: predefined (roles/) → project → org → other, then alpha."""
    if role_id.startswith("roles/"):
        return (0, role_id)
    if role_id.startswith("projects/"):
        return (1, role_id)
    if role_id.startswith("organizations/"):
        return (2, role_id)
    return (3, role_id)


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Permission Search page."""

    # Global unavailability guard — runs before empty-query check
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

    st.markdown(
        "<div class='section-label'>Permission Search</div>",
        unsafe_allow_html=True,
    )
    st.text_input(
        "Enter an exact GCP permission string (e.g. bigquery.tables.create)",
        key="permission_search_query",
    )

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
