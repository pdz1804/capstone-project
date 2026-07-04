"""Shared FastAPI dependencies."""

from __future__ import annotations

import os

from fastapi import Header

from app.core.paths import sanitize_storage_user_id


def storage_user_id(
    x_user_id: str | None = Header(
        None,
        alias="X-User-Id",
        description="Logical tenant/user id for S3 key prefixes and workspace isolation. "
        "Defaults to DEFAULT_STORAGE_USER_ID or 'default'.",
    ),
) -> str:
    return sanitize_storage_user_id(x_user_id or os.getenv("DEFAULT_STORAGE_USER_ID", "default"))
