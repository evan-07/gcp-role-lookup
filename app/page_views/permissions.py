"""
permissions.py

Permission Search page — given an exact GCP permission string,
finds every role that grants it and displays a Terraform-ready list.
"""

import streamlit as st


def sort_key(role_id: str) -> tuple:
    """Sort bucket: predefined (roles/) → project → org → other, then alpha."""
    if role_id.startswith("roles/"):
        return (0, role_id)
    if role_id.startswith("projects/"):
        return (1, role_id)
    if role_id.startswith("organizations/"):
        return (2, role_id)
    return (3, role_id)


def find_exact_matches(
    query: str, permissions: dict[str, set[str]]
) -> list[str]:
    """Return sorted role IDs whose permission set contains query exactly (case-insensitive)."""
    q = query.lower()
    return sorted(
        [rid for rid, perms in permissions.items() if q in {p.lower() for p in perms}],
        key=sort_key,
    )


def find_partial_matches(
    query: str, permissions: dict[str, set[str]], limit: int = 100
) -> tuple[list[tuple[str, int]], int]:
    """Return (rows, total_count) for permission strings containing query as substring.

    Excludes exact match. Rows are (permission_string, role_count) sorted by
    role_count descending then alphabetically, capped at limit.
    All permission strings are lowercased (case variants merged).
    """
    q = query.lower()
    counts: dict[str, int] = {}
    for perms in permissions.values():
        for p in perms:
            pl = p.lower()
            if q in pl and pl != q:
                counts[pl] = counts.get(pl, 0) + 1
    results = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return results[:limit], len(counts)


def render(roles: list[dict], permissions: dict[str, set[str]]) -> None:
    """Render the Permission Search page."""

    st.markdown(
        """
        <div class="app-header">
          <div>
            <h1>Permission Search</h1>
            <p>Find which GCP roles grant a specific IAM permission.
            Returns exact matches (roles that include it) and partial matches (permissions containing your query as a substring).</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

    if len(query) < 3:
        st.info("Enter at least 3 characters to search.")
        return

    role_title_map = {r["name"]: r["title"] for r in roles}
    exact_matches = find_exact_matches(query, permissions)
    partial_rows, partial_total = find_partial_matches(query, permissions)

    if not exact_matches and not partial_rows:
        st.info(f"No permissions or roles found for: {query}")
        return

    import pandas as pd

    # --- Exact Matches section ---
    if exact_matches:
        st.markdown(
            "<div class='section-label'>Exact Matches</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{len(exact_matches)} role(s) grant this permission exactly.")
        exact_rows = [
            {
                "Role ID": rid,
                "Role Title": role_title_map.get(rid, "(custom role)"),
                "Terraform String": f'"{rid}"',
            }
            for rid in exact_matches
        ]
        df_exact = pd.DataFrame(exact_rows)
        st.dataframe(df_exact, use_container_width=True, hide_index=True)
        st.markdown(
            "<div class='section-label'>Terraform Role Strings</div>",
            unsafe_allow_html=True,
        )
        st.code("\n".join(row["Terraform String"] for row in exact_rows), language=None)

    # --- Partial Matches section ---
    if partial_rows:
        st.markdown(
            "<div class='section-label'>Partial Matches</div>",
            unsafe_allow_html=True,
        )
        truncation_note = (
            f" Showing first {len(partial_rows)} — refine your query to narrow results."
            if partial_total > len(partial_rows) else ""
        )
        st.caption(
            f"{partial_total} permission string(s) contain '{query}'.{truncation_note}"
        )
        df_partial = pd.DataFrame(
            [{"Permission": perm, "# Roles": count} for perm, count in partial_rows]
        )
        st.dataframe(df_partial, use_container_width=True, hide_index=True)
