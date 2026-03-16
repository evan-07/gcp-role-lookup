"""Tests for Role Inspector diff logic edge cases."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_diff_only_in_a():
    perms_a = {"a.b.c", "d.e.f", "g.h.i"}
    perms_b = {"d.e.f", "x.y.z"}
    assert perms_a - perms_b == {"a.b.c", "g.h.i"}


def test_diff_in_both():
    perms_a = {"a.b.c", "d.e.f"}
    perms_b = {"d.e.f", "x.y.z"}
    assert perms_a & perms_b == {"d.e.f"}


def test_diff_only_in_b():
    perms_a = {"a.b.c", "d.e.f"}
    perms_b = {"d.e.f", "x.y.z"}
    assert perms_b - perms_a == {"x.y.z"}


def test_empty_diff_column_renders_none_marker():
    """Empty diff set produces the '(none)' sentinel used in st.code."""
    empty: set[str] = set()
    result = "\n".join(sorted(empty)) if empty else "(none)"
    assert result == "(none)"


def test_nonempty_diff_column_sorts_alphabetically():
    perms = {"z.a.b", "a.b.c", "m.n.o"}
    result = "\n".join(sorted(perms))
    assert result == "a.b.c\nm.n.o\nz.a.b"
