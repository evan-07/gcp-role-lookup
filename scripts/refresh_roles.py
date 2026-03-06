#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Purpose: Pulls all GCP predefined IAM roles and permissions from the IAM API.
# Usage: python3 scripts/refresh_roles.py (or python on Windows)
# Requires: gcloud CLI installed and authenticated
# Version: 2.0.0 (cross-platform)
# Last Modified: 2026-03-06
# ---------------------------------------------------------------------------

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


def validate_gcloud() -> bool:
    """
    Check if gcloud CLI is installed and in PATH.

    Returns:
        True if gcloud is available, False otherwise.
    """
    gcloud_path = shutil.which("gcloud")
    if not gcloud_path:
        print("[ERROR] gcloud CLI not found in PATH.")
        print("Please install gcloud: https://cloud.google.com/sdk/docs")
        return False
    print(f"[INFO] Found gcloud at: {gcloud_path}")
    return True


def get_access_token() -> str:
    """
    Get GCP access token via gcloud CLI.

    Returns:
        Access token string.

    Raises:
        SystemExit: If gcloud auth fails.
    """
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        print(
            "[ERROR] Failed to get gcloud access token. "
            "Ensure gcloud is authenticated."
        )
        print(f"Details: {exc.stderr}")
        sys.exit(1)
    except FileNotFoundError:
        print("[ERROR] gcloud command not found in PATH.")
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    # Validate gcloud is available
    if not validate_gcloud():
        sys.exit(1)

    repo_root = Path(__file__).parent.parent.resolve()
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    roles_output = data_dir / "gcp_roles.json"
    perms_output = data_dir / "role_permissions.json"

    print("[INFO] Getting GCP access token...")
    token = get_access_token()

    print("[INFO] Fetching roles and permissions from IAM API...")

    base_url = (
        "https://iam.googleapis.com/v1/roles?view=FULL&pageSize=1000"
    )
    url = base_url
    headers = {"Authorization": f"Bearer {token}"}

    all_raw_roles = []

    while url:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read())
                all_raw_roles.extend(data.get("roles", []))

                next_token = data.get("nextPageToken")
                if next_token:
                    url = f"{base_url}&pageToken={next_token}"
                else:
                    url = None
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                print(
                    "[ERROR] Unauthorized (401). "
                    "Token may be expired or invalid."
                )
            elif exc.code == 403:
                print(
                    "[ERROR] Forbidden (403). "
                    "Service account may lack iam.roles.list permission."
                )
            else:
                print(f"[ERROR] HTTP {exc.code}: {exc.reason}")
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] API request failed: {exc}")
            sys.exit(1)

    print(f"[INFO] Fetched {len(all_raw_roles)} roles from IAM API.")

    roles_list = []
    perms_dict = {}

    for r in all_raw_roles:
        name = r.get("name", "").strip()
        title = r.get("title", "").strip()
        if name and title:
            roles_list.append({"title": title, "name": name})

        perms = r.get("includedPermissions", [])
        perms_dict[name] = sorted(perms)

    roles_list.sort(key=lambda x: x["title"].lower())

    try:
        with open(roles_output, "w", encoding="utf-8") as f:
            json.dump(roles_list, f, indent=2)
        print(
            f"[INFO] Wrote {len(roles_list)} roles to: {roles_output}"
        )

        perms_dict_sorted = {
            k: perms_dict[k] for k in sorted(perms_dict)
        }
        with open(perms_output, "w", encoding="utf-8") as f:
            json.dump(perms_dict_sorted, f, indent=2)
        print(f"[INFO] Wrote permissions to: {perms_output}")

        print("[SUCCESS] Role data refresh complete.")

    except IOError as exc:
        print(f"[ERROR] Failed to write output files: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()