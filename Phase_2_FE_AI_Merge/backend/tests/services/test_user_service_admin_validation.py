from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.identity.schemas import UserCreate, UserResponse, UserUpdate
from app.identity.user_service import UserService


class _FakeUserRepo:
    def __init__(self, users: dict[str, UserResponse]) -> None:
        self.users = users

    def get_by_id(self, uid: str):
        return self.users.get(uid)

    def get_item_by_username(self, username: str):
        lookup = (username or '').strip().lower()
        for u in self.users.values():
            if (u.username or '').strip().lower() == lookup:
                return {'uid': u.uid, 'username': u.username}
        return None

    def get_item_by_email(self, email: str):
        lookup = (email or '').strip().lower()
        for u in self.users.values():
            if (u.email or '').strip().lower() == lookup:
                return {'uid': u.uid, 'email': u.email}
        return None

    def update(self, uid: str, user_in: UserUpdate):
        current = self.users.get(uid)
        if not current:
            return None
        data = current.model_dump()
        data.update(user_in.model_dump(exclude_unset=True))
        updated = UserResponse(**data)
        self.users[uid] = updated
        return updated

    def set_local_auth_credentials(self, uid: str, password_hash: str):
        current = self.users.get(uid)
        if not current:
            return None
        data = current.model_dump()
        data.update({'authProvider': 'local'})
        updated = UserResponse(**data)
        self.users[uid] = updated
        return updated

    def delete(self, uid: str) -> bool:
        return self.users.pop(uid, None) is not None

    def list(self, skip: int = 0, limit: int = 100):
        rows = list(self.users.values())
        if limit is None:
            return rows[skip:]
        return rows[skip: skip + limit]

    def create(self, user_in: UserCreate):
        created = UserResponse(
            uid=user_in.uid,
            email=str(user_in.email),
            username=user_in.username,
            displayName=user_in.displayName,
            role=user_in.role,
            isActive=bool(user_in.isActive),
            photoURL=user_in.photoURL,
            persona=user_in.persona,
            educationDescription=user_in.educationDescription,
            authProvider=user_in.authProvider,
            createdAt=datetime.now(timezone.utc),
            lastLogin=datetime.now(timezone.utc),
        )
        self.users[created.uid] = created
        return created



def _user(uid: str, email: str, username: str, *, role: str = 'student') -> UserResponse:
    return UserResponse(
        uid=uid,
        email=email,
        username=username,
        displayName='Name',
        role=role,
        isActive=True,
        photoURL=None,
        persona=None,
        educationDescription=None,
        authProvider='local',
        createdAt=datetime.now(timezone.utc),
        lastLogin=None,
    )


@pytest.mark.unit
def test_update_user_profile_rejects_invalid_role():
    repo = _FakeUserRepo({'u1': _user('u1', 'u1@example.com', 'user1')})
    svc = UserService(repo)  # type: ignore[arg-type]

    with pytest.raises(HTTPException) as exc:
        svc.update_user_profile('u1', UserUpdate(role='superadmin'))

    assert exc.value.status_code == 400
    assert 'Invalid role' in str(exc.value.detail)


@pytest.mark.unit
def test_update_user_profile_rejects_duplicate_username():
    repo = _FakeUserRepo(
        {
            'u1': _user('u1', 'u1@example.com', 'alpha'),
            'u2': _user('u2', 'u2@example.com', 'beta'),
        }
    )
    svc = UserService(repo)  # type: ignore[arg-type]

    with pytest.raises(HTTPException) as exc:
        svc.update_user_profile('u1', UserUpdate(username='beta'))

    assert exc.value.status_code == 409
    assert 'Username already exists' in str(exc.value.detail)


@pytest.mark.unit
def test_update_user_profile_normalizes_username():
    repo = _FakeUserRepo({'u1': _user('u1', 'u1@example.com', 'alpha')})
    svc = UserService(repo)  # type: ignore[arg-type]

    updated = svc.update_user_profile('u1', UserUpdate(username='  NewUser  '))

    assert updated.username == 'newuser'


@pytest.mark.unit
def test_ensure_default_admin_account_keeps_one(monkeypatch: pytest.MonkeyPatch):
    repo = _FakeUserRepo(
        {
            'u1': _user('u1', 'admin@local.dev', 'admin', role='admin'),
            'u2': _user('u2', 'admin2@example.com', 'otheradmin', role='admin'),
            'u3': _user('u3', 'student@example.com', 'admin', role='student'),
            'u4': _user('u4', 'admin3@example.com', 'a3', role='admin'),
        }
    )
    svc = UserService(repo)  # type: ignore[arg-type]

    monkeypatch.setenv('ENABLE_DEFAULT_ADMIN_BOOTSTRAP', 'true')
    monkeypatch.setenv('DEFAULT_ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('DEFAULT_ADMIN_EMAIL', 'admin@local.dev')
    monkeypatch.setenv('DEFAULT_ADMIN_PASSWORD', 'quangphu1804')

    keep = svc.ensure_default_admin_account()

    assert keep is not None
    assert keep.email == 'admin@local.dev'
    assert keep.username == 'admin'
    assert keep.role == 'admin'
    assert keep.isActive is True

    all_rows = repo.list(skip=0, limit=100)
    admins = [u for u in all_rows if (u.role or '').lower() == 'admin']
    assert len(admins) == 1
    assert admins[0].email == 'admin@local.dev'
