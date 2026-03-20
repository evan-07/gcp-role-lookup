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
