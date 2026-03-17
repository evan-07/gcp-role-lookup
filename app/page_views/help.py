"""
help.py

Help page — reads selected sections from README.md and renders them.
README.md is the single source of truth; this page has no content of its own.
"""

from pathlib import Path

import streamlit as st

HELP_SECTIONS = [
    "Pages",
    "How Matching Works",
    "Supersession Detection",
    "Refresh Role and Permission Data",
]


def render() -> None:
    """Render the Help page by extracting sections from README.md."""
    readme_path = Path(__file__).parent.parent.parent / "README.md"
    try:
        content = readme_path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read README.md: {exc}")
        return

    # Prepend \n so a section at position 0 is handled uniformly.
    # Result: [preamble, "Heading1\nbody1", "Heading2\nbody2", ...]
    parts = ("\n" + content).split("\n## ")
    # parts[0] is the preamble — discard it.
    sections: dict[str, str] = {}
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        sections[heading.strip()] = body

    first = True
    for name in HELP_SECTIONS:
        if not first:
            st.divider()
        first = False

        st.markdown(
            f"<div class='app-header'><div><h1>{name}</h1></div></div>",
            unsafe_allow_html=True,
        )
        if name not in sections:
            st.warning(f"Section '{name}' not found in README.md.")
        else:
            st.markdown(sections[name], unsafe_allow_html=True)
