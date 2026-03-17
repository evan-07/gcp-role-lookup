"""Tests for Permission Search sort and filter logic."""


def test_sort_key_predefined_role():
    from app.page_views.permissions import sort_key
    assert sort_key("roles/bigquery.dataEditor") == (0, "roles/bigquery.dataEditor")


def test_sort_key_project_role():
    from app.page_views.permissions import sort_key
    assert sort_key("projects/my-project/roles/customRole") == (
        1,
        "projects/my-project/roles/customRole",
    )


def test_sort_key_org_role():
    from app.page_views.permissions import sort_key
    assert sort_key("organizations/123/roles/customRole") == (
        2,
        "organizations/123/roles/customRole",
    )


def test_sort_key_unknown_bucket():
    from app.page_views.permissions import sort_key
    assert sort_key("unknown/role") == (3, "unknown/role")


def test_sort_predefined_before_project():
    from app.page_views.permissions import sort_key
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


def test_find_exact_matches_hit():
    from app.page_views.permissions import find_exact_matches
    perms = {
        "roles/bigquery.dataEditor": {"bigquery.tables.create", "bigquery.tables.delete"},
        "roles/bigquery.dataViewer": {"bigquery.tables.get"},
    }
    assert find_exact_matches("bigquery.tables.create", perms) == ["roles/bigquery.dataEditor"]


def test_find_exact_matches_miss():
    from app.page_views.permissions import find_exact_matches
    perms = {"roles/viewer": {"resourcemanager.projects.get"}}
    assert find_exact_matches("nonexistent.permission", perms) == []


def test_find_exact_matches_case_insensitive():
    from app.page_views.permissions import find_exact_matches
    perms = {"roles/viewer": {"BigQuery.Tables.Get"}}
    assert find_exact_matches("bigquery.tables.get", perms) == ["roles/viewer"]


def test_find_partial_matches_substring():
    from app.page_views.permissions import find_partial_matches
    perms = {
        "roles/a": {"bigquery.tables.create", "bigquery.tables.delete"},
        "roles/b": {"bigquery.tables.get"},
    }
    rows, total = find_partial_matches("bigquery", perms)
    perm_names = [r[0] for r in rows]
    assert "bigquery.tables.create" in perm_names
    assert "bigquery.tables.delete" in perm_names
    assert "bigquery.tables.get" in perm_names
    assert total == 3


def test_find_partial_matches_excludes_exact():
    from app.page_views.permissions import find_partial_matches
    perms = {"roles/a": {"bigquery.tables.create"}}
    rows, total = find_partial_matches("bigquery.tables.create", perms)
    assert rows == []
    assert total == 0


def test_find_partial_matches_sorted_by_role_count():
    from app.page_views.permissions import find_partial_matches
    perms = {
        "roles/a": {"bigquery.tables.create", "bigquery.tables.get"},
        "roles/b": {"bigquery.tables.create"},
    }
    rows, _ = find_partial_matches("bigquery", perms)
    # bigquery.tables.create appears in 2 roles, bigquery.tables.get in 1
    assert rows[0] == ("bigquery.tables.create", 2)
    assert rows[1] == ("bigquery.tables.get", 1)


def test_find_partial_matches_limit():
    from app.page_views.permissions import find_partial_matches
    # Build 5 distinct permissions all containing "svc"
    perms = {"roles/x": {f"svc.resource.action{i}" for i in range(5)}}
    rows, total = find_partial_matches("svc", perms, limit=3)
    assert len(rows) == 3
    assert total == 5


def test_find_partial_matches_empty():
    from app.page_views.permissions import find_partial_matches
    perms = {"roles/viewer": {"resourcemanager.projects.get"}}
    rows, total = find_partial_matches("zzznomatch", perms)
    assert rows == []
    assert total == 0
