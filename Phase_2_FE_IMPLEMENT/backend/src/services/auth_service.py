import firebase_admin
from firebase_admin import auth, credentials
import os
from fastapi import HTTPException, status
from typing import Optional

class AuthService:
    def __init__(self):
        # Initialize Firebase Admin SDK if not already initialized
        if not firebase_admin._apps:
            # Look for service account key in environment or a specific path
            key_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json")
            print(f"DEBUG: Looking for Firebase key at: {os.path.abspath(key_path)}")
            
            if os.path.exists(key_path):
                try:
                    cred = credentials.Certificate(key_path)
                    firebase_admin.initialize_app(cred)
                    print("✅ Firebase Admin SDK initialized successfully.")
                except Exception as ex:
                    print(f"❌ Failed to initialize Firebase with key: {str(ex)}")
            else:
                print("⚠️ Firebase Service Account Key NOT FOUND. Token verification will fail.")

    def verify_token(self, id_token: str) -> dict:
        try:
            # Add clock_skew_seconds=60 to handle tiny time drifts between 
            # the client and Google's servers.
            return auth.verify_id_token(id_token, clock_skew_seconds=60)
        except Exception as e:
            # If your version of firebase-admin is older than 6.2.0, clock_skew_seconds
            # might not be supported. This fallback ensures it still works.
            if "unexpected keyword argument 'clock_skew_seconds'" in str(e):
                try:
                    return auth.verify_id_token(id_token)
                except Exception as inner_e:
                    print(f"🔥 Token Verification Failed (Legacy): {str(inner_e)}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Invalid credentials: {str(inner_e)}",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            
            print(f"🔥 Token Verification Failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authentication credentials: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def get_user_from_token(self, id_token: str) -> dict:
        decoded_token = self.verify_token(id_token)
        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture"),
        }
