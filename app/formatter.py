"""
formatter.py

Formats MatchResult objects into Terraform HCL list entries.
Exact matches produce clean output; fuzzy/failed matches are
commented out with inline warnings and confidence levels.
"""

import json

from app.matcher import MatchResult
from app.supersession import DeduplicationResult, RemovedRole


def _confidence_label(score: float) -> str:
    """Return a human-readable confidence label."""
    if score >= 85:
        return "High"
    if score >= 60:
        return "Medium"
    return "Low"


def format_as_terraform(results: list[MatchResult], clean: bool = False) -> str:
    """
    Format a list of MatchResults as Terraform HCL list entries.

    Annotated mode (clean=False):
        Exact matches:
            "roles/bigquery.dataEditor", # BigQuery Data Editor
        Fuzzy matches (high/medium) — included with warning:
            # ⚠️ High confidence (92%) — matched "Storage Admin"
            "roles/storage.admin", # Storage Admin [auto-matched]
        Low confidence / not found — commented out:
            # ❌ No match found for: "Stoarge Adimn"
        Superseded — commented out:
            # "roles/bigquery.dataViewer", # ... [Superseded by ...]

    Clean mode (clean=True):
        Only resolved, non-superseded roles — no comment lines:
            "roles/bigquery.dataEditor",
            "roles/storage.admin",

    Args:
        results: List of MatchResult from matcher.match_titles_bulk.
        clean:   If True, emit only kept role IDs with no comment lines.

    Returns:
        Formatted multi-line string ready to paste into Terraform.
    """
    if not results:
        return ""

    lines: list[str] = []

    for result in results:
        if result.status == "empty":
            continue

        if clean:
            # Emit only resolved, non-superseded roles — no comments
            if result.supersession:
                continue
            if result.status in ("exact", "high", "medium") and result.role_id:
                lines.append(f'"{result.role_id}",')
            continue

        # Superseded roles are commented out regardless of match status
        if result.supersession:
            sup = result.supersession
            lines.append(
                f'# "{result.role_id}", '
                f"# {result.matched_title} "
                f"[Superseded by {sup.superseded_by_title}]"
            )
            continue

        if result.status == "exact":
            lines.append(
                f'"{result.role_id}", '
                f"# {result.matched_title}"
            )

        elif result.status in ("high", "medium"):
            label = _confidence_label(result.confidence or 0)
            lines.append(
                f"# ⚠️ {label} confidence "
                f"({result.confidence}%) — "
                f'matched "{result.matched_title}" '
                f'for input "{result.input_title}"'
            )
            lines.append(
                f'"{result.role_id}", '
                f"# {result.matched_title} [auto-matched]"
            )

        elif result.status == "low":
            lines.append(
                f'# ❌ Low confidence for: "{result.input_title}"'
            )
            if result.suggestions:
                lines.append("# Suggestions:")
                for s in result.suggestions:
                    lines.append(
                        f'#   → "{s["title"]}" '
                        f'→ {s["role_id"]} '
                        f'({s["confidence"]}%)'
                    )

        else:  # not_found
            lines.append(
                f'# ❌ No match found for: "{result.input_title}"'
            )

    return "\n".join(lines)


def format_results_summary(
    results: list[MatchResult],
) -> dict[str, int]:
    """
    Return a summary count of match statuses.

    Args:
        results: List of MatchResult objects.

    Returns:
        Dict with counts for each status category.
    """
    summary = {
        "exact": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "not_found": 0,
        "empty": 0,
        "superseded": 0,
    }
    for r in results:
        if r.status in summary:
            summary[r.status] += 1
        if r.supersession:
            summary["superseded"] += 1
    return summary


# ---------------------------------------------------------------------------
# Deduplicate Roles output formatters
# ---------------------------------------------------------------------------

def format_dedup_as_hcl(
    result: DeduplicationResult,
    clean: bool = False,
) -> str:
    """
    Format a DeduplicationResult as Terraform HCL list entries.

    Annotated mode (clean=False):
        "roles/storage.admin",
        # "roles/storage.objectViewer", # Storage Object Viewer [Superseded by Storage Admin]

    Clean mode (clean=True):
        "roles/storage.admin",

    Args:
        result: DeduplicationResult from deduplicate_role_ids().
        clean:  If True, omit comments for superseded roles.

    Returns:
        Formatted multi-line string ready to paste into Terraform.
    """
    if not result.kept and not result.removed:
        return ""

    lines: list[str] = []

    for role_id in result.kept:
        lines.append(f'"{role_id}",')

    if not clean:
        for removed in result.removed:
            lines.append(
                f'# "{removed.role_id}", '
                f"# {removed.role_title} "
                f"[Superseded by {removed.superseded_by_title}]"
            )

    return "\n".join(lines)


def format_dedup_as_json(
    result: DeduplicationResult,
    clean: bool = False,
) -> str:
    """
    Format a DeduplicationResult as JSON.

    Clean mode (clean=True): plain array of kept role IDs.
    Annotated mode (clean=False): structured object with ``kept`` and
    ``superseded`` arrays so no invalid ``//`` comments are needed.

    Args:
        result: DeduplicationResult from deduplicate_role_ids().
        clean:  If True, return a plain JSON array of kept role IDs.

    Returns:
        JSON string.
    """
    if clean:
        return json.dumps(result.kept, indent=2)

    payload: dict = {"kept": result.kept}
    if result.removed:
        payload["superseded"] = [
            {
                "role_id": r.role_id,
                "superseded_by": r.superseded_by_id,
                "reason": (
                    f"{r.role_title} is a strict subset of {r.superseded_by_title}"
                ),
            }
            for r in result.removed
        ]
    else:
        payload["superseded"] = []
    payload["unknown"] = result.unknown

    return json.dumps(payload, indent=2)
