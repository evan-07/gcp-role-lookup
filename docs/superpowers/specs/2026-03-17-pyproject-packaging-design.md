# pyproject.toml Packaging Design

## Goal

Eliminate all `sys.path.insert` hacks in the codebase by making `app` a properly installed Python package, and standardize pytest configuration using `pyproject.toml`.

## Approach

Minimal `pyproject.toml` alongside existing `requirements.txt`. The requirements files remain the authoritative source for pinned dependency versions. `pyproject.toml` is responsible only for project metadata, build system declaration, and pytest configuration. Users run `pip install -e . --no-deps` once after the normal dependency install to register the package on Python's path.

## Files Created

### `pyproject.toml` (new)

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

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

Makes `app` a proper Python package. Currently `app/page_views/__init__.py` exists but `app/__init__.py` does not — this is inconsistent and fixed here.

## Files Modified

### `app/main.py`

Remove:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

`pathlib.Path` and `sys` are not used elsewhere in this file after the removal.

### `app/page_views/resolve.py`, `inspect.py`, `permissions.py`, `find_role.py`

Remove from each:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
```

Verify `sys` and `Path` are not used elsewhere in each file before removing their imports.

### `tests/test_inspect_logic.py`

Remove path hack. Update import:
```python
# before
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
from page_views.inspect import group_permissions

# after
from app.page_views.inspect import group_permissions
```

### `tests/test_permissions_logic.py`

```python
# before
from page_views.permissions import sort_key, find_exact_matches, find_partial_matches

# after
from app.page_views.permissions import sort_key, find_exact_matches, find_partial_matches
```

### `tests/test_find_role_logic.py`

```python
# before
from page_views.find_role import parse_permissions_input, _tier, find_smallest_roles

# after
from app.page_views.find_role import parse_permissions_input, _tier, find_smallest_roles
```

### `tests/test_role_loader.py`

```python
# before
from role_loader import clear_all_caches

# after
from app.role_loader import clear_all_caches
```

### `setup_linux.sh`

Add after `pip install -r requirements.txt --prefer-binary`:
```bash
pip install -e . --no-deps
success "Package installed in editable mode"
```

### `setup_windows.ps1`

Add after `pip install -r requirements.txt --prefer-binary --quiet`:
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

## Setup Flow After Changes

```
python -m venv .venv
# activate venv
pip install -r requirements.txt          # pinned app dependencies
pip install -e . --no-deps               # register app package (one-time)

# for development/testing:
pip install -r requirements-dev.txt      # adds pytest
pytest                                   # no arguments needed (testpaths configured)
```

## What Does Not Change

- `requirements.txt` — runtime pinned deps, unchanged
- `requirements-dev.txt` — dev pinned deps, unchanged
- All application logic — untouched
- All test logic — only the import lines change
- `ContainerFile` — installs from `requirements.txt` directly, no editable install needed in the container (the `app/` directory is copied into `/app/` and Streamlit runs it directly)

## Verification

After implementation, run:
```bash
pytest
```
All 43 tests must pass with no `sys.path` manipulation anywhere in the codebase.
