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


# ---------------------------------------------------------------------------
# Deduplicate role IDs
# ---------------------------------------------------------------------------

@dataclass
class RemovedRole:
    """A role removed from the minimal set because it is superseded."""

    role_id: str             # e.g. "roles/storage.objectViewer"
    role_title: str          # e.g. "Storage Object Viewer"
    superseded_by_id: str    # e.g. "roles/storage.admin"
    superseded_by_title: str  # e.g. "Storage Admin"


@dataclass
class DeduplicationResult:
    """Result of deduplicating a list of role IDs."""

    kept: list[str]             # Role IDs in the minimal set
    removed: list[RemovedRole]  # Roles eliminated as redundant
    unknown: list[str]          # Role IDs not found in permissions map


def deduplicate_role_ids(
    role_ids: list[str],
    permissions: dict[str, set[str]],
    roles: list[dict],
) -> DeduplicationResult:
    """
    Return the minimal set of role IDs by removing strict-subset roles.

    Receives only pre-validated ``roles/``-prefixed IDs — prefix validation
    is the caller's responsibility. Role IDs not present in ``permissions``
    are collected as unknown and excluded from comparison.

    For every pair (A, B):
      - If perms(A) ⊂ perms(B)  →  A is superseded by B.
      - Roles with identical permissions: neither is a strict subset; both kept.

    Args:
        role_ids:    Pre-validated ``roles/`` prefixed role IDs.
        permissions: Dict mapping role_id → set of permission strings.
        roles:       Full roles list; used to look up titles by role_id.
                     Each dict must have ``"name"`` and ``"title"`` keys.

    Returns:
        DeduplicationResult with kept, removed, and unknown lists.
    """
    if not role_ids:
        return DeduplicationResult(kept=[], removed=[], unknown=[])

    # Deduplicate inputs while preserving order
    seen: set[str] = set()
    unique_ids: list[str] = []
    for rid in role_ids:
        if rid not in seen:
            seen.add(rid)
            unique_ids.append(rid)
    role_ids = unique_ids

    # Build title lookup: role_id → display title
    id_to_title: dict[str, str] = {
        r["name"]: r["title"]
        for r in roles
        if r.get("name") and r.get("title")
    }

    # Split into known (have permissions data) and unknown
    known: list[str] = []
    unknown: list[str] = []
    for role_id in role_ids:
        if role_id in permissions:
            known.append(role_id)
        else:
            unknown.append(role_id)

    if len(known) < 2:
        return DeduplicationResult(kept=known, removed=[], unknown=unknown)

    # Pairwise strict-subset check — O(N²), N is typically small (≤20)
    superseded_ids: set[str] = set()
    removed: list[RemovedRole] = []

    for i, role_a in enumerate(known):
        if role_a in superseded_ids:
            continue
        perms_a = permissions[role_a]

        for j, role_b in enumerate(known):
            if i == j or role_b in superseded_ids:
                continue
            perms_b = permissions[role_b]

            if perms_a < perms_b:  # strict subset
                superseded_ids.add(role_a)
                removed.append(
                    RemovedRole(
                        role_id=role_a,
                        role_title=id_to_title.get(role_a, role_a),
                        superseded_by_id=role_b,
                        superseded_by_title=id_to_title.get(role_b, role_b),
                    )
                )
                logger.info("Deduplicate: %s ⊂ %s", role_a, role_b)
                break  # One superseder is enough per role.
                       # Note: in a 3-way chain (A⊂B⊂C), A may be annotated as
                       # "superseded by B" even though B is itself superseded.
                       # The kept set is always correct; only the annotation may
                       # point to an intermediate superseder.

    kept = [r for r in known if r not in superseded_ids]
    return DeduplicationResult(kept=kept, removed=removed, unknown=unknown)