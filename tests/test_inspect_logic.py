"""Tests for Role Inspector diff logic edge cases."""


def test_diff_only_in_a():
    perms_a = {"a.b.c", "d.e.f", "g.h.i"}
    perms_b = {"d.e.f", "x.y.z"}
    assert perms_a - perms_b == {"a.b.c", "g.h.i"}


def test_diff_in_both():
    perms_a = {"a.b.c", "d.e.f"}
    perms_b = {"d.e.f", "x.y.z"}
    assert perms_a & perms_b == {"d.e.f"}


def test_diff_only_in_b():
    perms_a = {"a.b.c", "d.e.f"}
    perms_b = {"d.e.f", "x.y.z"}
    assert perms_b - perms_a == {"x.y.z"}


def test_empty_diff_column_renders_none_marker():
    """Empty diff set produces the '(none)' sentinel used in st.code."""
    empty: set[str] = set()
    result = "\n".join(sorted(empty)) if empty else "(none)"
    assert result == "(none)"


def test_nonempty_diff_column_sorts_alphabetically():
    perms = {"z.a.b", "a.b.c", "m.n.o"}
    result = "\n".join(sorted(perms))
    assert result == "a.b.c\nm.n.o\nz.a.b"


def test_group_permissions_basic():
    from app.page_views.inspect import group_permissions
    result = group_permissions({"bigquery.tables.create", "bigquery.tables.delete"})
    assert result == {"bigquery": ["bigquery.tables.create", "bigquery.tables.delete"]}


def test_group_permissions_multiple_services():
    from app.page_views.inspect import group_permissions
    result = group_permissions({"bigquery.tables.get", "compute.instances.list"})
    assert list(result.keys()) == ["bigquery", "compute"]


def test_group_permissions_no_dot():
    from app.page_views.inspect import group_permissions
    result = group_permissions({"nodotpermission"})
    assert "other" in result
    assert result["other"] == ["nodotpermission"]


def test_group_permissions_other_is_last():
    from app.page_views.inspect import group_permissions
    result = group_permissions({"nodot", "bigquery.tables.get", "compute.instances.list"})
    keys = list(result.keys())
    assert keys[-1] == "other"
    assert keys[0] == "bigquery"
    assert keys[1] == "compute"


def test_group_permissions_empty():
    from app.page_views.inspect import group_permissions
    assert group_permissions(set()) == {}


def test_try_it_examples_structure():
    from app.page_views.inspect import _EXAMPLES
    for ex in _EXAMPLES:
        assert "name" in ex
        assert "description" in ex
        assert "role_a" in ex
        assert "diff_mode" in ex
        assert ex["name"]
        assert ex["role_a"].startswith("roles/")
        assert isinstance(ex["diff_mode"], bool)
        if ex["diff_mode"]:
            assert ex.get("role_b", "").startswith("roles/")
        else:
            assert ex.get("role_b") is None or ex.get("role_b", "").startswith("roles/")
