"""Pluggable file storage (local filesystem vs S3)."""

from app.storage.service import FileStorageService, get_file_storage, reset_file_storage_singleton

__all__ = ["FileStorageService", "get_file_storage", "reset_file_storage_singleton"]
