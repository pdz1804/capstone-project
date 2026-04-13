from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.paths import merged_runtime_settings, qdrant_collection_names_for_user, sanitize_storage_user_id
from app.repositories import ImageIndexRepository, TextIndexRepository, build_qdrant_client
from app.repositories.knowledge_repository_dynamo import DynamoKnowledgeRepository
from app.storage import get_file_storage
from app.storage.service import parse_s3_uri


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _detect_knowledge_type(name: str) -> str:
    ext = Path((name or "").lower()).suffix
    if ext in {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md", ".rtf"}:
        return "document"
    if ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        return "video"
    if ext in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}:
        return "audio"
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"}:
        return "image"
    if ext in {".csv", ".xlsx", ".xls"}:
        return "spreadsheet"
    return "other"


def _build_knowledge_id(user_id: str, source_path: str) -> str:
    digest = hashlib.sha1(f"{user_id}|{source_path}".encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"kg_{digest}"


class KnowledgeService:
    _DISCOVERY_CACHE_TTL_SECONDS = 60.0
    _ROW_CACHE_TTL_SECONDS = 45.0
    _cached_s3_users: List[str] = []
    _cached_s3_users_at: float = 0.0
    _cached_rows_by_id: Dict[str, Dict[str, Any]] = {}
    _cached_rows_at: float = 0.0

    def __init__(self, repo: Optional[DynamoKnowledgeRepository] = None) -> None:
        self.repo = repo

    @classmethod
    def from_env(cls) -> "KnowledgeService":
        return cls(DynamoKnowledgeRepository.from_env())

    @classmethod
    def from_storage_only(cls) -> "KnowledgeService":
        return cls(repo=None)

    @classmethod
    def from_env_optional(cls) -> "KnowledgeService":
        try:
            return cls.from_env()
        except Exception:
            return cls.from_storage_only()

    def _is_storage_only(self) -> bool:
        return self.repo is None

    @staticmethod
    def _local_sidecar_path(source_path: str) -> Path:
        p = Path(source_path)
        return p.parent / f"{p.name}.metadata.json"

    @staticmethod
    def _ensure_s3_input_prefix() -> str:
        originals = (os.getenv("S3_ORIGINALS_BUCKET") or "").strip()
        processed = (os.getenv("S3_PROCESSED_BUCKET") or "").strip()
        legacy = (os.getenv("S3_BUCKET") or "").strip()
        default_input = "" if (originals and processed) else ("input/" if legacy else "")
        raw = os.getenv("S3_INPUT_PREFIX")
        value = (default_input if raw is None else str(raw).strip())
        if not value:
            return ""
        return value.rstrip("/") + "/"

    @staticmethod
    def _s3_isolation_enabled() -> bool:
        v = str(os.getenv("S3_USER_ISOLATION", "true")).strip().lower()
        return v not in {"0", "false", "no", "off"}

    def _read_sidecar(self, storage: Any, source_path: str) -> Dict[str, Any]:
        if source_path.startswith("s3://"):
            parsed = parse_s3_uri(source_path)
            if not parsed:
                return {}
            bucket, key = parsed
            client = getattr(storage, "_client", None)
            if client is None:
                return {}
            try:
                resp = client.get_object(Bucket=bucket, Key=f"{key}.metadata.json")
                raw = resp.get("Body").read()
                if not raw:
                    return {}
                data = json.loads(raw.decode("utf-8", errors="ignore"))
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}

        try:
            sidecar_path = self._local_sidecar_path(source_path)
            if not sidecar_path.exists():
                return {}
            with open(sidecar_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_sidecar(self, storage: Any, source_path: str, payload: Dict[str, Any]) -> None:
        if source_path.startswith("s3://"):
            parsed = parse_s3_uri(source_path)
            if not parsed:
                return
            bucket, key = parsed
            client = getattr(storage, "_client", None)
            if client is None:
                return
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            client.put_object(Bucket=bucket, Key=f"{key}.metadata.json", Body=body, ContentType="application/json")
            return

        sidecar_path = self._local_sidecar_path(source_path)
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sidecar_path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, indent=2)

    def _discover_storage_users(self, explicit_user_ids: Optional[List[str]] = None) -> List[str]:
        default_uid = sanitize_storage_user_id(os.getenv("DEFAULT_STORAGE_USER_ID", "default"))
        users: set[str] = {default_uid}

        for uid in explicit_user_ids or []:
            norm = sanitize_storage_user_id(uid)
            if norm:
                users.add(norm)

        # If caller already provides target users, skip expensive S3-wide discovery.
        if explicit_user_ids:
            return sorted(users)

        backend = str(os.getenv("FILE_STORAGE_BACKEND", "local")).strip().lower()
        if backend != "s3":
            return sorted(users)

        if not self._s3_isolation_enabled():
            return sorted(users)

        originals = (os.getenv("S3_ORIGINALS_BUCKET") or "").strip()
        legacy = (os.getenv("S3_BUCKET") or "").strip()
        bucket = originals or legacy
        if not bucket:
            return sorted(users)

        now = time.time()
        if now - type(self)._cached_s3_users_at <= type(self)._DISCOVERY_CACHE_TTL_SECONDS and type(self)._cached_s3_users:
            users.update(type(self)._cached_s3_users)
            return sorted(users)

        try:
            import boto3

            region = (os.getenv("AWS_REGION") or "").strip() or None
            client = boto3.client("s3", region_name=region)
            base_prefix = self._ensure_s3_input_prefix()
            prefix = f"{base_prefix}users/"
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents") or []:
                    key = str(obj.get("Key") or "")
                    if not key or key.endswith("/"):
                        continue
                    rel = key[len(base_prefix):] if base_prefix and key.startswith(base_prefix) else key
                    if not rel.startswith("users/"):
                        continue
                    parts = rel.split("/", 3)
                    if len(parts) < 3:
                        continue
                    uid = sanitize_storage_user_id(parts[1])
                    if uid:
                        users.add(uid)
        except Exception:
            pass

        discovered = sorted(users)
        type(self)._cached_s3_users = discovered
        type(self)._cached_s3_users_at = time.time()

        return discovered

    @classmethod
    def _invalidate_row_cache(cls) -> None:
        cls._cached_rows_at = 0.0
        cls._cached_rows_by_id = {}

    @staticmethod
    def _normalized_source_candidates(row: Dict[str, Any]) -> List[str]:
        source_path = str(row.get("source_path") or "").strip()
        title = str(row.get("title") or "").strip()
        source_name = Path(source_path).name if source_path else ""

        def _safe_stem(v: str) -> str:
            stem = Path(v).stem
            return re.sub(r"[^a-zA-Z0-9._-]+", "_", stem).strip("._").lower()

        candidates = {
            title,
            title.lower(),
            Path(title).name,
            Path(title).name.lower(),
            Path(title).stem,
            Path(title).stem.lower(),
            source_name,
            source_name.lower(),
            Path(source_name).stem,
            Path(source_name).stem.lower(),
            _safe_stem(title),
            _safe_stem(source_name),
        }
        return sorted({c for c in candidates if c})

    def _remove_indexed_vectors_for_row(self, row: Dict[str, Any]) -> Dict[str, int]:
        user_id = sanitize_storage_user_id(str(row.get("user_id") or ""))
        if not user_id:
            return {"removed_text_vectors": 0, "removed_image_vectors": 0}

        removed_text = 0
        removed_image = 0
        try:
            cfg = merged_runtime_settings()
            q = cfg.get("qdrant", {}) or {}
            text_col, image_col = qdrant_collection_names_for_user(
                q.get("text_collection", "edu_text_chunks"),
                q.get("image_collection", "edu_image_pages"),
                user_id,
            )
            client = build_qdrant_client(cfg)

            text_repo = TextIndexRepository(
                client,
                collection_name=text_col,
                vector_name=q.get("text_vector_name", "text"),
                vector_size=int(q.get("text_vector_size") or 384),
                storage_quantization=q.get("text_storage_quantization", "scalar"),
                on_disk_vectors=bool(q.get("text_on_disk_vectors", True)),
            )
            image_repo = ImageIndexRepository(
                client,
                collection_name=image_col,
                vector_name=q.get("image_vector_name", "colpali_multivec"),
                embedding_dim=int(q.get("image_vector_size") or 128),
                storage_quantization=q.get("image_storage_quantization", "scalar"),
            )

            for candidate in self._normalized_source_candidates(row):
                try:
                    removed_text += int(text_repo.delete_by_source(candidate, user_id=user_id) or 0)
                except Exception:
                    pass
                try:
                    removed_image += int(image_repo.delete_by_source(candidate, user_id=user_id) or 0)
                except Exception:
                    pass
        except Exception:
            pass

        return {
            "removed_text_vectors": removed_text,
            "removed_image_vectors": removed_image,
        }

    def _scan_uploaded_rows(self, user_ids: Optional[List[str]] = None, limit: int | None = 1000) -> List[Dict[str, Any]]:
        discovered_users = self._discover_storage_users(user_ids)
        by_id: Dict[str, Dict[str, Any]] = {}
        limit_n: int | None
        if limit is None:
            limit_n = None
        else:
            try:
                limit_n = max(1, int(limit))
            except Exception:
                limit_n = None

        scan_cap = (limit_n * 5) if limit_n is not None else None

        for uid in discovered_users:
            try:
                storage = get_file_storage(uid)
                rows = storage.list_input_files()
            except Exception:
                continue

            for row in rows:
                name = str(row.get("name") or "").strip()
                source_path = str(row.get("path") or "").strip()
                if not name or not source_path:
                    continue

                sidecar = self._read_sidecar(storage, source_path)
                owner = sanitize_storage_user_id(str(sidecar.get("user_id") or uid))
                created_at = str(sidecar.get("upload_time") or row.get("modified") or _iso_now())
                updated_at = str(sidecar.get("knowledge_updated_at") or created_at)
                tags_raw = sidecar.get("knowledge_tags") or []
                tags = [str(x).strip() for x in tags_raw if str(x).strip()] if isinstance(tags_raw, list) else []

                item = {
                    "knowledge_id": _build_knowledge_id(owner, source_path),
                    "user_id": owner,
                    "title": str(sidecar.get("knowledge_title") or name),
                    "source_path": source_path,
                    "knowledge_type": str(sidecar.get("knowledge_type") or _detect_knowledge_type(name)),
                    "status": str(sidecar.get("knowledge_status") or "uploaded"),
                    "is_active": bool(sidecar.get("knowledge_is_active", True)),
                    "tags": tags,
                    "notes": str(sidecar.get("knowledge_notes") or ""),
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
                by_id[item["knowledge_id"]] = item

                if scan_cap is not None and len(by_id) >= scan_cap:
                    break

            if scan_cap is not None and len(by_id) >= scan_cap:
                break

        out = list(by_id.values())
        out.sort(key=lambda x: str(x.get("updated_at") or ""), reverse=True)
        type(self)._cached_rows_by_id = {str(x.get("knowledge_id") or ""): x for x in out if str(x.get("knowledge_id") or "")}
        type(self)._cached_rows_at = time.time()
        if limit_n is None:
            return out
        return out[:limit_n]

    def _find_uploaded_row(self, knowledge_id: str) -> Dict[str, Any] | None:
        now = time.time()
        if now - type(self)._cached_rows_at <= type(self)._ROW_CACHE_TTL_SECONDS:
            cached = type(self)._cached_rows_by_id.get(knowledge_id)
            if cached:
                return cached

        rows = self._scan_uploaded_rows(limit=20000)
        for row in rows:
            if str(row.get("knowledge_id") or "") == knowledge_id:
                return row
        return None

    def _apply_sidecar_updates(self, row: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any] | None:
        source_path = str(row.get("source_path") or "").strip()
        user_id = sanitize_storage_user_id(str(row.get("user_id") or ""))
        if not source_path or not user_id:
            return None

        storage = get_file_storage(user_id)
        current = self._read_sidecar(storage, source_path)

        if not current:
            current = {
                "metadata_version": "1.0",
                "original_filename": row.get("title") or Path(source_path).name,
                "file_path": source_path,
                "upload_time": row.get("created_at") or _iso_now(),
                "upload_source": "admin",
                "user_id": user_id,
                "status": "pending",
                "completed_stages": ["upload"],
                "processing_start_time": None,
                "processing_end_time": None,
                "error_message": None,
                "error_details": None,
            }

        if payload.get("status") is not None:
            current["knowledge_status"] = str(payload.get("status") or "uploaded")
        if payload.get("is_active") is not None:
            current["knowledge_is_active"] = bool(payload.get("is_active"))
        if payload.get("tags") is not None:
            tags_raw = payload.get("tags") or []
            current["knowledge_tags"] = [str(x).strip() for x in tags_raw if str(x).strip()]
        if payload.get("notes") is not None:
            current["knowledge_notes"] = str(payload.get("notes") or "")
        if payload.get("title") is not None:
            current["knowledge_title"] = str(payload.get("title") or "").strip() or str(row.get("title") or "")
        if payload.get("knowledge_type") is not None:
            current["knowledge_type"] = str(payload.get("knowledge_type") or "").strip() or str(row.get("knowledge_type") or "other")

        current["knowledge_updated_at"] = _iso_now()
        self._write_sidecar(storage, source_path, current)
        type(self)._invalidate_row_cache()

        refreshed = self._find_uploaded_row(str(row.get("knowledge_id") or ""))
        return refreshed

    def create(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._is_storage_only():
            user_id = sanitize_storage_user_id(str(payload.get("user_id") or "").strip())
            source_path = str(payload.get("source_path") or "").strip()
            if not user_id:
                raise ValueError("user_id is required")
            if not source_path:
                raise ValueError("source_path is required and must point to an uploaded file")

            rows = self._scan_uploaded_rows(user_ids=[user_id], limit=20000)
            match = None
            for row in rows:
                if str(row.get("source_path") or "") == source_path:
                    match = row
                    break
            if not match:
                raise ValueError("source_path does not match an uploaded file")

            updated = self._apply_sidecar_updates(match, payload)
            if not updated:
                raise ValueError("Failed to create knowledge metadata")
            return updated

        user_id = str(payload.get("user_id") or "").strip()
        title = str(payload.get("title") or "").strip()
        source_path = str(payload.get("source_path") or "").strip()
        if not user_id:
            raise ValueError("user_id is required")
        if not title:
            raise ValueError("title is required")

        knowledge_id = str(payload.get("knowledge_id") or "").strip() or _build_knowledge_id(user_id, source_path or title)
        item = {
            "knowledge_id": knowledge_id,
            "user_id": user_id,
            "title": title,
            "source_path": source_path,
            "knowledge_type": str(payload.get("knowledge_type") or _detect_knowledge_type(title)),
            "status": str(payload.get("status") or "uploaded"),
            "is_active": bool(payload.get("is_active", True)),
            "tags": payload.get("tags") or [],
            "notes": str(payload.get("notes") or ""),
            "created_at": payload.get("created_at") or _iso_now(),
            "updated_at": _iso_now(),
        }
        if self.repo is None:
            raise ValueError("Knowledge persistence is not configured")
        return self.repo.create(item)

    def upsert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._is_storage_only():
            return self.create(payload)

        user_id = str(payload.get("user_id") or "").strip()
        title = str(payload.get("title") or "").strip()
        source_path = str(payload.get("source_path") or "").strip()
        if not user_id:
            raise ValueError("user_id is required")
        if not title:
            raise ValueError("title is required")

        knowledge_id = str(payload.get("knowledge_id") or "").strip() or _build_knowledge_id(user_id, source_path or title)
        current = self.repo.get(knowledge_id)
        item = {
            "knowledge_id": knowledge_id,
            "user_id": user_id,
            "title": title,
            "source_path": source_path,
            "knowledge_type": str(payload.get("knowledge_type") or _detect_knowledge_type(title)),
            "status": str(payload.get("status") or (current or {}).get("status") or "uploaded"),
            "is_active": bool(payload.get("is_active", (current or {}).get("is_active", True))),
            "tags": payload.get("tags") if payload.get("tags") is not None else (current or {}).get("tags", []),
            "notes": str(payload.get("notes") if payload.get("notes") is not None else (current or {}).get("notes", "")),
            "created_at": (current or {}).get("created_at") or _iso_now(),
            "updated_at": _iso_now(),
        }
        if self.repo is None:
            raise ValueError("Knowledge persistence is not configured")
        return self.repo.upsert(item)

    def get(self, knowledge_id: str) -> Dict[str, Any] | None:
        if self._is_storage_only():
            return self._find_uploaded_row(knowledge_id)
        if self.repo is None:
            return None
        return self.repo.get(knowledge_id)

    def update(self, knowledge_id: str, payload: Dict[str, Any]) -> Dict[str, Any] | None:
        if self._is_storage_only():
            row = self._find_uploaded_row(knowledge_id)
            if not row:
                return None
            return self._apply_sidecar_updates(row, payload)
        if self.repo is None:
            return None
        return self.repo.update(knowledge_id, payload)

    def delete(self, knowledge_id: str) -> bool:
        report = self.delete_with_report(knowledge_id)
        return bool(report.get("deleted"))

    def delete_with_report(self, knowledge_id: str) -> Dict[str, Any]:
        if self._is_storage_only():
            row = self._find_uploaded_row(knowledge_id)
            if not row:
                return {
                    "deleted": False,
                    "knowledge_id": knowledge_id,
                    "removed_text_vectors": 0,
                    "removed_image_vectors": 0,
                }
            source_path = str(row.get("source_path") or "")
            user_id = sanitize_storage_user_id(str(row.get("user_id") or ""))
            if not source_path or not user_id:
                return {
                    "deleted": False,
                    "knowledge_id": knowledge_id,
                    "removed_text_vectors": 0,
                    "removed_image_vectors": 0,
                }

            index_cleanup = self._remove_indexed_vectors_for_row(row)
            try:
                storage = get_file_storage(user_id)
                deleted = bool(storage.delete(source_path))
                if deleted:
                    type(self)._invalidate_row_cache()
                return {
                    "deleted": deleted,
                    "knowledge_id": knowledge_id,
                    "source_path": source_path,
                    "user_id": user_id,
                    **index_cleanup,
                }
            except Exception:
                return {
                    "deleted": False,
                    "knowledge_id": knowledge_id,
                    "source_path": source_path,
                    "user_id": user_id,
                    **index_cleanup,
                }
        if self.repo is None:
            return {
                "deleted": False,
                "knowledge_id": knowledge_id,
                "removed_text_vectors": 0,
                "removed_image_vectors": 0,
            }
        deleted = bool(self.repo.delete(knowledge_id))
        return {
            "deleted": deleted,
            "knowledge_id": knowledge_id,
            "removed_text_vectors": 0,
            "removed_image_vectors": 0,
        }

    def list(
        self,
        *,
        user_id: str | None = None,
        known_user_ids: Optional[List[str]] = None,
        knowledge_type: str | None = None,
        is_active: bool | None = None,
        query: str | None = None,
        limit: int | None = 1000,
    ) -> List[Dict[str, Any]]:
        if self._is_storage_only():
            user_filter = sanitize_storage_user_id(user_id) if user_id else None
            scan_users = [user_filter] if user_filter else known_user_ids
            scan_limit = None if limit is None else max(limit, 5000)
            rows = self._scan_uploaded_rows(user_ids=scan_users, limit=scan_limit)
            q = (query or "").strip().lower()
            ktype = (knowledge_type or "").strip().lower()

            if user_filter:
                rows = [x for x in rows if str(x.get("user_id") or "") == user_filter]
            if ktype:
                rows = [x for x in rows if str(x.get("knowledge_type") or "").lower() == ktype]
            if is_active is not None:
                rows = [x for x in rows if bool(x.get("is_active", True)) == bool(is_active)]
            if q:
                rows = [
                    x
                    for x in rows
                    if q in str(x.get("title") or "").lower()
                    or q in str(x.get("source_path") or "").lower()
                    or q in str(x.get("user_id") or "").lower()
                    or q in str(x.get("knowledge_id") or "").lower()
                ]
            rows.sort(key=lambda x: str(x.get("updated_at") or ""), reverse=True)
            if limit is None:
                return rows
            return rows[:limit]

        if self.repo is None:
            return []
        return self.repo.list(
            user_id=user_id,
            knowledge_type=knowledge_type,
            is_active=is_active,
            query=query,
            limit=limit,
        )

    def sync_input_files_for_users(self, user_ids: Optional[List[str]]) -> int:
        if self._is_storage_only():
            rows = self._scan_uploaded_rows(user_ids=user_ids, limit=50000)
            return len(rows)

        if not user_ids:
            return 0

        synced = 0
        for user_id in user_ids:
            if not user_id:
                continue
            try:
                storage = get_file_storage(user_id)
                rows = storage.list_input_files()
            except Exception:
                continue

            for row in rows:
                name = str(row.get("name") or "").strip()
                path = str(row.get("path") or "").strip()
                if not name:
                    continue
                item = {
                    "user_id": user_id,
                    "title": name,
                    "source_path": path,
                    "knowledge_type": _detect_knowledge_type(name),
                    "status": "uploaded",
                    "is_active": True,
                }
                self.upsert(item)
                synced += 1
        return synced
