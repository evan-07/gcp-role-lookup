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
