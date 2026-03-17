# pyproject.toml Packaging Design

## Goal

Eliminate all `sys.path.insert` hacks in the codebase by making `app` a properly installed Python package, and standardize pytest configuration using `pyproject.toml`.

## Approach

Minimal `pyproject.toml` alongside existing `requirements.txt`. The requirements files remain the authoritative source for pinned dependency versions. `pyproject.toml` is responsible only for project metadata, build system declaration, and pytest configuration. Users run `pip install -e . --no-deps` once after the normal dependency install to register the package on Python's path.

## Existing __init__.py State

- `app/__init__.py` — does **not** exist. Must be created.
- `app/page_views/__init__.py` — already exists. No change needed.
- `tests/__init__.py` — already exists. No change needed.

## Files Created

### `pyproject.toml` (new, repo root)

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

`dependencies = []` is intentional — pins are managed by `requirements.txt`, not here.

### `app/__init__.py` (new, empty)

Makes `app` a proper Python package. Create as an empty file.

## Files Modified

### `app/main.py`

Remove these three specific lines (they are not contiguous — `import logging` sits between `import sys` and `from pathlib import Path` and must be kept):

```python
import sys          # remove
from pathlib import Path  # remove
sys.path.insert(0, str(Path(__file__).parent.parent))  # remove
```

`import logging` on the line between `import sys` and `from pathlib import Path` must **not** be removed — it is used later in the file.

**Also update** the four deferred dispatch imports inside the `if/elif` block (currently bare `page_views.*`, which relied on the now-removed path hack):

```python
# before
from page_views.resolve import render as render_resolve
from page_views.inspect import render as render_inspect
from page_views.permissions import render as render_permissions
from page_views.find_role import render as render_find_role

# after
from app.page_views.resolve import render as render_resolve
from app.page_views.inspect import render as render_inspect
from app.page_views.permissions import render as render_permissions
from app.page_views.find_role import render as render_find_role
```

The existing `from app.role_loader import ...` import already uses the `app.` prefix — leave it unchanged.

### `app/page_views/resolve.py`, `inspect.py`, `permissions.py`, `find_role.py`

Each file contains these three lines — remove all three from each file. The lines are **not contiguous** in all files (other imports may appear between them), so remove each line individually rather than as a block:

```python
import sys                                                       # remove
from pathlib import Path                                         # remove
sys.path.insert(0, str(Path(__file__).parent.parent.parent))    # remove
```

Before removing `import sys` or `from pathlib import Path`, confirm each is not used elsewhere in the file.

### `tests/test_inspect_logic.py`

Current path hack (adds repo root):
```python
sys.path.insert(0, str(Path(__file__).parent.parent))
```

The deferred imports inside test functions already use the correct `app.` prefix (e.g. `from app.page_views.inspect import group_permissions`). Remove only:
- `import sys`
- `from pathlib import Path`
- `sys.path.insert(0, str(Path(__file__).parent.parent))`

The test imports themselves are already correct — no other changes needed in this file.

### `tests/test_role_loader.py`

Current path hack (adds repo root):
```python
sys.path.insert(0, str(Path(__file__).parent.parent))
```

The import already uses `import app.role_loader as rl`. Remove only:
- `import sys`
- `from pathlib import Path`
- `sys.path.insert(0, str(Path(__file__).parent.parent))`

### `tests/test_permissions_logic.py`

Current path hack (adds `app/` directory, enabling bare `page_views.*` imports):
```python
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
```

Remove the path hack and its supporting imports. Then update every deferred import inside test functions from bare `page_views.*` to `app.page_views.*`:

```python
# before
from page_views.permissions import sort_key
from page_views.permissions import find_exact_matches
from page_views.permissions import find_partial_matches

# after
from app.page_views.permissions import sort_key
from app.page_views.permissions import find_exact_matches
from app.page_views.permissions import find_partial_matches
```

### `tests/test_find_role_logic.py`

Current path hack (adds `app/` directory, enabling bare `page_views.*` imports):
```python
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
```

Remove the path hack and its supporting imports. Then update every deferred import inside test functions from bare `page_views.*` to `app.page_views.*`:

```python
# before
from page_views.find_role import parse_permissions_input
from page_views.find_role import _tier
from page_views.find_role import find_smallest_roles

# after
from app.page_views.find_role import parse_permissions_input
from app.page_views.find_role import _tier
from app.page_views.find_role import find_smallest_roles
```

### `setup_linux.sh`

Inside the `if [ "$SKIP_VENV" = false ]` block, insert two new lines after the `pip install -r requirements.txt --prefer-binary` line and before the `success "Dependencies installed"` line:

```bash
pip install -e . --no-deps
success "Package installed in editable mode"
```

The existing `success "Dependencies installed"` line remains after the new lines.

### `setup_windows.ps1`

After the `pip install -r requirements.txt` block and its `Write-Success "Dependencies installed"` call, insert:

```powershell
& pip install -e . --no-deps --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error_ "Failed to install package in editable mode."
    exit 1
}
Write-Success "Package installed in editable mode"
```

### `README.md`

**Manual setup sections (Windows Option B and Linux/macOS Option B):** Add `pip install -e . --no-deps` after `pip install -r requirements.txt`.

**Running Tests section:** Add `pip install -e . --no-deps` as a prerequisite step before running pytest.

## ContainerFile

No changes needed. The container sets `WORKDIR /app` and copies `app/` to `./app/`, making `app` importable as a subdirectory. The updated `app.page_views.*` imports resolve correctly in this context. No editable install is required in the container.

## Setup Flow After Changes

```
python -m venv .venv
# activate venv
pip install -r requirements.txt          # pinned app dependencies
pip install -e . --no-deps               # register app package (one-time)

# for development/testing:
pip install -r requirements-dev.txt      # adds pytest (includes -r requirements.txt)
pytest                                   # no arguments needed (testpaths configured)
```

## What Does Not Change

- `requirements.txt` — runtime pinned deps, unchanged
- `requirements-dev.txt` — dev pinned deps, unchanged
- `app/page_views/__init__.py` — already exists, unchanged
- `tests/__init__.py` — already exists, unchanged
- All application logic — untouched
- All test logic — only import lines change in `test_permissions_logic.py` and `test_find_role_logic.py`
- `ContainerFile` — no changes needed

## Verification

After implementation, run:
```bash
pytest
```
All 43 tests must pass with no `sys.path` manipulation anywhere in the codebase.
