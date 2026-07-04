from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from .firebase_auth import FirebaseAuthService
from .schemas import AuthSessionResponse, LocalLoginRequest, LocalRegisterRequest, UserResponse, UserUpdate
from .user_repository_factory import get_user_repository_from_env
from .user_service import UserService

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


def get_firebase_auth() -> FirebaseAuthService:
    return FirebaseAuthService()


def get_user_repository():
    return get_user_repository_from_env()


def get_user_service(repo=Depends(get_user_repository)) -> UserService:
    return UserService(repo)


@auth_router.post("/login", response_model=UserResponse)
def login(
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
def register_local_account(
    body: LocalRegisterRequest,
    user_service: UserService = Depends(get_user_service),
):
    return user_service.register_local_account(body)


@auth_router.post("/login-local", response_model=AuthSessionResponse)
def login_local_account(
    body: LocalLoginRequest,
    user_service: UserService = Depends(get_user_service),
):
    return user_service.login_local_account(body)


def get_current_user(
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


def get_current_admin(user: UserResponse = Depends(get_current_user)) -> UserResponse:
    if (user.role or "").lower() != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role is required")
    if not bool(user.isActive):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin account is deactivated")
    return user


@users_router.get("/me", response_model=UserResponse)
def get_me(user: UserResponse = Depends(get_current_user)):
    return user


@users_router.patch("/me", response_model=UserResponse)
def update_me(
    body: UserUpdate,
    user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    safe_update = UserUpdate(
        username=body.username,
        displayName=body.displayName,
        photoURL=body.photoURL,
        persona=body.persona,
        educationDescription=body.educationDescription,
        lastLogin=body.lastLogin,
    )
    return user_service.update_user_profile(user.uid, safe_update)


@users_router.get("/{uid}", response_model=UserResponse)
def get_user_by_id(
    uid: str,
    user: UserResponse = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    if (user.role or "").lower() != "admin" and user.uid != uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this user")
    return user_service.get_user_profile(uid)


@users_router.get("/", response_model=List[UserResponse])
def list_users(
    user_service: UserService = Depends(get_user_service),
    _admin: UserResponse = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
    query: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
):
    return user_service.list_users(
        skip=skip,
        limit=limit,
        query=query,
        role=role,
        is_active=is_active,
    )
