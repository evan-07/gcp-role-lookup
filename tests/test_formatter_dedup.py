"""Tests for format_dedup_as_hcl() and format_dedup_as_json()."""

import json

from app.formatter import format_dedup_as_hcl, format_dedup_as_json
from app.supersession import DeduplicationResult, RemovedRole

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RESULT_WITH_REMOVAL = DeduplicationResult(
    kept=["roles/storage.admin"],
    removed=[
        RemovedRole(
            role_id="roles/storage.objectViewer",
            role_title="Storage Object Viewer",
            superseded_by_id="roles/storage.admin",
            superseded_by_title="Storage Admin",
        )
    ],
    unknown=[],
)

RESULT_NO_REMOVAL = DeduplicationResult(
    kept=["roles/storage.admin", "roles/bigquery.dataViewer"],
    removed=[],
    unknown=[],
)

RESULT_EMPTY = DeduplicationResult(kept=[], removed=[], unknown=[])

RESULT_WITH_UNKNOWN = DeduplicationResult(
    kept=["roles/storage.admin"],
    removed=[],
    unknown=["roles/fake.role"],
)


# ---------------------------------------------------------------------------
# format_dedup_as_hcl — annotated mode
# ---------------------------------------------------------------------------

def test_hcl_annotated_kept_role_appears():
    output = format_dedup_as_hcl(RESULT_WITH_REMOVAL, clean=False)
    assert '"roles/storage.admin",' in output


def test_hcl_annotated_removed_role_commented_out():
    output = format_dedup_as_hcl(RESULT_WITH_REMOVAL, clean=False)
    assert '# "roles/storage.objectViewer"' in output


def test_hcl_annotated_removed_role_includes_superseder():
    output = format_dedup_as_hcl(RESULT_WITH_REMOVAL, clean=False)
    assert "Storage Admin" in output


def test_hcl_annotated_no_removal_clean_output():
    output = format_dedup_as_hcl(RESULT_NO_REMOVAL, clean=False)
    assert '"roles/storage.admin",' in output
    assert '"roles/bigquery.dataViewer",' in output
    assert "#" not in output


def test_hcl_annotated_empty_result():
    output = format_dedup_as_hcl(RESULT_EMPTY, clean=False)
    assert output == ""


# ---------------------------------------------------------------------------
# format_dedup_as_hcl — clean mode
# ---------------------------------------------------------------------------

def test_hcl_clean_kept_role_appears():
    output = format_dedup_as_hcl(RESULT_WITH_REMOVAL, clean=True)
    assert '"roles/storage.admin",' in output


def test_hcl_clean_no_comments_for_removed():
    output = format_dedup_as_hcl(RESULT_WITH_REMOVAL, clean=True)
    assert "objectViewer" not in output


def test_hcl_clean_empty_result():
    output = format_dedup_as_hcl(RESULT_EMPTY, clean=True)
    assert output == ""


# ---------------------------------------------------------------------------
# format_dedup_as_json — annotated mode
# ---------------------------------------------------------------------------

def test_json_annotated_is_valid_json():
    output = format_dedup_as_json(RESULT_WITH_REMOVAL, clean=False)
    parsed = json.loads(output)
    assert isinstance(parsed, dict)


def test_json_annotated_kept_array():
    output = format_dedup_as_json(RESULT_WITH_REMOVAL, clean=False)
    parsed = json.loads(output)
    assert parsed["kept"] == ["roles/storage.admin"]


def test_json_annotated_superseded_array():
    output = format_dedup_as_json(RESULT_WITH_REMOVAL, clean=False)
    parsed = json.loads(output)
    assert len(parsed["superseded"]) == 1
    entry = parsed["superseded"][0]
    assert entry["role_id"] == "roles/storage.objectViewer"
    assert entry["superseded_by"] == "roles/storage.admin"
    assert "reason" in entry


def test_json_annotated_no_removal_no_superseded_key():
    output = format_dedup_as_json(RESULT_NO_REMOVAL, clean=False)
    parsed = json.loads(output)
    assert parsed["kept"] == ["roles/storage.admin", "roles/bigquery.dataViewer"]
    assert parsed.get("superseded", []) == []


def test_json_annotated_empty_result():
    output = format_dedup_as_json(RESULT_EMPTY, clean=False)
    parsed = json.loads(output)
    assert parsed["kept"] == []


def test_json_annotated_includes_unknown():
    output = format_dedup_as_json(RESULT_WITH_UNKNOWN, clean=False)
    parsed = json.loads(output)
    assert parsed["unknown"] == ["roles/fake.role"]


# ---------------------------------------------------------------------------
# format_dedup_as_json — clean mode
# ---------------------------------------------------------------------------

def test_json_clean_is_plain_array():
    output = format_dedup_as_json(RESULT_WITH_REMOVAL, clean=True)
    parsed = json.loads(output)
    assert isinstance(parsed, list)
    assert parsed == ["roles/storage.admin"]


def test_json_clean_no_removal_returns_full_array():
    output = format_dedup_as_json(RESULT_NO_REMOVAL, clean=True)
    parsed = json.loads(output)
    assert set(parsed) == {"roles/storage.admin", "roles/bigquery.dataViewer"}


def test_json_clean_empty_result():
    output = format_dedup_as_json(RESULT_EMPTY, clean=True)
    parsed = json.loads(output)
    assert parsed == []
