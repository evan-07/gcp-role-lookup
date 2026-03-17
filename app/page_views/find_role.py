"""
find_role.py

Find Smallest Role page — given a list of required GCP permissions,
finds the role(s) that grant all of them with the fewest extra permissions.
Falls back to top partial matches when no exact match exists.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


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
    pass  # implemented in Task 2
