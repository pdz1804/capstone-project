from __future__ import annotations

import logging
import os

from .user_repository_dynamo import DynamoUserRepository
from .user_repository_local import LocalFileUserRepository

logger = logging.getLogger(__name__)


def _allow_local_aws_fallback() -> bool:
    raw = str(os.getenv("ALLOW_LOCAL_AWS_FALLBACK", "true")).strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _aws_credentials_available(region: str | None = None) -> bool:
    try:
        import boto3

        session = boto3.session.Session(region_name=region or None)
        creds = session.get_credentials()
        if creds is None:
            return False
        frozen = creds.get_frozen_credentials()
        return bool(getattr(frozen, "access_key", None))
    except Exception as exc:
        logger.warning("Could not inspect AWS credentials for identity repository selection: %s", exc)
        return False


def get_user_repository_from_env():
    table_name = (os.getenv("DYNAMODB_USERS_TABLE") or "").strip()
    region = (os.getenv("AWS_REGION") or "").strip() or None
    if table_name and (_aws_credentials_available(region) or not _allow_local_aws_fallback()):
        return DynamoUserRepository.from_env()

    repo = LocalFileUserRepository.from_env()
    if table_name:
        logger.warning(
            "DYNAMODB_USERS_TABLE is set but AWS credentials are unavailable; "
            "using local JSON user store at %s",
            repo.default_path(),
        )
    else:
        logger.warning(
            "DYNAMODB_USERS_TABLE is not set; using local JSON user store at %s",
            repo.default_path(),
        )
    return repo
