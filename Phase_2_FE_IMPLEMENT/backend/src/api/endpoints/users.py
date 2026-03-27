from fastapi import APIRouter, Depends, Header, HTTPException, status
from typing import List, Annotated
from ...services.auth_service import AuthService
from ...services.user_service import UserService
from ...repositories.user_repository import UserRepository
from ...database.db_config import get_db
from sqlalchemy.orm import Session
from ...database.schemas import UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

def get_auth_service():
    return AuthService()

def get_user_service(db: Session = Depends(get_db)):
    return UserService(UserRepository(db))

async def get_current_user(
    authorization: str = Header(...),
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    token = authorization.split(" ")[1]
    user_info = auth_service.get_user_from_token(token)
    user = user_service.get_user_profile(user_info["uid"])
    return user

@router.get("/me", response_model=UserResponse)
async def get_me(user: UserResponse = Depends(get_current_user)):
    return user

@router.get("/", response_model=List[UserResponse])
async def list_users(
    user_service: UserService = Depends(get_user_service),
    skip: int = 0,
    limit: int = 100
):
    return user_service.list_users(skip=skip, limit=limit)
