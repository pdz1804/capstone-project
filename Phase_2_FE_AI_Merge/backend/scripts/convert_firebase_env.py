#!/usr/bin/env python3
"""
Convert Firebase service account JSON file to environment variable format.

Usage:
    python scripts/convert_firebase_env.py firebase-service-account.json

This will output the JSON as a single-line string suitable for FIREBASE_SERVICE_ACCOUNT env var.
"""

import json
import sys
from pathlib import Path


def convert_firebase_json_to_env(json_file_path: str) -> str:
    """Convert Firebase service account JSON file to env var format (single-line JSON)."""
    try:
        with open(json_file_path, 'r') as f:
            cred_dict = json.load(f)
        return json.dumps(cred_dict, separators=(',', ':'))
    except FileNotFoundError:
        print(f"Error: File not found: {json_file_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {json_file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/convert_firebase_env.py <path-to-firebase-service-account.json>")
        print("")
        print("Example:")
        print("  python scripts/convert_firebase_env.py firebase-service-account.json")
        print("")
        print("This will output the JSON as a single-line string for the FIREBASE_SERVICE_ACCOUNT env var.")
        sys.exit(1)

    json_file = sys.argv[1]
    env_string = convert_firebase_json_to_env(json_file)

    print("=" * 100)
    print("Firebase Service Account Conversion")
    print("=" * 100)
    print("\nAdd this to your .env file:\n")
    print(f"FIREBASE_SERVICE_ACCOUNT={env_string}")
    print("\n" + "=" * 100)
    print("\nFor production, use an environment variable instead:")
    print("  export FIREBASE_SERVICE_ACCOUNT='...'  # Paste the above string")
    print("\nFor Docker, use:")
    print("  docker run -e FIREBASE_SERVICE_ACCOUNT='...' <image>")
    print("\nFor GitHub Actions, use:")
    print("  - name: Set Firebase credentials")
    print("    env:")
    print("      FIREBASE_SERVICE_ACCOUNT: ${{ secrets.FIREBASE_SERVICE_ACCOUNT }}")


if __name__ == "__main__":
    main()
