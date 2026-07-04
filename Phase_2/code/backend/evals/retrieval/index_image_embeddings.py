"""Script to index image embeddings for specific files via API."""

import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ 'requests' library not found. Install with: pip install requests")
    sys.exit(1)

# Configuration
API_BASE_URL = "http://localhost:8000"
USER_ID = os.getenv("DEFAULT_STORAGE_USER_ID", "default")

def index_image_embeddings(file_names=None, force=True, mode="standard", api_url=API_BASE_URL, user_id=USER_ID):
    """
    Index image embeddings for specific files.
    
    Args:
        file_names: List of file names (e.g., ["Deepseek v4", "2412.19437v2"])
                   If None, indexes all files.
        force: Force re-indexing even if already indexed
        mode: "standard" or "fast"
    """
    url = f"{api_url}/api/index/image"
    
    params = {"force": force}
    body = {
        "selected_names": file_names or [],
        "mode": mode
    }
    
    print(f"🔧 Indexing image embeddings...")
    print(f"   User ID: {user_id}")
    print(f"   Files: {file_names or 'ALL'}")
    print(f"   Force: {force}")
    print(f"   Mode: {mode}")
    print()
    
    # Add user_id to headers (adjust based on your auth setup)
    headers = {
        "Content-Type": "application/json",
        "X-User-ID": user_id  # Adjust based on your auth
    }
    
    try:
        response = requests.post(
            url,
            params=params,
            json=body,
            headers=headers,
            timeout=600  # 10 minutes timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Image indexing completed!")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            # Check results
            img_res = result.get("results", {}).get("image", {})
            if img_res.get("status") == "failed":
                print(f"\n❌ Image indexing FAILED:")
                print(f"   Error: {img_res.get('error')}")
                return False
            
            return True
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out (10 minutes). Try again or increase timeout.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Index image embeddings for specific files via API"
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="List of file names to index (e.g., 'Deepseek v4' '2412.19437v2')"
    )
    parser.add_argument(
        "--user-id",
        default=USER_ID,
        help=f"User ID (default: {USER_ID})"
    )
    parser.add_argument(
        "--api-url",
        default=API_BASE_URL,
        help=f"API base URL (default: {API_BASE_URL})"
    )
    parser.add_argument(
        "--no-force",
        action="store_true",
        help="Don't force re-indexing (skip if already indexed)"
    )
    parser.add_argument(
        "--mode",
        choices=["standard", "fast"],
        default="standard",
        help="Indexing mode (default: standard)"
    )
    
    args = parser.parse_args()
    
    success = index_image_embeddings(
        file_names=args.files,
        force=not args.no_force,
        mode=args.mode,
        api_url=args.api_url,
        user_id=args.user_id,
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
