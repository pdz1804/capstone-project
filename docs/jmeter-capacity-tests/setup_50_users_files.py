#!/usr/bin/env python3
"""Setup: Upload 50 files (one per user) and create mapping CSV"""

import csv
import json
import requests
from pathlib import Path
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BASE_URL = "https://k2p-bkmind-learning-platform.com:443"
USERS_CSV = "data/users.csv"
UPLOAD_FILE = "data/Text_mining_by_using_Python2025_5pages.pdf"
OUTPUT_MAPPING = "data/user_file_mapping.csv"

def setup_50_users():
    """Upload files for 50 users and create mapping"""

    print("=" * 80)
    print("BK-MInD - Setup Phase 1: Upload Files for 50 Users")
    print("=" * 80)

    # Read users
    users = []
    with open(USERS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        users = list(reader)

    print(f"[INFO] Loaded {len(users)} users from {USERS_CSV}\n")

    # Create mapping
    mapping = [["email", "user_id", "file_path"]]
    success_count = 0
    error_count = 0

    # Upload file for each user
    for i, user in enumerate(users, 1):
        email = user['email']
        password = user['password']
        user_num = i

        try:
            print(f"[{i}/{len(users)}] Processing user: {email}", end=" ", flush=True)

            # Step 1: Login
            login_url = f"{BASE_URL}/api/auth/login-local"
            login_data = {"email": email, "password": password}

            login_response = requests.post(
                login_url,
                json=login_data,
                headers={"Content-Type": "application/json"},
                verify=False,
                timeout=10
            )
            login_response.raise_for_status()
            login_json = login_response.json()
            token = login_json.get("access_token")
            user_id = login_json.get("user", {}).get("uid")

            if not token or not user_id:
                print(f"✗ No token or user_id received")
                error_count += 1
                continue

            print(f"✓ Auth (uid={user_id})", end=" ", flush=True)

            # Step 2: Upload file
            upload_url = f"{BASE_URL}/api/upload"
            files = {"files": open(UPLOAD_FILE, 'rb')}
            headers = {
                "Authorization": f"Bearer {token}",
                "X-User-Id": user_id  # Pass user_id in header for per-user storage
            }

            upload_response = requests.post(
                upload_url,
                files=files,
                headers=headers,
                verify=False,
                timeout=300
            )
            upload_response.raise_for_status()
            upload_json = upload_response.json()

            # Extract file path (check both 'files' and 'data' keys)
            file_path = None
            if "files" in upload_json and len(upload_json["files"]) > 0:
                file_path = upload_json["files"][0].get("path")
            elif "data" in upload_json and len(upload_json["data"]) > 0:
                file_path = upload_json["data"][0].get("path")

            if not file_path:
                print(f"✗ No file_path in response")
                error_count += 1
                continue

            # Verify file is in user's directory (not /default/)
            if f"users/{user_id}/" not in file_path:
                print(f"✗ File not in user directory: {file_path}")
                error_count += 1
                continue

            print(f"✓ Uploaded -> .../{file_path.split('/')[-1]}")

            # Add to mapping: email, user_id, file_path
            mapping.append([email, user_id, file_path])
            success_count += 1

        except Exception as e:
            print(f"✗ Error: {str(e)}")
            error_count += 1

    # Save mapping
    with open(OUTPUT_MAPPING, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(mapping)

    print("\n" + "=" * 80)
    print("SETUP COMPLETE")
    print("=" * 80)
    print(f"✓ Successful uploads: {success_count}")
    print(f"✗ Failed uploads: {error_count}")
    print(f"✓ Mapping saved to: {OUTPUT_MAPPING}\n")

    # Show sample
    print("Mapping sample (first 6 rows):")
    with open(OUTPUT_MAPPING, 'r') as f:
        for i, line in enumerate(f):
            if i < 6:
                print(line.strip())

    print("\n" + "=" * 80)
    print("Next: Run the test with:")
    print("jmeter -n -t 05_process_mapped.jmx -Jhost=k2p-bkmind-learning-platform.com -Jport=443 -Jthreads=50 -Jramp_up=10 -Jduration=90 -l results/process_mapped_50threads.jtl")
    print("=" * 80)

if __name__ == "__main__":
    setup_50_users()
