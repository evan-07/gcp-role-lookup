"""
role_loader.py

Loads GCP predefined roles from a local JSON cache.
Optionally refreshes from the live GCP IAM API using ADC.
Cross-platform support for Windows, Linux, and macOS.
"""

import json
import logging
import os
import platform
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent.parent / "data" / "gcp_roles.json"
PERMISSIONS_PATH = (
    Path(__file__).parent.parent / "data" / "role_permissions.json"
)


def _get_adc_path() -> Optional[Path]:
    """
    Locate Application Default Credentials (ADC) file.

    Checks in order:
    1. GOOGLE_APPLICATION_CREDENTIALS env var (all platforms)
    2. OS-specific gcloud config directory:
       - Windows: %APPDATA%\\gcloud\\
       - Linux/macOS: ~/.config/gcloud/

    Returns:
        Path object if ADC file exists, None otherwise.
    """
    # Priority 1: Explicit env var (works on all platforms)
    explicit_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if explicit_creds:
        creds_path = Path(explicit_creds)
        if creds_path.exists():
            logger.info(
                "ADC found via GOOGLE_APPLICATION_CREDENTIALS: %s",
                explicit_creds,
            )
            return creds_path
        else:
            logger.warning(
                "GOOGLE_APPLICATION_CREDENTIALS set but file not "
                "found: %s",
                explicit_creds,
            )

    # Priority 2: OS-specific gcloud config directory
    if platform.system() == "Windows":
        appdata = os.getenv("APPDATA")
        if appdata:
            gcloud_dir = Path(appdata) / "gcloud"
            adc_file = gcloud_dir / "application_default_credentials.json"
        else:
            logger.warning("APPDATA env var not set on Windows")
            adc_file = None
    else:
        # Linux and macOS
        home = Path.home()
        adc_file = home / ".config" / "gcloud" / \
            "application_default_credentials.json"

    if adc_file and adc_file.exists():
        logger.info("ADC found in gcloud config: %s", adc_file)
        return adc_file

    logger.warning(
        "No ADC found. Set GOOGLE_APPLICATION_CREDENTIALS or run "
        "'gcloud auth application-default login'."
    )
    return None


def load_roles() -> list[dict]:
    """
    Load roles from the local JSON cache.

    Returns:
        List of role dicts with 'title' and 'name' keys.

    Raises:
        FileNotFoundError: If the roles JSON file is missing.
        ValueError: If the JSON is malformed.
    """
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Roles data file not found: {DATA_PATH}. "
            "Run 'python scripts/refresh_roles.py' to generate it."
        )

    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            roles = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Malformed roles JSON at {DATA_PATH}: {exc}"
        ) from exc

    if not isinstance(roles, list):
        raise ValueError(
            "Expected a JSON array of role objects in gcp_roles.json."
        )

    return roles


def refresh_roles_from_api(
    project_id: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Refresh the local roles cache by calling the GCP IAM API.

    Uses Application Default Credentials (ADC). Writes results
    back to the local JSON cache file.

    Works on Windows, Linux, and macOS.

    Args:
        project_id: Optional GCP project ID. If None, uses the
            GOOGLE_CLOUD_PROJECT env var or gcloud's active project.

    Returns:
        Tuple of (success: bool, message: str).
    """
    try:
        from googleapiclient import discovery  # type: ignore
        from google.auth import default as google_auth_default
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        return (
            False,
            "google-api-python-client and google-auth are required "
            "for live refresh. Install them via: "
            "pip install -r requirements.txt",
        )

    # Check ADC availability
    adc_path = _get_adc_path()
    if not adc_path:
        return (
            False,
            "No Application Default Credentials found. "
            "Run 'gcloud auth application-default login' first.",
        )

    try:
        credentials, detected_project = google_auth_default(
            scopes=[
                "https://www.googleapis.com/auth/cloud-platform"
                ".read-only"
            ]
        )
    except DefaultCredentialsError as exc:
        return (
            False,
            f"ADC authentication failed: {exc}. "
            "Run 'gcloud auth application-default login'.",
        )
    except Exception as exc:  # noqa: BLE001
        return (
            False,
            f"Unexpected auth error: {exc}",
        )

    try:
        service = discovery.build(
            "iam", "v1", credentials=credentials
        )
        roles = []
        request = service.roles().list(view="FULL")
        while request is not None:
            response = request.execute()
            for role in response.get("roles", []):
                title = role.get("title", "")
                name = role.get("name", "")
                if title and name:
                    roles.append(
                        {
                            "title": title,
                            "name": name,
                        }
                    )
            request = service.roles().list_next(
                previous_request=request,
                previous_response=response,
            )

        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(roles, f, indent=2)

        logger.info(
            "Refreshed %d roles from GCP IAM API.", len(roles)
        )
        return True, f"Successfully refreshed {len(roles)} roles."

    except Exception as exc:  # noqa: BLE001
        return (
            False,
            f"API call failed: {exc}. "
            "Ensure your GCP credentials have iam.roles.list "
            "permission.",
        )


def load_permissions() -> dict[str, set[str]]:
    """
    Load per-role permission sets from the local JSON cache.

    Returns an empty dict (not an error) if the file is missing,
    allowing the caller to degrade gracefully by skipping supersession
    checks rather than crashing.

    Returns:
        Dict mapping role_id (str) → set of permission strings.
        Empty dict if the file does not exist or is unreadable.
    """
    if not PERMISSIONS_PATH.exists():
        logger.warning(
            "role_permissions.json not found at %s. "
            "Run 'python scripts/refresh_roles.py' to generate it. "
            "Supersession checking will be disabled.",
            PERMISSIONS_PATH,
        )
        return {}

    try:
        with open(PERMISSIONS_PATH, "r", encoding="utf-8") as f:
            raw: dict = json.load(f)
    except json.JSONDecodeError as exc:
        logger.error(
            "Malformed role_permissions.json: %s. "
            "Supersession checking disabled.",
            exc,
        )
        return {}

    if not isinstance(raw, dict):
        logger.error(
            "role_permissions.json must be a JSON object. "
            "Supersession checking disabled."
        )
        return {}

    # Convert lists to sets for O(1) subset checks
    return {
        role_id: set(perms)
        for role_id, perms in raw.items()
        if isinstance(perms, list)
    }