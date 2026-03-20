"""
matcher.py

Matches user-provided role titles to GCP predefined role IDs.
Uses exact matching first, then rapidfuzz for fuzzy suggestions.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from rapidfuzz import process, fuzz

if TYPE_CHECKING:
    from app.supersession import SupersessionFlag

logger = logging.getLogger(__name__)

# Confidence thresholds
THRESHOLD_HIGH = 85
THRESHOLD_MEDIUM = 60
MAX_SUGGESTIONS = 3
JACCARD_MIN = 0.30
JACCARD_MIN_INPUT_WORDS = 3
LENGTH_PENALTY_FACTOR = 0.85
STOPWORDS = frozenset({
    "and", "or", "the", "of", "for", "a", "an", "to", "in", "with",
})


@dataclass
class MatchResult:
    """Result of a single role title lookup."""

    input_title: str
    matched_title: Optional[str] = None
    role_id: Optional[str] = None
    confidence: Optional[float] = None
    status: str = "not_found"
    suggestions: list[dict] = field(default_factory=list)

    # Attached by supersession.check_supersessions() after matching
    supersession: Optional["SupersessionFlag"] = None

    @property
    def is_exact(self) -> bool:
        """Return True if the match was exact."""
        return self.status == "exact"

    @property
    def has_match(self) -> bool:
        """Return True if any usable match was found."""
        return self.status in ("exact", "high", "medium")


def _build_index(
    roles: list[dict],
) -> tuple[dict[str, str], list[str]]:
    """
    Build a case-insensitive lookup index from roles data.

    Args:
        roles: List of role dicts with 'title' and 'name' keys.

    Returns:
        Tuple of (title_to_id mapping, list of all titles).
    """
    title_to_id: dict[str, str] = {}
    titles: list[str] = []

    for role in roles:
        title = role.get("title", "").strip()
        name = role.get("name", "").strip()
        if title and name:
            title_to_id[title.lower()] = name
            titles.append(title)

    return title_to_id, titles


def _tokenize(title: str) -> set[str]:
    """
    Lowercase and split title into word tokens, removing stopwords.

    If stripping stopwords would produce an empty set, returns the full
    lowercased token set to avoid downstream division-by-zero.
    """
    words = {w.lower() for w in title.split()}
    filtered = words - STOPWORDS
    return filtered if filtered else words


def match_title(
    input_title: str,
    roles: list[dict],
) -> MatchResult:
    """
    Match a single input title to a GCP role.

    Args:
        input_title: The role title string provided by the user.
        roles: List of role dicts loaded from gcp_roles.json.

    Returns:
        MatchResult with status, role_id, and any suggestions.
    """
    if not input_title or not input_title.strip():
        return MatchResult(input_title=input_title, status="empty")

    input_clean = input_title.strip()
    title_to_id, titles = _build_index(roles)

    # --- Exact match (case-insensitive) ---
    exact_key = input_clean.lower()
    if exact_key in title_to_id:
        matched = next(
            t for t in titles if t.lower() == exact_key
        )
        return MatchResult(
            input_title=input_clean,
            matched_title=matched,
            role_id=title_to_id[exact_key],
            confidence=100.0,
            status="exact",
        )

    # --- Fuzzy match ---
    results = process.extract(
        input_clean,
        titles,
        scorer=fuzz.WRatio,
        limit=MAX_SUGGESTIONS,
    )

    if not results:
        return MatchResult(
            input_title=input_clean,
            status="not_found",
        )

    best_title, best_score, _ = results[0]
    best_role_id = title_to_id.get(best_title.lower())

    suggestions = [
        {
            "title": r[0],
            "role_id": title_to_id.get(r[0].lower(), ""),
            "confidence": round(r[1], 1),
        }
        for r in results
    ]

    if best_score >= THRESHOLD_HIGH:
        status = "high"
    elif best_score >= THRESHOLD_MEDIUM:
        status = "medium"
    else:
        status = "low"

    return MatchResult(
        input_title=input_clean,
        matched_title=best_title,
        role_id=best_role_id,
        confidence=round(best_score, 1),
        status=status,
        suggestions=suggestions,
    )


def match_titles_bulk(
    input_text: str,
    roles: list[dict],
) -> list[MatchResult]:
    """
    Match multiple newline-separated role titles.

    Args:
        input_text: Multi-line string; one title per line.
        roles: List of role dicts loaded from gcp_roles.json.

    Returns:
        List of MatchResult objects in input order.
    """
    if not input_text or not input_text.strip():
        return []

    lines = [
        line.strip()
        for line in input_text.splitlines()
        if line.strip()
    ]

    return [match_title(line, roles) for line in lines]