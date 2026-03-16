"""Tests for Permission Search sort and filter logic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


def test_sort_key_predefined_role():
    from pages.permissions import sort_key
    assert sort_key("roles/bigquery.dataEditor") == (0, "roles/bigquery.dataEditor")


def test_sort_key_project_role():
    from pages.permissions import sort_key
    assert sort_key("projects/my-project/roles/customRole") == (
        1,
        "projects/my-project/roles/customRole",
    )


def test_sort_key_org_role():
    from pages.permissions import sort_key
    assert sort_key("organizations/123/roles/customRole") == (
        2,
        "organizations/123/roles/customRole",
    )


def test_sort_key_unknown_bucket():
    from pages.permissions import sort_key
    assert sort_key("unknown/role") == (3, "unknown/role")


def test_sort_predefined_before_project():
    from pages.permissions import sort_key
    assert sort_key("roles/a") < sort_key("projects/b")


def test_search_exact_membership():
    """Search is exact set membership, not a substring match."""
    permissions = {
        "roles/bigquery.dataEditor": {
            "bigquery.tables.create",
            "bigquery.tables.delete",
        },
        "roles/bigquery.dataViewer": {
            "bigquery.tables.get",
            "bigquery.tables.list",
        },
    }
    query = "bigquery.tables.create"
    matches = [
        rid
        for rid, perms in permissions.items()
        if query in {p.lower() for p in perms}
    ]
    assert matches == ["roles/bigquery.dataEditor"]


def test_search_no_match():
    permissions = {"roles/viewer": {"resourcemanager.projects.get"}}
    query = "nonexistent.permission"
    matches = [
        rid
        for rid, perms in permissions.items()
        if query in {p.lower() for p in perms}
    ]
    assert matches == []


def test_search_case_insensitive_stored_permissions():
    """Stored permissions are lowercased before membership test."""
    permissions = {"roles/viewer": {"BigQuery.Tables.Get"}}
    query = "bigquery.tables.get"
    matches = [
        rid
        for rid, perms in permissions.items()
        if query in {p.lower() for p in perms}
    ]
    assert matches == ["roles/viewer"]
