# Permission Search Enhancement Design

## Goal

Extend the Permission Search page to support substring matching so users can discover permission strings by typing partial queries, while preserving the existing exact-match behavior.

## Scope

All changes are confined to `app/page_views/permissions.py` and `tests/test_permissions_logic.py`.

---

## Search Behavior

The search activates when the query is **3 or more characters**. Queries shorter than 3 characters show a hint: `"Enter at least 3 characters to search."` and no results.

Two independent lookups run on every qualifying query:

1. **Exact match** — roles where the query is a member of their permission set (current behavior, case-insensitive)
2. **Partial match** — permission strings (across all roles) that contain the query as a case-insensitive substring, excluding the exact query itself

---

## Results Display

Results are shown in two separate labeled sections. Each section is only rendered if it has results.

### Exact Matches Section

Shown when the query is a known exact permission string (i.e., at least one role grants it exactly).

Identical to the current output:
- Caption: `"N role(s) grant this permission exactly."`
- Table: Role ID, Role Title, Terraform String columns
- Terraform block: `st.code` with newline-separated quoted role IDs
- Uses existing `sort_key()` for role ordering

### Partial Matches Section

Shown when 1 or more permission strings contain the query as a substring (and the query is 3+ characters).

Output:
- Caption: `"N permission string(s) contain '{query}'."` — if results are truncated the caption reads `"N permission string(s) contain '{query}'. Showing first 100 — refine your query to narrow results."`
- Table with two columns: **Permission** (lowercased permission string) and **# Roles** (count of roles granting it)
- Rows sorted by `# Roles` descending, then permission string alphabetically
- Maximum 100 rows displayed
- The exact query string is excluded from this table (it appears in Exact Matches if applicable)

### No Results

If both sections are empty: `st.info(f"No permissions or roles found for: {query}")`

---

## Pure Functions (module-level, testable)

### Existing: `sort_key(role_id: str) -> tuple`
Unchanged.

### New: `find_exact_matches(query: str, permissions: dict[str, set[str]]) -> list[str]`
Returns sorted list of role IDs whose permission set contains `query` exactly (case-insensitive).

```python
def find_exact_matches(query: str, permissions: dict[str, set[str]]) -> list[str]:
    q = query.lower()
    return sorted(
        [rid for rid, perms in permissions.items() if q in {p.lower() for p in perms}],
        key=sort_key,
    )
```

### New: `find_partial_matches(query: str, permissions: dict[str, set[str]], limit: int = 100) -> tuple[list[tuple[str, int]], int]`
Returns `(rows, total_count)` where `rows` is a list of `(permission_string, role_count)` tuples for permissions containing the query as a substring (excluding exact match), sorted by role_count descending then alphabetically, capped at `limit`. `total_count` is the full count before capping.

All permission strings are lowercased before counting. If the source data contains the same permission with different casings across roles, they are merged into one lowercased key — this is intentional normalisation.

```python
def find_partial_matches(
    query: str, permissions: dict[str, set[str]], limit: int = 100
) -> tuple[list[tuple[str, int]], int]:
    q = query.lower()
    counts: dict[str, int] = {}
    for perms in permissions.values():
        for p in perms:
            pl = p.lower()
            if q in pl and pl != q:
                counts[pl] = counts.get(pl, 0) + 1
    results = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return results[:limit], len(counts)
```

---

## Updated render() Flow

```
query = st.session_state["permission_search_query"].strip().lower()

if len(query) < 3:
    if query:  # non-empty but too short
        st.info("Enter at least 3 characters to search.")
    return

exact_matches = find_exact_matches(query, permissions)
partial_rows, partial_total = find_partial_matches(query, permissions)

if not exact_matches and not partial_rows:
    st.info(f"No permissions or roles found for: {query}")
    return

# Exact matches section
if exact_matches:
    st.markdown("<div class='section-label'>Exact Matches</div>", unsafe_allow_html=True)
    st.caption(f"{len(exact_matches)} role(s) grant this permission exactly.")
    # ... table + terraform block (same as current) ...

# Partial matches section
if partial_rows:
    st.markdown("<div class='section-label'>Partial Matches</div>", unsafe_allow_html=True)
    truncation_note = (
        f" Showing first {len(partial_rows)} — refine your query to narrow results."
        if partial_total > len(partial_rows) else ""
    )
    st.caption(f"{partial_total} permission string(s) contain '{query}'.{truncation_note}")
    # ... table with Permission + # Roles columns ...
```

---

## Backwards Compatibility

Exact-match behavior is preserved. Users who type a full permission string get identical output in the Exact Matches section. The minimum 3-character threshold is the only behaviour change for very short queries (previously showed "No roles found" immediately; now shows a hint).

---

## Testing

New and modified tests in `tests/test_permissions_logic.py`. Import:

```python
from app.page_views.permissions import find_exact_matches, find_partial_matches, sort_key
```

Tests for `find_exact_matches`:
- `test_find_exact_matches_hit` — query matches a permission exactly
- `test_find_exact_matches_miss` — query not in any permission set
- `test_find_exact_matches_case_insensitive` — stored permissions uppercased, query lowercase

Tests for `find_partial_matches`:
- `test_find_partial_matches_substring` — query is substring of multiple permissions
- `test_find_partial_matches_excludes_exact` — exact match excluded from partial results
- `test_find_partial_matches_sorted_by_role_count` — higher role count appears first
- `test_find_partial_matches_limit` — results capped at limit, total_count reflects full count
- `test_find_partial_matches_empty` — no matches returns empty list and zero total

---

## Files Modified

| File | Change |
|------|--------|
| `app/page_views/permissions.py` | Extract `find_exact_matches()` and `find_partial_matches()` as module-level functions; update `render()` to use them and display both sections |
| `tests/test_permissions_logic.py` | Add 8 new tests for the two new functions |
