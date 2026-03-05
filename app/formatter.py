"""
formatter.py

Formats MatchResult objects into Terraform HCL list entries.
Exact matches produce clean output; fuzzy/failed matches are
commented out with inline warnings and confidence levels.
"""

from app.matcher import MatchResult


def _confidence_label(score: float) -> str:
    """Return a human-readable confidence label."""
    if score >= 85:
        return "High"
    if score >= 60:
        return "Medium"
    return "Low"


def format_as_terraform(results: list[MatchResult]) -> str:
    """
    Format a list of MatchResults as Terraform HCL list entries.

    Exact matches:
        "roles/bigquery.dataEditor", # BigQuery Data Editor

    Fuzzy matches (high/medium) — included with warning:
        # ⚠️ High confidence (92%) — matched "Storage Admin"
        "roles/storage.admin", # Storage Admin [auto-matched]

    Low confidence / not found — commented out:
        # ❌ No match found for: "Stoarge Adimn"
        # Suggestions:
        #   - "Storage Admin" → roles/storage.admin (61%)

    Args:
        results: List of MatchResult from matcher.match_titles_bulk.

    Returns:
        Formatted multi-line string ready to paste into Terraform.
    """
    if not results:
        return ""

    lines: list[str] = []

    for result in results:
        if result.status == "empty":
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