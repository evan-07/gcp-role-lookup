# GCP Role Lookup

Streamlit app for resolving GCP IAM role titles to role IDs.
Outputs Terraform HCL-formatted entries.

## Quick Start

### Running Locally (For Testing)
Prerequisites

Make sure you have Python 3.12+ and the VS Code Python extension installed.

Steps
1. Create and activate a virtual environment
```bash
cd gcp-role-lookup
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows
```
2. Install dependencies
```bash
pip install -r requirements.txt
```
3. Run Streamlit
```bash
streamlit run app/main.py
```
Streamlit will open http://localhost:8501 automatically.


### With Podman (recommended)

```bash
# Build
podman build -t gcp-role-lookup .

# Run (static mode, no auth required)
podman run --rm -p 8501:8501 gcp-role-lookup

# Run (with live refresh via ADC)
podman run --rm -p 8501:8501 \
  -v ~/.config/gcloud:/home/appuser/.config/gcloud:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/home/appuser/.config/gcloud/application_default_credentials.json \
  gcp-role-lookup
```

Open http://localhost:8501 in your browser.

### Local Dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/main.py
```

## Refresh Roles Locally

Execute the following command to update the predefined IAM roles and permissions data:

```bash
python3 scripts/refresh_roles.py
```

Requires `gcloud` authenticated with `roles/iam.roleViewer`.

## Fuzzy Match Thresholds

| Score | Status  | Behaviour                          |
|-------|---------|------------------------------------|
| 100%  | Exact   | Emitted as-is                      |
| ≥ 85% | High    | Emitted with inline warning comment |
| 60–84%| Medium  | Emitted with inline warning comment |
| < 60% | Low     | Commented out with suggestions     |
| None  | Not found | Commented out                    |

## IAM Least Privilege

The live refresh only requires:
```
roles/iam.roleViewer
```
Do not grant broader roles for this operation.