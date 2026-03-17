# Find Smallest Role Design

## Goal

Add a new "Find Smallest Role" page that accepts a list of required GCP permissions and finds the role(s) that grant all of them with the fewest extra permissions (least privilege). When no single role covers all requirements, shows the top partial matches ranked by coverage.

## Scope

- New file: `app/page_views/find_role.py`
- New file: `tests/test_find_role_logic.py`
- Modify: `app/main.py` (session state key, nav button, dispatch)

---

## Page: Find Smallest Role

### Input

A `st.text_area` (one permission per line) with a "Find Role →" button. Session state key: `find_role_input` (str, default `""`). Input is parsed by the module-level `parse_permissions_input()` function (see below) before searching.

### Unavailability guard

If `permissions` is empty, show a warning and return (same pattern as other pages). No guard needed for `roles` since role titles are optional for this feature (role ID is sufficient).

### Results: Exact Matches

Shown when at least one role grants all required permissions.

- Section label: `"Exact Matches"`
- Caption: `"N role(s) grant all M required permissions."`
- Table columns: **Role ID**, **Title**, **Total Permissions**
- Sorted by `(tier, total_permission_count)` ascending — smallest role first within each tier:
  - Tier 0: `roles/` (predefined)
  - Tier 1: `projects/`
  - Tier 2: `organizations/`
  - Tier 3: other

### Results: Partial Matches

Shown **only when there are no exact matches**. Displays the top 10 roles by coverage.

- Section label: `"Partial Matches"`
- Caption: `"No single role grants all M permissions. Top partial matches:"`
- Table columns: **Role ID**, **Title**, **Covers**, **Total Permissions**
  - **Covers**: string formatted as `"X / M"` (e.g. `"3 / 5"`)
- Sorted by `(-covered_count, tier, total_permission_count)` — most coverage first, tie-broken by tier then size
- Maximum 10 rows

### No Results

If both sections are empty (no role grants even one required permission):
`st.info("No roles found granting any of the required permissions.")`

### Empty / Invalid Input

If the text area is empty or contains no valid permission strings after parsing:
Return without rendering results (same pattern as other search pages).

---

## Pure Function: parse_permissions_input()

Lives at module level in `find_role.py`.

```python
def parse_permissions_input(raw: str) -> set[str]:
    """Parse raw text area input into a set of lowercased permission strings.

    Strips whitespace, lowercases, discards blank lines and duplicates.
    """
    return {line.strip().lower() for line in raw.splitlines() if line.strip()}
```

---

## Pure Function: find_smallest_roles()

Lives at module level in `find_role.py`, independently testable.

```python
def find_smallest_roles(
    required: set[str],
    permissions: dict[str, set[str]],
    role_title_map: dict[str, str],
    partial_limit: int = 10,
) -> tuple[list[dict], list[dict]]:
    """Find roles that grant all (or most) of the required permissions.

    Returns (exact_matches, partial_matches) as lists of dicts:
      {"role_id": str, "title": str, "total_perms": int, "covered": int}

    exact_matches: roles where required ⊆ role_perms, sorted by (tier, total_perms)
    partial_matches: top partial_limit roles by covered count (only when exact is empty),
                     sorted by (-covered, tier, total_perms)
    """
    ...
```

### Tier helper (module-level)

```python
def _tier(role_id: str) -> int:
    if role_id.startswith("roles/"): return 0
    if role_id.startswith("projects/"): return 1
    if role_id.startswith("organizations/"): return 2
    return 3
```

### Algorithm

```python
def find_smallest_roles(required, permissions, role_title_map, partial_limit=10):
    if not required:
        return [], []

    exact, partial = [], []

    for role_id, perms in permissions.items():
        covered = len(required & perms)
        if covered == 0:
            continue
        entry = {
            "role_id": role_id,
            "title": role_title_map.get(role_id, "(custom role)"),
            "total_perms": len(perms),
            "covered": covered,
        }
        if required.issubset(perms):
            exact.append(entry)
        else:
            partial.append(entry)

    exact.sort(key=lambda x: (_tier(x["role_id"]), x["total_perms"], x["role_id"]))

    if exact:
        return exact, []

    partial.sort(key=lambda x: (-x["covered"], _tier(x["role_id"]), x["total_perms"], x["role_id"]))
    return [], partial[:partial_limit]
```

Note: `partial` is only returned when `exact` is empty (spec requirement C — show both but partial only when no exact match).

---

## Session State

One new key added to `_DEFAULTS` in `app/main.py`:

```python
"find_role_input": "",
```

Results are computed inline on button click (same pattern as Resolve Titles). No additional state keys needed.

---

## Navigation

In `app/main.py`:

1. Add `"find_role_input": ""` to `_DEFAULTS`
2. Add a fourth nav button in the sidebar: `"Find Smallest Role"` (active when `page == "find_role"`)
3. Add dispatch: `elif st.session_state["page"] == "find_role": from page_views.find_role import render as render_find_role; render_find_role(roles_data, permissions_data)`

---

## Testing

New file `tests/test_find_role_logic.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
```

Tests for `parse_permissions_input()`:
- `test_parse_trims_whitespace` — `"  a.b.c  "` → `{"a.b.c"}`
- `test_parse_lowercases` — `"BigQuery.Tables.Get"` → `{"bigquery.tables.get"}`
- `test_parse_discards_blank_lines` — `"a.b\n\n\nc.d"` → `{"a.b", "c.d"}`
- `test_parse_deduplicates` — `"a.b\na.b"` → `{"a.b"}`

Tests for `_tier()`:
- `test_tier_predefined` — `roles/x` → 0
- `test_tier_project` — `projects/x` → 1
- `test_tier_org` — `organizations/x` → 2
- `test_tier_other` — `unknown/x` → 3

Tests for `find_smallest_roles()`:
- `test_exact_match_found` — one role grants all required perms, appears in exact list
- `test_exact_match_sorted_by_size` — two exact-match roles both in `roles/` tier, smaller total_perms ranks first
- `test_exact_match_tier_before_size` — predefined role (`roles/`) ranked before project role (`projects/`) even if project role has fewer total permissions
- `test_no_exact_returns_partial` — no exact match, partial list returned sorted by coverage count descending
- `test_partial_limit` — more than 10 partial matches, only top 10 returned
- `test_empty_required` — empty required set returns ([], [])
- `test_no_coverage` — no role covers any required permission, both lists empty
- `test_exact_suppresses_partial` — when exact matches exist, partial list is always empty

---

## Files Modified / Created

| File | Change |
|------|--------|
| `app/page_views/find_role.py` | New: `parse_permissions_input()`, `_tier()`, `find_smallest_roles()`, `render()` |
| `tests/test_find_role_logic.py` | New: 16 unit tests (4 parse + 4 tier + 8 find_smallest_roles) |
| `app/main.py` | Add `find_role_input` to `_DEFAULTS`; add nav button; add dispatch |
