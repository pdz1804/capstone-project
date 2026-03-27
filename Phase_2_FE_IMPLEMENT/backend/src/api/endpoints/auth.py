from fastapi import APIRouter, Depends, Header, HTTPException, status
from typing import Annotated
from ...services.auth_service import AuthService
from ...services.user_service import UserService
from ...repositories.user_repository import UserRepository
from ...database.db_config import get_db
from sqlalchemy.orm import Session
from ...database.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

def get_auth_service():
    return AuthService()

def get_user_service(db: Session = Depends(get_db)):
    return UserService(UserRepository(db))

@router.post("/login", response_model=UserResponse)
async def login(
    authorization: str = Header(...),
    auth_service: AuthService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    token = authorization.split(" ")[1]
    user_data = auth_service.get_user_from_token(token)
    user = user_service.sync_user(user_data)
    return user
