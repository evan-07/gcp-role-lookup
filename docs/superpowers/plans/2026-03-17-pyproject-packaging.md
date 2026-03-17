# pyproject.toml Packaging Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate all `sys.path.insert` hacks by making `app` a properly installed Python package via `pyproject.toml`, and standardize pytest configuration so `pytest` works with no arguments.

**Architecture:** Add `pyproject.toml` at the repo root for metadata and pytest config. Create `app/__init__.py` to make `app` a proper package. Install with `pip install -e . --no-deps` to register it. Then update all bare `page_views.*` imports to `app.page_views.*` and strip all `sys.path.insert` lines.

**Tech Stack:** Python 3.12, setuptools, pytest 8.3.4

**Spec:** `docs/superpowers/specs/2026-03-17-pyproject-packaging-design.md`

---

## Chunk 1: Foundation

### Task 1: Create pyproject.toml and app/__init__.py, install package

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`

This is the foundation. All path-hack removal depends on the package being registered first. Do not remove any hacks yet.

- [ ] **Step 1: Verify the baseline — all 43 tests pass before any changes**

  Run from repo root with the venv activated:
  ```bash
  pytest
  ```
  Expected output ends with: `43 passed`

  If any tests fail, stop and fix them before continuing.

- [ ] **Step 2: Create `pyproject.toml` at the repo root**

  Create `pyproject.toml` with this exact content:

  ```toml
  [build-system]
  requires = ["setuptools>=68"]
  build-backend = "setuptools.build_meta"

  [project]
  name = "gcp-role-lookup"
  version = "1.0.0"
  requires-python = ">=3.12"
  dependencies = []

  [tool.pytest.ini_options]
  testpaths = ["tests"]
  addopts = "-v"
  ```

  `dependencies = []` is intentional. All pins are managed by `requirements.txt`.

- [ ] **Step 3: Create `app/__init__.py` as an empty file**

  Create `app/__init__.py` with no content (empty file). This makes `app` a proper Python package so `from app.X import Y` works after the editable install.

- [ ] **Step 4: Install the package in editable mode**

  With the venv activated, run from the repo root:
  ```bash
  pip install -e . --no-deps
  ```

  Expected: pip installs the package without installing dependencies (they're already installed from `requirements.txt`). You should see output like:
  ```
  Successfully installed gcp-role-lookup-1.0.0
  ```

- [ ] **Step 5: Verify all 43 tests still pass**

  ```bash
  pytest
  ```
  Expected: `43 passed`

  The `pyproject.toml` sets `testpaths = ["tests"]` and `addopts = "-v"`, so running bare `pytest` is now equivalent to `pytest tests/ -v`.

- [ ] **Step 6: Commit**

  ```bash
  git add pyproject.toml app/__init__.py
  git commit -m "feat: add pyproject.toml and app/__init__.py for proper package structure"
  ```

---

## Chunk 2: Fix test file imports

### Task 2: Update test_permissions_logic.py — update imports and remove path hack

**Files:**
- Modify: `tests/test_permissions_logic.py`

This file uses `sys.path.insert(0, str(Path(__file__).parent.parent / "app"))` to put the `app/` directory on the path, which lets it import `from page_views.permissions import ...`. With the package installed, the correct form is `from app.page_views.permissions import ...`.

- [ ] **Step 1: Remove the path hack lines from `tests/test_permissions_logic.py`**

  Remove these three lines from the top of the file:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
  ```

- [ ] **Step 2: Update all bare `page_views.permissions` imports in the same file**

  Every test function in this file has a deferred import like:
  ```python
  from page_views.permissions import sort_key
  from page_views.permissions import find_exact_matches
  from page_views.permissions import find_partial_matches
  ```

  Change every occurrence to use the `app.` prefix:
  ```python
  from app.page_views.permissions import sort_key
  from app.page_views.permissions import find_exact_matches
  from app.page_views.permissions import find_partial_matches
  ```

  There are multiple test functions — update every occurrence in the file. Use find-and-replace: replace `from page_views.permissions import` with `from app.page_views.permissions import`.

- [ ] **Step 3: Run the permissions tests to verify**

  ```bash
  pytest tests/test_permissions_logic.py
  ```
  Expected: all permissions tests pass (16 tests).

- [ ] **Step 4: Run all tests**

  ```bash
  pytest
  ```
  Expected: `43 passed`

- [ ] **Step 5: Commit**

  ```bash
  git add tests/test_permissions_logic.py
  git commit -m "refactor: remove sys.path hack and update imports in test_permissions_logic.py"
  ```

---

### Task 3: Update test_find_role_logic.py — update imports and remove path hack

**Files:**
- Modify: `tests/test_find_role_logic.py`

Same pattern as Task 2. This file uses the same `app/`-directory path hack and bare `page_views.find_role` imports.

- [ ] **Step 1: Remove the path hack lines from `tests/test_find_role_logic.py`**

  Remove these three lines from the top of the file:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
  ```

- [ ] **Step 2: Update all bare `page_views.find_role` imports in the same file**

  Change every deferred import like:
  ```python
  from page_views.find_role import parse_permissions_input
  from page_views.find_role import _tier
  from page_views.find_role import find_smallest_roles
  ```

  To:
  ```python
  from app.page_views.find_role import parse_permissions_input
  from app.page_views.find_role import _tier
  from app.page_views.find_role import find_smallest_roles
  ```

  Use find-and-replace: replace `from page_views.find_role import` with `from app.page_views.find_role import`.

- [ ] **Step 3: Run the find_role tests to verify**

  ```bash
  pytest tests/test_find_role_logic.py
  ```
  Expected: all find_role tests pass (16 tests).

- [ ] **Step 4: Run all tests**

  ```bash
  pytest
  ```
  Expected: `43 passed`

- [ ] **Step 5: Commit**

  ```bash
  git add tests/test_find_role_logic.py
  git commit -m "refactor: remove sys.path hack and update imports in test_find_role_logic.py"
  ```

---

### Task 4: Remove path hacks from test_inspect_logic.py and test_role_loader.py

**Files:**
- Modify: `tests/test_inspect_logic.py`
- Modify: `tests/test_role_loader.py`

These two files already have correct `app.`-prefixed imports. Only the path hack lines need removing — no import updates required.

- [ ] **Step 1: Remove path hack from `tests/test_inspect_logic.py`**

  Remove these three lines from the top of the file:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent.parent))
  ```

  The deferred imports inside test functions (e.g. `from app.page_views.inspect import group_permissions`) are already correct — leave them as-is.

- [ ] **Step 2: Remove path hack from `tests/test_role_loader.py`**

  Remove these three lines from the top of the file:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent.parent))
  ```

  The `import app.role_loader as rl` inside the test function is already correct — leave it as-is.

- [ ] **Step 3: Run all tests**

  ```bash
  pytest
  ```
  Expected: `43 passed`

- [ ] **Step 4: Commit**

  ```bash
  git add tests/test_inspect_logic.py tests/test_role_loader.py
  git commit -m "refactor: remove sys.path hacks from test_inspect_logic.py and test_role_loader.py"
  ```

---

## Chunk 3: Fix app source files

### Task 5: Fix app/main.py — remove path hack and update dispatch imports

**Files:**
- Modify: `app/main.py`

`main.py` has a path hack that adds the repo root to `sys.path`. It also has four deferred dispatch imports using bare `page_views.*` that relied on that hack. Both must be fixed together — if you remove the hack without updating the imports, the dispatch block will fail at runtime.

- [ ] **Step 1: Remove three specific lines from `app/main.py`**

  The lines to remove are **not contiguous** — `import logging` sits between `import sys` and `from pathlib import Path` and must be kept. Remove each line individually:

  | Line | Content | Action |
  |------|---------|--------|
  | 9  | `import sys` | **remove** |
  | 10 | `import logging` | **keep** — used later for `logger` |
  | 11 | `from pathlib import Path` | **remove** |
  | 15 | `sys.path.insert(0, str(Path(__file__).parent.parent))` | **remove** |

  After removing lines 9, 11, and 15, the top of the file should look like:
  ```python
  import logging

  import streamlit as st

  from app.role_loader import load_roles, load_permissions, clear_all_caches, refresh_roles_from_api
  ```

- [ ] **Step 2: Update the four dispatch imports at the bottom of `app/main.py`**

  Find the `if/elif` dispatch block near the bottom of the file. The four deferred imports currently read:
  ```python
  from page_views.resolve import render as render_resolve
  from page_views.inspect import render as render_inspect
  from page_views.permissions import render as render_permissions
  from page_views.find_role import render as render_find_role
  ```

  Update each to include the `app.` prefix:
  ```python
  from app.page_views.resolve import render as render_resolve
  from app.page_views.inspect import render as render_inspect
  from app.page_views.permissions import render as render_permissions
  from app.page_views.find_role import render as render_find_role
  ```

  The `from app.role_loader import ...` line near the top already has the `app.` prefix — leave it unchanged.

- [ ] **Step 3: Run all tests**

  ```bash
  pytest
  ```
  Expected: `43 passed`

  Note: the tests don't exercise the Streamlit dispatch block directly, but a syntax error or import error in `main.py` would surface here if it's imported transitively.

- [ ] **Step 4: Commit**

  ```bash
  git add app/main.py
  git commit -m "refactor: remove sys.path hack and update dispatch imports in main.py"
  ```

---

### Task 6: Remove path hacks from all four page_views files

**Files:**
- Modify: `app/page_views/resolve.py`
- Modify: `app/page_views/inspect.py`
- Modify: `app/page_views/permissions.py`
- Modify: `app/page_views/find_role.py`

Each file has `import sys`, `from pathlib import Path`, and `sys.path.insert(0, str(Path(__file__).parent.parent.parent))`. These lines are **not always contiguous** — other imports may appear between them. Remove each line individually.

- [ ] **Step 1: Remove path hack from `app/page_views/resolve.py`**

  Find and remove these three lines (they appear on lines 8, 9, and 14 — not consecutive):
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent.parent.parent))
  ```

  Neither `sys` nor `Path` is used elsewhere in `resolve.py` — safe to remove both imports.

- [ ] **Step 2: Remove path hack from `app/page_views/inspect.py`**

  Find and remove the same three lines. In this file, `from collections import defaultdict` sits between `import sys` and `from pathlib import Path` — remove only the three hack lines, leave `defaultdict`.

  Neither `sys` nor `Path` is used elsewhere in `inspect.py`.

- [ ] **Step 3: Remove path hack from `app/page_views/permissions.py`**

  Find and remove the same three lines. In this file, `import streamlit as st` appears between `from pathlib import Path` and `sys.path.insert(...)` — remove only the three hack lines, leave streamlit.

  Neither `sys` nor `Path` is used elsewhere in `permissions.py`.

- [ ] **Step 4: Remove path hack from `app/page_views/find_role.py`**

  Find and remove the same three lines. In this file, `import streamlit as st` appears between `from pathlib import Path` and `sys.path.insert(...)` — remove only the three hack lines, leave streamlit.

  Neither `sys` nor `Path` is used elsewhere in `find_role.py`.

- [ ] **Step 5: Run all tests**

  ```bash
  pytest
  ```
  Expected: `43 passed`

- [ ] **Step 6: Verify no sys.path hacks remain anywhere in the codebase**

  ```bash
  grep -r "sys.path.insert" app/ tests/
  ```
  Expected: no output (no matches).

- [ ] **Step 7: Commit**

  ```bash
  git add app/page_views/resolve.py app/page_views/inspect.py app/page_views/permissions.py app/page_views/find_role.py
  git commit -m "refactor: remove sys.path hacks from all page_views modules"
  ```

---

## Chunk 4: Update setup scripts and docs

### Task 7: Update setup_linux.sh, setup_windows.ps1, and README.md

**Files:**
- Modify: `setup_linux.sh`
- Modify: `setup_windows.ps1`
- Modify: `README.md`

Add `pip install -e . --no-deps` to the setup flow so new users get the package registered automatically.

- [ ] **Step 1: Update `setup_linux.sh`**

  Inside the `if [ "$SKIP_VENV" = false ]` block, find the two consecutive lines:
  ```bash
  pip install -r requirements.txt --prefer-binary
  success "Dependencies installed"
  ```

  Insert two new lines between them so the block reads:
  ```bash
  pip install -r requirements.txt --prefer-binary
  pip install -e . --no-deps
  success "Package installed in editable mode"
  success "Dependencies installed"
  ```

- [ ] **Step 2: Update `setup_windows.ps1`**

  Find the `pip install -r requirements.txt` block and its success call:
  ```powershell
  & pip install -r requirements.txt --prefer-binary --quiet
  if ($LASTEXITCODE -ne 0) {
      Write-Error_ "Failed to install dependencies."
      exit 1
  }
  Write-Success "Dependencies installed"
  ```

  Add the editable install after the `Write-Success "Dependencies installed"` line:
  ```powershell
  & pip install -e . --no-deps --quiet
  if ($LASTEXITCODE -ne 0) {
      Write-Error_ "Failed to install package in editable mode."
      exit 1
  }
  Write-Success "Package installed in editable mode"
  ```

- [ ] **Step 3: Update `README.md` — Windows manual setup (Option B)**

  Find the Windows Option B block:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  streamlit run app/main.py
  ```

  Add the editable install line:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  pip install -e . --no-deps
  streamlit run app/main.py
  ```

- [ ] **Step 4: Update `README.md` — Linux/macOS manual setup (Option B)**

  Find the Linux Option B block:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  streamlit run app/main.py
  ```

  Add the editable install line:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  pip install -e . --no-deps
  streamlit run app/main.py
  ```

- [ ] **Step 5: Update `README.md` — Running Tests section**

  Find:
  ```markdown
  Install dev dependencies first (includes pytest):

  ```bash
  pip install -r requirements-dev.txt
  ```
  ```

  Update to:
  ```markdown
  Install dev dependencies and register the package:

  ```bash
  pip install -r requirements-dev.txt
  pip install -e . --no-deps
  ```
  ```

- [ ] **Step 6: Run all tests one final time**

  ```bash
  pytest
  ```
  Expected: `43 passed`

- [ ] **Step 7: Verify no sys.path hacks remain anywhere**

  ```bash
  grep -r "sys.path.insert" app/ tests/
  ```
  Expected: no output.

- [ ] **Step 8: Commit**

  ```bash
  git add setup_linux.sh setup_windows.ps1 README.md
  git commit -m "docs: add pip install -e . step to setup scripts and README"
  ```

---

## Done

All 43 tests pass. No `sys.path.insert` calls remain in `app/` or `tests/`. Running `pytest` with no arguments works. The `pip install -e . --no-deps` step is documented in all setup paths.
