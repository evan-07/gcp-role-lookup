# GCP Role Lookup

A Streamlit application for working with GCP IAM roles. Convert human-readable role titles to canonical role IDs, deduplicate role lists to the minimum required set, explore role permissions, search by permission string, and find the least-privilege role for a given set of requirements.

---

## Table of Contents

- [Pages](#pages)
- [Repository Layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Authentication for Live Refresh](#authentication-for-live-refresh)
- [Run on Windows](#run-on-windows)
- [Run on Linux/macOS](#run-on-linuxmacos)
- [Run in a Container (Podman or Docker)](#run-in-a-container-podman-or-docker)
- [Refresh Role and Permission Data](#refresh-role-and-permission-data)
- [How Matching Works](#how-matching-works)
- [Supersession Detection](#supersession-detection)
- [Running Tests](#running-tests)
- [Troubleshooting](#troubleshooting)

---

## Pages

### Resolve Titles

Paste GCP role titles (one per line) to look up their canonical role IDs. The app uses fuzzy matching to handle near-matches and ambiguous titles.

- **Output formats:** Terraform HCL block or a plain JSON array of role IDs, switchable via toggle
- **Confidence labels:** Exact / High / Medium / Low / Not found
- **Supersession detection:** Flags roles whose permissions are fully covered by another role in the same batch
- **Review Required table:** Surfaces all fuzzy matches and superseded roles for human review

### Role Inspector

Select any GCP role to browse its full permission set, grouped by service (e.g. `bigquery`, `compute`, `storage`). Each service group is a collapsible expander showing the permissions alphabetically.

Enable **Compare two roles** to view a three-column diff: permissions only in Role A, shared by both, and only in Role B.

### Permission Search

Enter an IAM permission string to find which roles grant it.

- **Exact Matches:** Roles whose permission set includes the exact string — shown with role ID, title, and Terraform string
- **Partial Matches:** Permission strings containing your query as a substring, ranked by the number of roles that grant them
- Minimum 3 characters required before searching

### Deduplicate Roles

Paste a list of predefined GCP role IDs (one per line) to remove redundant entries. Any role whose permissions are fully covered by another role in the list is eliminated, enforcing least privilege.

- **Input:** `roles/` prefixed role IDs only (predefined GCP roles)
- **Output formats:** Terraform HCL or JSON, switchable via toggle
- **Annotated mode:** Superseded roles appear as comments explaining why they were removed
- **Clean mode:** Only the minimal set of kept roles, no comments
- **Unknown IDs:** Roles not found in the data are flagged in a warning table without blocking the rest

### Find Smallest Role

Enter a list of required permissions (one per line) to find the least-privilege GCP role that grants all of them.

- **Exact Matches:** Roles that cover every required permission, sorted by tier (predefined → project → org) then by total permission count (smallest first)
- **Partial Matches:** Shown only when no exact match exists — top 10 roles ranked by coverage
- Helps avoid over-provisioning by surfacing the narrowest qualifying role

---

## Repository Layout

```text
gcp-role-lookup/
├── app/
│   ├── main.py                # Streamlit entry point — CSS, session state, nav, dispatch
│   ├── matcher.py             # Fuzzy title-to-ID matching (rapidfuzz)
│   ├── formatter.py           # Terraform HCL and JSON output formatting
│   ├── role_loader.py         # Local cache loading + optional live API refresh
│   ├── supersession.py        # Permission subset / supersession detection
│   └── page_views/
│       ├── resolve.py         # Resolve Titles page
│       ├── inspect.py         # Role Inspector page
│       ├── permissions.py     # Permission Search page
│       ├── find_role.py       # Find Smallest Role page
│       └── deduplicate.py     # Deduplicate Roles page
├── data/
│   ├── gcp_roles.json         # Role title → ID cache (bundled, refreshable)
│   └── role_permissions.json  # Role ID → permissions map (bundled, refreshable)
├── scripts/
│   └── refresh_roles.py       # Pulls latest roles + permissions from IAM API
├── tests/
│   ├── test_find_role_logic.py
│   ├── test_inspect_logic.py
│   ├── test_permissions_logic.py
│   ├── test_role_loader.py
│   ├── test_supersession_dedup.py
│   └── test_formatter_dedup.py
├── Architecture.md            # Design decisions and technical reference
├── ContainerFile              # Podman/Docker build file
├── setup_windows.ps1          # Windows setup + launch script
├── setup_linux.sh             # Linux/macOS setup + launch script
└── requirements.txt
```

---

## Prerequisites

### Required for normal app usage

- **Python 3.12+**
- **pip**

### Required only for live data refresh

- **gcloud CLI** installed and authenticated
- Identity with permission to call the IAM roles API (`iam.roles.list`)

### Verify prerequisites

```bash
python --version
pip --version
gcloud --version
```

If `gcloud` is missing, install from https://cloud.google.com/sdk/docs/install

---

## Authentication for Live Refresh

Authentication is only needed when refreshing role or permission data from GCP. The app works fully offline with the bundled data files.

### Recommended: Application Default Credentials (ADC)

```bash
gcloud auth application-default login
```

Default ADC file locations:
- **Windows:** `%APPDATA%\gcloud\application_default_credentials.json`
- **Linux/macOS:** `~/.config/gcloud/application_default_credentials.json`

### Optional: Explicit service account key

**PowerShell (Windows):**
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\service-account-key.json"
```

**bash (Linux/macOS):**
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

---

## Run on Windows

### Option A (recommended): helper script

From PowerShell in the repository root:

```powershell
.\setup_windows.ps1
```

The script checks Python 3.12+, creates `.venv`, installs dependencies, and starts Streamlit. It will ask whether to configure ADC — the default is **no**, so just press Enter to skip and start the app immediately. ADC is only needed to refresh the bundled role data.

If PowerShell blocks script execution:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Optional flags:

```powershell
.\setup_windows.ps1 -SkipGcloud
.\setup_windows.ps1 -SkipVenv
```

### Option B: manual setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e . --no-deps
streamlit run app/main.py
```

App URL: http://localhost:8501

---

## Run on Linux/macOS

### Option A (recommended): helper script

```bash
chmod +x setup_linux.sh
./setup_linux.sh
```

The script checks Python 3.12+, creates `.venv`, installs dependencies, and starts Streamlit. It will ask whether to configure ADC — the default is **no**, so just press Enter to skip and start the app immediately. ADC is only needed to refresh the bundled role data.

Optional flags:

```bash
./setup_linux.sh --skip-gcloud
./setup_linux.sh --skip-venv
```

### Option B: manual setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e . --no-deps
streamlit run app/main.py
```

App URL: http://localhost:8501

---

## Run in a Container (Podman or Docker)

> The build file is named `ContainerFile` (capital **F**). Use `-f ContainerFile` explicitly.

### Build

```bash
# Podman
podman build -f ContainerFile -t gcp-role-lookup .

# Docker
docker build -f ContainerFile -t gcp-role-lookup .
```

### Run with bundled static data (no credentials needed)

```bash
podman run --rm -p 8501:8501 gcp-role-lookup
```

### Run with ADC mounted (enables live refresh)

**Linux/macOS:**
```bash
podman run --rm -p 8501:8501 \
  -v "$HOME/.config/gcloud:/home/appuser/.config/gcloud:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/home/appuser/.config/gcloud/application_default_credentials.json \
  gcp-role-lookup
```

**Windows PowerShell:**
```powershell
docker run --rm -p 8501:8501 `
  -v "$env:APPDATA\gcloud:/home/appuser/.config/gcloud:ro" `
  -e GOOGLE_APPLICATION_CREDENTIALS=/home/appuser/.config/gcloud/application_default_credentials.json `
  gcp-role-lookup
```

---

## Refresh Role and Permission Data

The app ships with bundled role data in `data/gcp_roles.json` and `data/role_permissions.json`. These files are sufficient for offline use. Refresh them when you want the latest GCP IAM roles.

### Step 1 — Install gcloud CLI (if not already installed)

Download and install from https://cloud.google.com/sdk/docs/install, then verify:

```bash
gcloud --version
```

### Step 2 — Authenticate with Application Default Credentials (ADC)

```bash
gcloud auth application-default login
```

This opens a browser window for Google sign-in. Your credentials are saved to:
- **Windows:** `%APPDATA%\gcloud\application_default_credentials.json`
- **Linux/macOS:** `~/.config/gcloud/application_default_credentials.json`

The identity used must have permission to call the IAM roles API (`iam.roles.list`). The built-in role `roles/iam.roleViewer` is sufficient.

Verify the active account afterwards:

```bash
gcloud auth list
```

### Step 3 — Run the refresh script

```bash
# Windows
.venv\Scripts\python scripts/refresh_roles.py

# Linux/macOS
.venv/bin/python scripts/refresh_roles.py
```

This updates both `data/gcp_roles.json` and `data/role_permissions.json`. The app sidebar also has a **↻ Refresh from GCP API** button that runs the same refresh without leaving the browser.

---

## How Matching Works

The Resolve Titles page matches input titles to role IDs using fuzzy string matching (rapidfuzz). Each result is assigned a confidence label:

| Confidence | Score | Output behaviour |
|---|---|---|
| Exact | 100 | Included as-is |
| High | 85–99 | Included, flagged for review |
| Medium | 60–84 | Included, flagged for review |
| Low | < 60 | Commented out in HCL output |
| Not found | — | Commented out in HCL output |

---

## Supersession Detection

When `data/role_permissions.json` is present, the app checks whether any resolved role's permission set is a strict subset of another resolved role in the same batch. The narrower (superseded) role is marked and commented out in output:

```hcl
# "roles/bigquery.dataViewer", # BigQuery Data Viewer [Superseded by roles/bigquery.dataEditor]
"roles/bigquery.dataEditor",   # BigQuery Data Editor
```

If `role_permissions.json` is missing, supersession checks are skipped and the app works normally.

---

## Running Tests

Install dev dependencies and register the package:

```bash
pip install -r requirements-dev.txt
pip install -e . --no-deps
```

Then run:

```bash
pytest
```

The test suite covers matching logic, permission grouping, search functions, role loader, Find Smallest Role algorithm, deduplication logic, and formatter output (71 tests total).

---

## Troubleshooting

### `gcloud CLI not found in PATH`

Install from https://cloud.google.com/sdk/docs/install, then verify with `gcloud --version`.

### Authentication errors (`No ADC found`, `401`, `403`)

```bash
gcloud auth application-default login
gcloud auth list   # verify active account
```

### `role_permissions.json not found` warning in sidebar

The Role Inspector, Permission Search, and Find Smallest Role pages all require this file. Refresh it:

```bash
python scripts/refresh_roles.py
```

### Streamlit does not start

```bash
pip install -r requirements.txt
streamlit run app/main.py
```

### Port 8501 already in use

```bash
streamlit run app/main.py --server.port 8502
```
