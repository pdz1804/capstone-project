from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, status

from .firebase_auth import FirebaseAuthService
from .schemas import AuthSessionResponse, LocalLoginRequest, LocalRegisterRequest, UserResponse
from .user_repository_dynamo import DynamoUserRepository
from .user_service import UserService

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


def get_firebase_auth() -> FirebaseAuthService:
    return FirebaseAuthService()


def get_user_repository() -> DynamoUserRepository:
    return DynamoUserRepository.from_env()


def get_user_service(repo: DynamoUserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(repo)


@auth_router.post("/login", response_model=UserResponse)
async def login(
    authorization: str = Header(...),
    auth_service: FirebaseAuthService = Depends(get_firebase_auth),
    user_service: UserService = Depends(get_user_service),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    token = authorization.split(" ", 1)[1]
    user_data = auth_service.get_user_from_token(token)
    return user_service.sync_user(user_data)


@auth_router.post("/register-local", response_model=AuthSessionResponse)
async def register_local_account(
    body: LocalRegisterRequest,
    user_service: UserService = Depends(get_user_service),
):
    return user_service.register_local_account(body)


@auth_router.post("/login-local", response_model=AuthSessionResponse)
async def login_local_account(
    body: LocalLoginRequest,
    user_service: UserService = Depends(get_user_service),
):
    return user_service.login_local_account(body)


async def get_current_user(
    authorization: str = Header(...),
    auth_service: FirebaseAuthService = Depends(get_firebase_auth),
    user_service: UserService = Depends(get_user_service),
) -> UserResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    token = authorization.split(" ", 1)[1]
    try:
        return user_service.get_user_from_local_token(token)
    except HTTPException:
        pass
    info = auth_service.get_user_from_token(token)
    return user_service.get_user_profile(info["uid"])


@users_router.get("/me", response_model=UserResponse)
async def get_me(user: UserResponse = Depends(get_current_user)):
    return user


@users_router.get("/", response_model=List[UserResponse])
async def list_users(
    user_service: UserService = Depends(get_user_service),
    skip: int = 0,
    limit: int = 100,
):
    return user_service.list_users(skip=skip, limit=limit)
