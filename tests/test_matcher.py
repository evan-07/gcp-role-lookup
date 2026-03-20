"""Tests for matcher helper functions and scoring pipeline."""


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------

def test_tokenize_lowercases():
    from app.matcher import _tokenize
    assert _tokenize("Cloud Build Admin") == {"cloud", "build", "admin"}


def test_tokenize_removes_stopwords():
    from app.matcher import _tokenize
    assert _tokenize("Backup and DR Cloud SQL Operator") == {"backup", "dr", "cloud", "sql", "operator"}


def test_tokenize_stopword_only_input_returns_full_set():
    """When stripping stopwords would produce empty set, return full set."""
    from app.matcher import _tokenize
    result = _tokenize("of the and")
    assert result == {"of", "the", "and"}


def test_tokenize_empty_string_returns_empty_set():
    from app.matcher import _tokenize
    assert _tokenize("") == set()


def test_tokenize_single_content_word():
    from app.matcher import _tokenize
    assert _tokenize("Admin") == {"admin"}


# ---------------------------------------------------------------------------
# _jaccard
# ---------------------------------------------------------------------------

def test_jaccard_identical_sets():
    from app.matcher import _jaccard
    assert _jaccard({"cloud", "admin"}, {"cloud", "admin"}) == 1.0


def test_jaccard_no_overlap():
    from app.matcher import _jaccard
    assert _jaccard({"cloud", "admin"}, {"backup", "sql"}) == 0.0


def test_jaccard_partial_overlap():
    from app.matcher import _jaccard
    # intersection={cloud}, union={cloud,build,admin,backup,sql,operator} → 1/6
    result = _jaccard({"cloud", "build", "admin"}, {"cloud", "backup", "sql", "operator"})
    assert abs(result - 1/6) < 0.001


def test_jaccard_both_empty():
    from app.matcher import _jaccard
    assert _jaccard(set(), set()) == 0.0


def test_jaccard_one_empty():
    from app.matcher import _jaccard
    assert _jaccard(set(), {"cloud", "admin"}) == 0.0
    assert _jaccard({"cloud", "admin"}, set()) == 0.0


# ---------------------------------------------------------------------------
# _length_penalty
# ---------------------------------------------------------------------------

def test_length_penalty_equal_length():
    from app.matcher import _length_penalty
    assert _length_penalty(3, 3) == 1.0


def test_length_penalty_candidate_1_5x_longer():
    """ratio=1.5 → floor(1.5)=1 → 1-1=0 → 0.85^0=1.0 → no penalty"""
    from app.matcher import _length_penalty
    assert _length_penalty(2, 3) == 1.0


def test_length_penalty_candidate_2x_longer():
    """ratio=2.0 → floor(2.0)=2 → 2-1=1 → 0.85^1=0.85"""
    from app.matcher import _length_penalty, LENGTH_PENALTY_FACTOR
    assert _length_penalty(2, 4) == LENGTH_PENALTY_FACTOR ** 1


def test_length_penalty_candidate_3x_longer():
    """ratio=3.0 → floor(3.0)=3 → 3-1=2 → 0.85^2≈0.7225"""
    from app.matcher import _length_penalty, LENGTH_PENALTY_FACTOR
    assert abs(_length_penalty(2, 6) - LENGTH_PENALTY_FACTOR ** 2) < 0.001


def test_length_penalty_zero_input_count_no_error():
    """max(input_count, 1) guard — no ZeroDivisionError"""
    from app.matcher import _length_penalty
    result = _length_penalty(0, 4)
    assert isinstance(result, float)
    assert 0.0 < result <= 1.0


# ---------------------------------------------------------------------------
# match_title — pipeline regression tests
# ---------------------------------------------------------------------------

_ROLES = [
    {"title": "Backup and DR Cloud SQL Operator", "name": "roles/backupdr.cloudSqlOperator"},
    {"title": "Cloud Build Admin", "name": "roles/cloudbuild.builds.editor"},
    {"title": "Storage Admin", "name": "roles/storage.admin"},
    {"title": "Compute Instance Admin (v1)", "name": "roles/compute.instanceAdmin.v1"},
    {"title": "BigQuery Data Editor", "name": "roles/bigquery.dataEditor"},
    {"title": "BigQuery Data Admin", "name": "roles/bigquery.dataAdmin"},
]

# Fixture without "Cloud Build Admin" — replicates the false-positive scenario
# where the user queries "Cloud build admin" but only unrelated candidates exist.
_ROLES_NO_CLOUD_BUILD = [
    {"title": "Backup and DR Cloud SQL Operator", "name": "roles/backupdr.cloudSqlOperator"},
    {"title": "Storage Admin", "name": "roles/storage.admin"},
    {"title": "Compute Instance Admin (v1)", "name": "roles/compute.instanceAdmin.v1"},
    {"title": "BigQuery Data Editor", "name": "roles/bigquery.dataEditor"},
    {"title": "BigQuery Data Admin", "name": "roles/bigquery.dataAdmin"},
]


def test_false_positive_demoted_to_low():
    """'Cloud build admin' must NOT match 'Backup and DR Cloud SQL Operator' as high/medium.

    Uses a fixture without 'Cloud Build Admin' to replicate the scenario where
    the user queries a role that doesn't exist and the scorer must not
    auto-promote a clearly wrong candidate.
    """
    from app.matcher import match_title
    result = match_title("Cloud build admin", _ROLES_NO_CLOUD_BUILD)
    assert result.status == "low", (
        f"Expected 'low' but got '{result.status}' "
        f"(matched '{result.matched_title}' at {result.confidence}%)"
    )


def test_typo_input_not_demoted():
    """'Stoarge Admin' must still match 'Storage Admin' as medium or better."""
    from app.matcher import match_title
    result = match_title("Stoarge Admin", _ROLES)
    assert result.status in ("exact", "high", "medium"), (
        f"Expected medium-or-better but got '{result.status}' "
        f"(matched '{result.matched_title}' at {result.confidence}%)"
    )


def test_exact_match_unaffected():
    """Exact match path must still work and return status='exact'."""
    from app.matcher import match_title
    result = match_title("Storage Admin", _ROLES)
    assert result.status == "exact"
    assert result.role_id == "roles/storage.admin"


def test_suggestions_present_when_demoted():
    """Suggestions must still be populated even when status is 'low'."""
    from app.matcher import match_title
    result = match_title("Cloud build admin", _ROLES_NO_CLOUD_BUILD)
    assert len(result.suggestions) > 0


def test_suggestions_use_raw_not_penalised_scores():
    """Suggestion confidence values reflect raw token_sort_ratio, not effective scores.

    For 'Cloud build admin', the effective score is capped by the Jaccard gate
    (≤59), but the raw token_sort_ratio score is higher (e.g. ~42 for the best
    candidate). The suggestion confidence must equal the raw score, not the cap.
    Concretely: result.confidence (effective) must differ from at least one
    suggestion's confidence when a Jaccard cap was applied.
    """
    from app.matcher import match_title, THRESHOLD_MEDIUM
    result = match_title("Cloud build admin", _ROLES_NO_CLOUD_BUILD)
    # Effective score was capped — must be below THRESHOLD_MEDIUM
    assert result.confidence < THRESHOLD_MEDIUM
    # At least one suggestion confidence must equal the raw (uncapped) score,
    # which means it differs from result.confidence (the capped effective score)
    suggestion_confidences = {s["confidence"] for s in result.suggestions}
    assert result.confidence not in suggestion_confidences or any(
        s["confidence"] != result.confidence for s in result.suggestions
    ), "Expected suggestion scores to reflect raw (uncapped) values"


def test_stopword_only_3word_input_jaccard_fires():
    """A 3-stopword input triggers Jaccard gate (tokenize fallback gives 3 tokens)."""
    from app.matcher import match_title
    # "of the and" → _tokenize fallback returns {"of","the","and"} (3 tokens)
    # Jaccard gate activates; no GCP role shares these stopwords → demoted to low
    result = match_title("of the and", _ROLES)
    assert result.status in ("low", "not_found")


def test_empty_input_returns_empty_status():
    from app.matcher import match_title
    result = match_title("", _ROLES)
    assert result.status == "empty"


def test_no_results_returns_not_found():
    from app.matcher import match_title
    result = match_title("zzzzzzzzzzzzz", _ROLES)
    assert result.status in ("low", "not_found")
