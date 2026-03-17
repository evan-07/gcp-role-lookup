"""
find_role.py

Find Smallest Role page — given a list of required GCP permissions,
finds the role(s) that grant all of them with the fewest extra permissions.
Falls back to top partial matches when no exact match exists.
"""

import streamlit as st


def parse_permissions_input(raw: str) -> set[str]:
    """Parse raw text area input into a set of lowercased permission strings.

    Strips whitespace, lowercases, discards blank lines and duplicates.
    """
    return {line.strip().lower() for line in raw.splitlines() if line.strip()}


def _tier(role_id: str) -> int:
    """Return sort tier for a role ID: predefined=0, project=1, org=2, other=3."""
    if role_id.startswith("roles/"):
        return 0
    if role_id.startswith("projects/"):
        return 1
    if role_id.startswith("organizations/"):
        return 2
    return 3


def find_smallest_roles(
    required: set[str],
    permissions: dict[str, set[str]],
    role_title_map: dict[str, str],
    partial_limit: int = 10,
) -> tuple[list[dict], list[dict]]:
    """Find roles that grant all (or most) of the required permissions.

    Returns (exact_matches, partial_matches) as lists of dicts:
      {"role_id": str, "title": str, "total_perms": int, "covered": int}

    exact_matches: roles where required ⊆ role_perms, sorted by (tier, total_perms, role_id)
    partial_matches: top partial_limit roles by covered count (only when exact is empty),
                     sorted by (-covered, tier, total_perms, role_id)
    """
    if not required:
        return [], []

    exact: list[dict] = []
    partial: list[dict] = []

    for role_id, perms in permissions.items():
        covered = len(required & perms)
        if covered == 0:
            continue
        entry = {
            "role_id": role_id,
            "title": role_title_map.get(role_id, "(custom role)"),
            "total_perms": len(perms),
            "covered": covered,
        }
        if required.issubset(perms):
            exact.append(entry)
        else:
            partial.append(entry)

    exact.sort(key=lambda x: (_tier(x["role_id"]), x["total_perms"], x["role_id"]))

    if exact:
        return exact, []

    partial.sort(key=lambda x: (-x["covered"], _tier(x["role_id"]), x["total_perms"], x["role_id"]))
    return [], partial[:partial_limit]


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Find Smallest Role page."""

    st.markdown(
        """
        <div class="app-header">
          <div>
            <h1>Find Smallest Role</h1>
            <p>Enter the permissions your workload needs and find the least-privilege GCP role that covers all of them.
            When no single role qualifies, the top partial matches are shown ranked by coverage.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not permissions:
        st.warning(
            "Permission data is not loaded. "
            "Please use the Refresh button in the sidebar."
        )
        return

    role_title_map = {r["name"]: r["title"] for r in roles}

    st.markdown(
        "<div class='section-label'>Required Permissions — one per line</div>",
        unsafe_allow_html=True,
    )
    st.text_area(
        "Required permissions",
        placeholder="bigquery.tables.create\nbigquery.tables.delete\nbigquery.datasets.get",
        label_visibility="collapsed",
        key="find_role_input",
    )

    find_clicked = st.button("Find Role →", type="primary")

    if not find_clicked:
        return

    required = parse_permissions_input(st.session_state["find_role_input"])

    if not required:
        st.info("Enter at least one permission to search.")
        return

    exact, partial = find_smallest_roles(required, permissions, role_title_map)

    if not exact and not partial:
        st.info("No roles found granting any of the required permissions.")
        return

    import pandas as pd  # deferred to avoid module-level Streamlit dependency in tests

    if exact:
        st.markdown(
            "<div class='section-label'>Exact Matches</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{len(exact)} role(s) grant all {len(required)} required permissions.")
        df_exact = pd.DataFrame([
            {
                "Role ID": e["role_id"],
                "Title": e["title"],
                "Total Permissions": e["total_perms"],
            }
            for e in exact
        ])
        st.dataframe(df_exact, use_container_width=True, hide_index=True)

    if partial:
        st.markdown(
            "<div class='section-label'>Partial Matches</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"No single role grants all {len(required)} permissions. "
            "Top partial matches:"
        )
        df_partial = pd.DataFrame([
            {
                "Role ID": p["role_id"],
                "Title": p["title"],
                "Covers": f"{p['covered']} / {len(required)}",
                "Total Permissions": p["total_perms"],
            }
            for p in partial
        ])
        st.dataframe(df_partial, use_container_width=True, hide_index=True)
