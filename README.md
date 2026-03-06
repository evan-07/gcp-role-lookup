# GCP Role Lookup

Streamlit app for resolving GCP IAM role titles to role IDs.
Outputs Terraform HCL-formatted entries.

**Cross-platform support:** Windows, Linux, macOS

---

## Prerequisites

Before you start, ensure you have:

- **Python 3.12 or later** — [Download](https://www.python.org/downloads/)
- **gcloud CLI** — [Install](https://cloud.google.com/sdk/docs/install)
- **GCP credentials** — See [Authentication](#authentication) below

### Verify Prerequisites

```bash
python --version          # Should be 3.12+
gcloud --version          # Should be present
gcloud auth list          # Should show active account
```

---

## Authentication

This tool requires GCP credentials to refresh role data from the IAM API.

### Option 1: Application Default Credentials (Recommended for Development)

Works on **Windows, Linux, and macOS**.

```bash
gcloud auth application-default login
```

This creates `application_default_credentials.json` in:
- **Windows**: `%APPDATA%\gcloud\`
- **Linux/macOS**: `~/.config/gcloud/`

### Option 2: Explicit Credentials File

Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable:

**Windows (PowerShell):**
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\path\to\service-account-key.json"
```

**Windows (Command Prompt):**
```cmd
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\service-account-key.json
```

**Linux/macOS:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

---

## Quick Start

### Windows

1. **Clone and navigate to the repo:**
   ```powershell
   git clone https://github.com/evan-07/gcp-role-lookup.git
   cd gcp-role-lookup
   ```

2. **Create and activate a virtual environment:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
   > If you get a permissions error, run:
   > ```powershell
   > Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   > ```

3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Authenticate with GCP (first time only):**
   ```powershell
   gcloud auth application-default login
   ```

5. **Refresh role data (optional, but recommended):**
   ```powershell
   python scripts/refresh_roles.py
   ```

6. **Run Streamlit:**
   ```powershell
   streamlit run app/main.py
   ```

   Streamlit will automatically open `http://localhost:8501` in your browser.

### Linux / macOS

1. **Clone and navigate to the repo:**
   ```bash
   git clone https://github.com/evan-07/gcp-role-lookup.git
   cd gcp-role-lookup
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Authenticate with GCP (first time only):**
   ```bash
   gcloud auth application-default login
   ```

5. **Refresh role data (optional, but recommended):**
   ```bash
   python3 scripts/refresh_roles.py
   ```

6. **Run Streamlit:**
   ```bash
   streamlit run app/main.py
   ```

   Streamlit will automatically open `http://localhost:8501` in your browser.

---

## Refreshing Role Data

The tool comes with a static cache of GCP roles (`data/gcp_roles.json`). To update it with the latest roles and permissions from GCP:

**Windows:**
```powershell
python scripts/refresh_roles.py
```

**Linux/macOS:**
```bash
python3 scripts/refresh_roles.py
```

**Requirements:**
- gcloud authenticated (run `gcloud auth application-default login`)
- Service account must have `roles/iam.roleViewer` permission

---

## Fuzzy Match Confidence Levels

The tool uses fuzzy matching to resolve role titles. Confidence levels are:

| Score | Status  | Behaviour                          |
|-------|---------|------------------------------------|
| 100%  | Exact   | Emitted as-is                      |
| ≥ 85% | High    | Emitted with inline warning comment |
| 60–84%| Medium  | Emitted with inline warning comment |
| < 60% | Low     | Commented out with suggestions     |
| None  | Not found | Commented out                    |

---

## Supersession Detection

The tool identifies when a resolved role's permissions are a strict subset of another role in your batch. Superseded roles are commented out in the Terraform output.

Example:
```hcl
# "roles/bigquery.dataEditor", # BigQuery Data Editor [Superseded by roles/bigquery.admin]
"roles/bigquery.admin", # BigQuery Admin
```

---

## Troubleshooting

### "No match found for: [role title]"

- The role may not exist in GCP, or the title is misspelled.
- Run `python scripts/refresh_roles.py` to fetch the latest role list.
- Check the **Suggestions** in the "Review Required" table.

### "No ADC found" or "ADC authentication failed"

**Windows:**
```powershell
gcloud auth application-default login
# This creates %APPDATA%\gcloud\application_default_credentials.json
```

**Linux/macOS:**
```bash
gcloud auth application-default login
# This creates ~/.config/gcloud/application_default_credentials.json
```

### "gcloud CLI not found in PATH"

Install gcloud SDK: https://cloud.google.com/sdk/docs/install

Verify it's in your PATH:
```bash
gcloud --version
```

### Streamlit won't start

Ensure all dependencies are installed:

**Windows:**
```powershell
pip install -r requirements.txt
```

**Linux/macOS:**
```bash
pip install -r requirements.txt
```

---

## Development

### Project Structure

```
gcp-role-lookup/
├── app/
│   ├── main.py              # Streamlit entry point
│   ├── matcher.py           # Fuzzy matching logic
│   ├── formatter.py         # Terraform HCL formatting
│   ├── role_loader.py       # GCP role data loading
│   └── supersession.py      # Supersession detection
├── scripts/
│   └── refresh_roles.py     # Refresh role data from GCP API
├── data/
│   ├── gcp_roles.json       # Static role cache
│   └── role_permissions.json # Role permissions (generated)
├── requirements.txt
├── Containerfile            # Podman/Docker build
└── README.md
```

### Code Style

All Python code follows **PEP 8**:
- Max line length: 79 characters
- Type hints where practical
- Docstrings for all public functions

---

## License

(Add license info if applicable)