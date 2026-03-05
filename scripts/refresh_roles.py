#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Purpose: Pulls all GCP predefined IAM roles and permissions from the IAM API.
# Usage: python3 scripts/refresh_roles.py
# Version: 1.0.0
# Last Modified: 2026-03-04
# ---------------------------------------------------------------------------

import json
import subprocess
import urllib.request
import os
import sys

def get_access_token():
    try:
        result = subprocess.run(['gcloud', 'auth', 'print-access-token'], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("[ERROR] Failed to get gcloud access token. Ensure gcloud is authenticated.")
        sys.exit(1)

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(repo_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    roles_output = os.path.join(data_dir, 'gcp_roles.json')
    perms_output = os.path.join(data_dir, 'role_permissions.json')
    
    token = get_access_token()
    print("[INFO] Fetching roles and permissions from IAM API...")
    
    base_url = "https://iam.googleapis.com/v1/roles?view=FULL&pageSize=1000"
    url = base_url
    headers = {"Authorization": f"Bearer {token}"}
    
    all_raw_roles = []
    
    while url:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read())
                all_raw_roles.extend(data.get('roles', []))
                
                next_token = data.get('nextPageToken')
                if next_token:
                    url = f"{base_url}&pageToken={next_token}"
                else:
                    url = None
        except Exception as e:
            print(f"[ERROR] API request failed: {e}")
            sys.exit(1)
            
    print(f"[INFO] Fetched {len(all_raw_roles)} roles.")
    
    roles_list = []
    perms_dict = {}
    
    for r in all_raw_roles:
        name = r.get("name", "")
        title = r.get("title", "")
        if name and title:
            roles_list.append({"title": title.strip(), "name": name.strip()})
        
        perms = r.get("includedPermissions", [])
        perms_dict[name] = sorted(perms)
        
    roles_list.sort(key=lambda x: x["title"].lower())
    
    with open(roles_output, 'w') as f:
        json.dump(roles_list, f, indent=2)
    print(f"[INFO] Wrote {len(roles_list)} roles to: {roles_output}")
    
    perms_dict_sorted = {k: perms_dict[k] for k in sorted(perms_dict)}
    with open(perms_output, 'w') as f:
        json.dump(perms_dict_sorted, f, indent=2)
    print(f"[INFO] Wrote permissions to: {perms_output}")

if __name__ == "__main__":
    main()