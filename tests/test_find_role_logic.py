"""Tests for Find Smallest Role pure logic."""


# --- parse_permissions_input ---

def test_parse_trims_whitespace():
    from app.page_views.find_role import parse_permissions_input
    assert parse_permissions_input("  a.b.c  ") == {"a.b.c"}


def test_parse_lowercases():
    from app.page_views.find_role import parse_permissions_input
    assert parse_permissions_input("BigQuery.Tables.Get") == {"bigquery.tables.get"}


def test_parse_discards_blank_lines():
    from app.page_views.find_role import parse_permissions_input
    assert parse_permissions_input("a.b\n\n\nc.d") == {"a.b", "c.d"}


def test_parse_deduplicates():
    from app.page_views.find_role import parse_permissions_input
    assert parse_permissions_input("a.b\na.b") == {"a.b"}


# --- _tier ---

def test_tier_predefined():
    from app.page_views.find_role import _tier
    assert _tier("roles/bigquery.dataEditor") == 0


def test_tier_project():
    from app.page_views.find_role import _tier
    assert _tier("projects/my-project/roles/customRole") == 1


def test_tier_org():
    from app.page_views.find_role import _tier
    assert _tier("organizations/123/roles/customRole") == 2


def test_tier_other():
    from app.page_views.find_role import _tier
    assert _tier("unknown/role") == 3


# --- find_smallest_roles ---

def test_exact_match_found():
    from app.page_views.find_role import find_smallest_roles
    perms = {"roles/a": {"x.y.z", "a.b.c"}}
    exact, partial = find_smallest_roles({"x.y.z"}, perms, {})
    assert len(exact) == 1
    assert exact[0]["role_id"] == "roles/a"
    assert exact[0]["covered"] == 1
    assert partial == []


def test_exact_match_sorted_by_size():
    from app.page_views.find_role import find_smallest_roles
    # Both roles/a and roles/b grant the required perm; roles/a is larger
    perms = {
        "roles/a": {"x.y.z", "extra.a", "extra.b"},   # 3 perms
        "roles/b": {"x.y.z", "extra.c"},               # 2 perms
    }
    exact, _ = find_smallest_roles({"x.y.z"}, perms, {})
    assert exact[0]["role_id"] == "roles/b"  # smaller first


def test_exact_match_tier_before_size():
    from app.page_views.find_role import find_smallest_roles
    # projects/ role is smaller but roles/ tier ranks first
    perms = {
        "projects/p/roles/small": {"x.y.z"},               # 1 perm, tier 1
        "roles/big": {"x.y.z", "extra.a", "extra.b"},      # 3 perms, tier 0
    }
    exact, _ = find_smallest_roles({"x.y.z"}, perms, {})
    assert exact[0]["role_id"] == "roles/big"  # tier 0 before tier 1


def test_no_exact_returns_partial():
    from app.page_views.find_role import find_smallest_roles
    # Use 3 required perms so no role covers all
    perms = {
        "roles/a": {"x.y.z", "a.b.c"},  # covers 2 of 3
        "roles/b": {"x.y.z"},           # covers 1 of 3
    }
    exact, partial = find_smallest_roles({"x.y.z", "a.b.c", "m.n.o"}, perms, {})
    assert exact == []
    assert partial[0]["role_id"] == "roles/a"  # higher coverage first
    assert partial[0]["covered"] == 2


def test_partial_limit():
    from app.page_views.find_role import find_smallest_roles
    # 15 roles each covering 1 of 2 required perms
    perms = {f"roles/r{i}": {"x.y.z"} for i in range(15)}
    exact, partial = find_smallest_roles({"x.y.z", "a.b.c"}, perms, {}, partial_limit=10)
    assert exact == []
    assert len(partial) == 10


def test_empty_required():
    from app.page_views.find_role import find_smallest_roles
    perms = {"roles/a": {"x.y.z"}}
    exact, partial = find_smallest_roles(set(), perms, {})
    assert exact == []
    assert partial == []


def test_no_coverage():
    from app.page_views.find_role import find_smallest_roles
    perms = {"roles/a": {"x.y.z"}}
    exact, partial = find_smallest_roles({"a.b.c"}, perms, {})
    assert exact == []
    assert partial == []


def test_exact_suppresses_partial():
    from app.page_views.find_role import find_smallest_roles
    perms = {
        "roles/full": {"x.y.z", "a.b.c"},   # exact
        "roles/partial": {"x.y.z"},          # partial
    }
    exact, partial = find_smallest_roles({"x.y.z", "a.b.c"}, perms, {})
    assert len(exact) == 1
    assert partial == []
