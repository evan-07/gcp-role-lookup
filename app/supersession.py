"""
supersession.py

Post-processing step that detects when a resolved role's permissions
are a strict subset of another resolved role in the same input batch.

Operates only on the current batch — no global lookups.
Attaches SupersessionFlag to affected MatchResult objects in-place.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from app.matcher import MatchResult

logger = logging.getLogger(__name__)


@dataclass
class SupersessionFlag:
    """Marks a role as redundant within the current batch."""

    superseded_by_id: str    # e.g. "roles/bigquery.dataEditor"
    superseded_by_title: str  # e.g. "BigQuery Data Editor"


def check_supersessions(
    results: list[MatchResult],
    permissions: dict[str, set[str]],
    roles: list[dict],
) -> list[MatchResult]:
    """
    Detect strict-subset supersession within the resolved batch.

    For every pair (A, B) of successfully resolved roles in the batch:
      - If perms(A) ⊂ perms(B), flag A as superseded by B.

    Attaches a SupersessionFlag to each superseded MatchResult.
    Results without permissions data are silently skipped.

    Args:
        results:     Resolved MatchResult list from match_titles_bulk.
        permissions: Dict mapping role_id → set of permission strings.
        roles:       Full roles list, used to look up titles by role_id.

    Returns:
        The same results list with SupersessionFlag attached where
        applicable (mutates in-place and also returns for chaining).
    """
    if not permissions:
        logger.warning(
            "permissions map is empty — supersession check skipped."
        )
        return results

    # Build a title lookup from role_id for display purposes
    id_to_title: dict[str, str] = {
        r["name"]: r["title"] for r in roles
        if r.get("name") and r.get("title")
    }

    # Collect only resolved results that have a role_id + permissions
    resolved = [
        r for r in results
        if r.role_id and r.role_id in permissions
        and r.status not in ("empty", "not_found", "low")
    ]

    if len(resolved) < 2:
        return results

    # Pairwise strict-subset check — O(N^2), N is typically small (≤20)
    for i, result_a in enumerate(resolved):
        if result_a.supersession:
            # Already flagged by an earlier pair — skip
            continue

        perms_a = permissions[result_a.role_id]

        for j, result_b in enumerate(resolved):
            if i == j:
                continue
            if result_b.supersession:
                continue

            perms_b = permissions[result_b.role_id]

            # Strict subset: A ⊂ B (A is proper subset of B)
            if perms_a < perms_b:
                title_b = id_to_title.get(
                    result_b.role_id,
                    result_b.matched_title or result_b.role_id,
                )
                result_a.supersession = SupersessionFlag(
                    superseded_by_id=result_b.role_id,
                    superseded_by_title=title_b,
                )
                logger.info(
                    "Supersession: %s ⊂ %s",
                    result_a.role_id,
                    result_b.role_id,
                )
                break  # One superseder is enough per role

    return results