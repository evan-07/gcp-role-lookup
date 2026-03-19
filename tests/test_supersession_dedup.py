"""Tests for deduplicate_role_ids() in supersession.py."""

from app.supersession import deduplicate_role_ids

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROLES = [
    {"name": "roles/storage.admin", "title": "Storage Admin"},
    {"name": "roles/storage.objectViewer", "title": "Storage Object Viewer"},
    {"name": "roles/storage.objectCreator", "title": "Storage Object Creator"},
    {"name": "roles/bigquery.dataEditor", "title": "BigQuery Data Editor"},
    {"name": "roles/bigquery.dataViewer", "title": "BigQuery Data Viewer"},
]

# storage.admin has all perms of objectViewer and more → objectViewer superseded
# bigquery.dataEditor has all perms of dataViewer and more → dataViewer superseded
PERMISSIONS = {
    "roles/storage.admin": {"storage.buckets.create", "storage.objects.create", "storage.objects.get", "storage.objects.list"},
    "roles/storage.objectViewer": {"storage.objects.get", "storage.objects.list"},
    "roles/storage.objectCreator": {"storage.objects.create"},
    "roles/bigquery.dataEditor": {"bigquery.tables.create", "bigquery.tables.delete", "bigquery.tables.get"},
    "roles/bigquery.dataViewer": {"bigquery.tables.get"},
}


# ---------------------------------------------------------------------------
# Basic supersession
# ---------------------------------------------------------------------------

def test_subset_role_is_removed():
    """roles/storage.objectViewer ⊂ roles/storage.admin → objectViewer removed."""
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/storage.objectViewer"],
        PERMISSIONS,
        ROLES,
    )
    assert result.kept == ["roles/storage.admin"]
    assert len(result.removed) == 1
    assert result.removed[0].role_id == "roles/storage.objectViewer"
    assert result.removed[0].superseded_by_id == "roles/storage.admin"
    assert result.unknown == []


def test_removed_role_includes_titles():
    """RemovedRole contains both the superseded title and the superseder title."""
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/storage.objectViewer"],
        PERMISSIONS,
        ROLES,
    )
    removed = result.removed[0]
    assert removed.role_title == "Storage Object Viewer"
    assert removed.superseded_by_title == "Storage Admin"


def test_multiple_supersessions():
    """Two pairs — each smaller role is removed."""
    result = deduplicate_role_ids(
        [
            "roles/storage.admin",
            "roles/storage.objectViewer",
            "roles/bigquery.dataEditor",
            "roles/bigquery.dataViewer",
        ],
        PERMISSIONS,
        ROLES,
    )
    assert set(result.kept) == {"roles/storage.admin", "roles/bigquery.dataEditor"}
    assert len(result.removed) == 2
    assert result.unknown == []


# ---------------------------------------------------------------------------
# No supersession
# ---------------------------------------------------------------------------

def test_disjoint_roles_all_kept():
    """Roles with no permission overlap — all kept."""
    result = deduplicate_role_ids(
        ["roles/storage.objectCreator", "roles/bigquery.dataViewer"],
        PERMISSIONS,
        ROLES,
    )
    assert set(result.kept) == {"roles/storage.objectCreator", "roles/bigquery.dataViewer"}
    assert result.removed == []
    assert result.unknown == []


def test_identical_permissions_both_kept():
    """Two roles with identical permissions — neither is a strict subset, both kept."""
    permissions = {
        "roles/storage.admin": {"storage.objects.get"},
        "roles/storage.objectViewer": {"storage.objects.get"},
    }
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/storage.objectViewer"],
        permissions,
        ROLES,
    )
    assert set(result.kept) == {"roles/storage.admin", "roles/storage.objectViewer"}
    assert result.removed == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_single_role_is_kept():
    """Single input role — nothing to compare, returned as kept."""
    result = deduplicate_role_ids(
        ["roles/storage.admin"],
        PERMISSIONS,
        ROLES,
    )
    assert result.kept == ["roles/storage.admin"]
    assert result.removed == []
    assert result.unknown == []


def test_empty_input():
    """Empty input list — empty result."""
    result = deduplicate_role_ids([], PERMISSIONS, ROLES)
    assert result.kept == []
    assert result.removed == []
    assert result.unknown == []


def test_unknown_role_id():
    """Role ID not in permissions map → collected as unknown."""
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/nonexistent.role"],
        PERMISSIONS,
        ROLES,
    )
    assert result.kept == ["roles/storage.admin"]
    assert result.unknown == ["roles/nonexistent.role"]
    assert result.removed == []


def test_empty_permissions_map():
    """Empty permissions dict — all roles unknown (no data to compare)."""
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/storage.objectViewer"],
        {},
        ROLES,
    )
    assert result.kept == []
    assert result.removed == []
    assert set(result.unknown) == {"roles/storage.admin", "roles/storage.objectViewer"}


def test_all_unknown_roles():
    """All inputs missing from permissions — all collected as unknown."""
    result = deduplicate_role_ids(
        ["roles/fake.one", "roles/fake.two"],
        PERMISSIONS,
        ROLES,
    )
    assert result.kept == []
    assert result.removed == []
    assert set(result.unknown) == {"roles/fake.one", "roles/fake.two"}


def test_duplicate_input_ids_deduplicated():
    """Duplicate role IDs in input are treated as a single role."""
    result = deduplicate_role_ids(
        ["roles/storage.admin", "roles/storage.admin", "roles/storage.objectViewer"],
        PERMISSIONS,
        ROLES,
    )
    assert result.kept == ["roles/storage.admin"]
    assert len(result.removed) == 1
