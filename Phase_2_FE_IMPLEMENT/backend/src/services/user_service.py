from ..repositories.user_repository import UserRepository
from ..database.schemas import UserCreate, UserUpdate, UserResponse
from ..database.models import User
from fastapi import HTTPException, status
from typing import List, Optional

class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def get_user_profile(self, uid: str) -> User:
        user = self.user_repo.get_by_id(uid)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user

    def sync_user(self, user_data: dict) -> User:
        uid = user_data.get("uid")
        existing_user = self.user_repo.get_by_id(uid)
        
        if not existing_user:
            user_in = UserCreate(
                uid=uid,
                email=user_data.get("email"),
                displayName=user_data.get("name"),
                photoURL=user_data.get("picture")
            )
            return self.user_repo.create(user_in)
        else:
            # Update last login or other fields if needed
            user_update = UserUpdate(
                displayName=user_data.get("name"),
                photoURL=user_data.get("picture")
            )
            return self.user_repo.update(uid, user_update)

    def update_user_role(self, uid: str, role: str) -> User:
        user_update = UserUpdate(role=role)
        updated_user = self.user_repo.update(uid, user_update)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return updated_user

    def list_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        return self.user_repo.list(skip, limit)
