"""Local vs S3 storage for uploads, pipeline I/O, and file management APIs."""

from __future__ import annotations

import logging
import os
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.services.file_metadata_service import FileMetadataService

logger = logging.getLogger(__name__)

# --- shared row shape for API (matches historical files_routes fields) ---


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _iso_from_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def parse_s3_uri(uri: str) -> Optional[Tuple[str, str]]:
    if not uri.startswith("s3://"):
        return None
    rest = uri[5:]
    if "/" not in rest:
        return None
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        return None
    return bucket, key


class FileStorageService(ABC):
    """Uploads, listing, delete, and pipeline sync hooks."""

    backend_name: str

    @abstractmethod
    def list_input_files(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_processed_files(self, include_preview: bool) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def save_upload(self, original_filename: str, content: bytes, user_id: str = "unknown") -> Dict[str, Any]:
        """Persist one upload; return a file row including `path` for delete/API."""

    @abstractmethod
    def delete(self, path_or_uri: str) -> bool:
        """Return True if something was removed."""

    @abstractmethod
    def prepare_pipeline_input(self, local_input_dir: Path, selected_paths: Optional[List[str]] = None) -> None:
        """Ensure local_input_dir contains inputs the pipeline expects."""

    @abstractmethod
    def publish_pipeline_output(self, local_processing_dir: Path) -> None:
        """After a successful run, persist processing tree (no-op for local-only)."""

    @abstractmethod
    def resolve_pdf_path(
        self,
        pdf_name: str,
        local_rag_ready: Path,
        local_input_dir: Path,
    ) -> Tuple[Optional[Path], bool]:
        """Return (local Path, remove_after_use). Second flag True for temp downloads."""

    def can_read_object(self, bucket: str, key: str) -> bool:
        """S3-only tenant check; local backend ignores."""
        return True


class LocalFileStorage(FileStorageService):
    backend_name = "local"

    def __init__(self, input_dir: Path, output_dir: Path) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.processing_dir = output_dir / "processing"

    def list_input_files(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if self.input_dir.exists():
            for f in self.input_dir.rglob("*"):
                if f.is_file() and not f.name.startswith("."):
                    if f.name.endswith(".metadata.json"):
                        continue
                    rows.append(self._file_info_path(f))
        return rows

    def list_processed_files(self, include_preview: bool) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if not self.processing_dir.exists():
            return rows
        text_suffixes = {".json", ".md", ".txt"}
        for stage_dir in self.processing_dir.iterdir():
            if not stage_dir.is_dir():
                continue
            for f in stage_dir.rglob("*"):
                if f.is_file() and f.suffix.lower() in text_suffixes:
                    info = self._file_info_path(f)
                    info["stage"] = stage_dir.name
                    if include_preview:
                        try:
                            with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                                chunk = fp.read(500)
                            info["preview"] = chunk + ("..." if len(chunk) >= 500 else "")
                        except OSError:
                            pass
                    rows.append(info)
        return rows

    def save_upload(self, original_filename: str, content: bytes, user_id: str = "unknown") -> Dict[str, Any]:
        safe_name = Path(original_filename).name
        if not safe_name:
            safe_name = "unnamed"
        dest = self.input_dir / safe_name
        if dest.exists():
            base, suffix = dest.stem, dest.suffix
            c = 1
            while dest.exists():
                dest = self.input_dir / f"{base}_{c}{suffix}"
                c += 1
        self.input_dir.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        row = self._file_info_path(dest)
        row["storage"] = self.backend_name
        
        # Create and save metadata for the uploaded file
        try:
            metadata_svc = FileMetadataService()
            metadata_svc.create_metadata(
                original_filename=original_filename,
                file_path=dest,
                file_content=content,
                user_id=user_id,
                upload_source="api",
            )
            row["metadata"] = {
                "status": "pending",
                "created": True,
            }
        except Exception as e:
            logger.warning(f"Failed to create metadata for {dest}: {e}")
            row["metadata"] = {
                "status": "pending",
                "created": False,
                "error": str(e),
            }
        
        return row

    def delete(self, path_or_uri: str) -> bool:
        p = Path(path_or_uri)
        try:
            p = p.resolve()
        except OSError:
            return False
        if not p.exists() or not p.is_file():
            return False
        roots = (self.input_dir.resolve(), self.output_dir.resolve())
        if not any(self._is_under(p, r) for r in roots):
            return False
        
        # Clean up metadata file if it exists
        try:
            metadata_svc = FileMetadataService()
            metadata_svc.cleanup_metadata(p)
        except Exception as e:
            logger.warning(f"Failed to clean up metadata for {p}: {e}")
        
        p.unlink()
        return True

    @staticmethod
    def _is_under(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def prepare_pipeline_input(self, local_input_dir: Path, selected_paths: Optional[List[str]] = None) -> None:
        return None

    def publish_pipeline_output(self, local_processing_dir: Path) -> None:
        return None

    def resolve_pdf_path(
        self,
        pdf_name: str,
        local_rag_ready: Path,
        local_input_dir: Path,
    ) -> Tuple[Optional[Path], bool]:
        if not pdf_name.endswith(".pdf"):
            pdf_name = pdf_name + ".pdf"
        if local_rag_ready.exists():
            for f in local_rag_ready.rglob("*.pdf"):
                if f.name == pdf_name:
                    return f, False
        if local_input_dir.exists():
            for f in local_input_dir.rglob("*.pdf"):
                if f.name == pdf_name:
                    return f, False
        return None, False

    def _file_info_path(self, file_path: Path) -> Dict[str, Any]:
        stat = file_path.stat()
        return {
            "name": file_path.name,
            "path": str(file_path.resolve()),
            "size": _human_size(stat.st_size),
            "modified": _iso_from_ts(stat.st_mtime),
            "type": file_path.suffix.lower(),
            "storage": self.backend_name,
        }


def _normalize_s3_prefix(raw: Optional[str], default_if_unset: str) -> str:
    """Return prefix ending with '/' or '' for bucket root. Env '' means root."""
    if raw is None:
        s = default_if_unset
    else:
        s = raw.strip()
    if not s:
        return ""
    return s.rstrip("/") + "/"


class S3FileStorage(FileStorageService):
    backend_name = "s3"

    def __init__(
        self,
        originals_bucket: str,
        processed_bucket: str,
        input_prefix: str,
        processing_prefix: str,
        local_input_dir: Path,
        local_output_dir: Path,
        region: Optional[str] = None,
        s3_client: Any = None,
    ) -> None:
        self.originals_bucket = originals_bucket
        self.processed_bucket = processed_bucket
        self.input_prefix = input_prefix
        self.processing_prefix = processing_prefix
        self.local_input_dir = local_input_dir
        self.local_output_dir = local_output_dir
        self.local_processing_dir = local_output_dir / "processing"
        if s3_client is not None:
            self._client = s3_client
        else:
            import boto3

            session = boto3.session.Session(region_name=region or None)
            self._client = session.client("s3")

    def _key_input(self, relative_name: str) -> str:
        rel = relative_name.lstrip("/").replace("\\", "/")
        return f"{self.input_prefix}{rel}" if self.input_prefix else rel

    def _key_processing(self, relative: str) -> str:
        rel = relative.lstrip("/").replace("\\", "/")
        return f"{self.processing_prefix}{rel}" if self.processing_prefix else rel

    def _uri(self, bucket: str, key: str) -> str:
        return f"s3://{bucket}/{key}"

    def processed_uri(self, relative_path: str) -> str:
        key = self._key_processing(relative_path)
        return self._uri(self.processed_bucket, key)

    def write_processed_bytes(
        self, relative_path: str, data: bytes, content_type: Optional[str] = None
    ) -> str:
        key = self._key_processing(relative_path)
        kwargs: Dict[str, Any] = {"Bucket": self.processed_bucket, "Key": key, "Body": data}
        if content_type:
            kwargs["ContentType"] = content_type
        self._client.put_object(**kwargs)
        return self._uri(self.processed_bucket, key)

    def read_processed_bytes(self, relative_path: str) -> Optional[bytes]:
        from botocore.exceptions import ClientError

        key = self._key_processing(relative_path)
        try:
            obj = self._client.get_object(Bucket=self.processed_bucket, Key=key)
            return obj["Body"].read()
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    def read_object(self, bucket: str, key: str) -> Tuple[bytes, Optional[str]]:
        """Download object body; used for image streaming."""
        if bucket not in (self.originals_bucket, self.processed_bucket):
            raise ValueError("bucket not allowed for this storage backend")
        obj = self._client.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read(), obj.get("ContentType")

    def can_read_object(self, bucket: str, key: str) -> bool:
        """True if ``key`` is under this instance's configured prefixes (tenant-safe GET)."""
        if bucket == self.originals_bucket:
            if not self.input_prefix:
                return True
            return key.startswith(self.input_prefix)
        if bucket == self.processed_bucket:
            if not self.processing_prefix:
                return True
            return key.startswith(self.processing_prefix)
        return False

    def uri_for_local_under_processing(self, file_path: Path) -> Optional[str]:
        """``s3://`` URI in the processed bucket for a path under the local processing root."""
        try:
            root = self.local_processing_dir.resolve()
            p = Path(file_path).resolve()
            rel = p.relative_to(root).as_posix()
        except (ValueError, OSError):
            return None
        key = self._key_processing(rel)
        return self._uri(self.processed_bucket, key)

    def uri_for_local_under_input(self, file_path: Path) -> Optional[str]:
        """``s3://`` URI in the originals bucket for a path under the local input root."""
        try:
            root = self.local_input_dir.resolve()
            p = Path(file_path).resolve()
            rel = p.relative_to(root).as_posix()
        except (ValueError, OSError):
            return None
        key = self._key_input(rel)
        return self._uri(self.originals_bucket, key)

    def list_input_files(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.originals_bucket, Prefix=self.input_prefix):
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                rel = key[len(self.input_prefix) :] if self.input_prefix else key
                name = rel.split("/")[-1] if rel else key
                if name.startswith("."):
                    continue
                if name.endswith(".metadata.json"):
                    # Sidecar metadata object, not a user-uploaded original file.
                    continue
                lm = obj["LastModified"]
                if lm.tzinfo is None:
                    lm = lm.replace(tzinfo=timezone.utc)
                rows.append(
                    {
                        "name": name,
                        "path": self._uri(self.originals_bucket, key),
                        "size": _human_size(obj["Size"]),
                        "modified": lm.isoformat(),
                        "type": Path(name).suffix.lower(),
                        "storage": self.backend_name,
                    }
                )
        return rows

    def list_processed_files(self, include_preview: bool) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        text_suffixes = {".json", ".md", ".txt"}
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.processed_bucket, Prefix=self.processing_prefix):
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                suf = Path(key).suffix.lower()
                if suf not in text_suffixes:
                    continue
                rel = key[len(self.processing_prefix) :] if self.processing_prefix else key
                parts = rel.split("/") if rel else []
                stage = parts[0] if parts else ""
                name = Path(key).name
                lm = obj["LastModified"]
                if lm.tzinfo is None:
                    lm = lm.replace(tzinfo=timezone.utc)
                info: Dict[str, Any] = {
                    "name": name,
                    "path": self._uri(self.processed_bucket, key),
                    "size": _human_size(obj["Size"]),
                    "modified": lm.isoformat(),
                    "type": suf,
                    "stage": stage,
                    "storage": self.backend_name,
                }
                if include_preview:
                    try:
                        prev = self._client.get_object(
                            Bucket=self.processed_bucket,
                            Key=key,
                            Range="bytes=0-499",
                        )
                        body = prev["Body"].read()
                        text = body.decode("utf-8", errors="ignore")
                        info["preview"] = text + ("..." if obj["Size"] > 500 else "")
                    except Exception as e:
                        logger.debug("S3 preview skip %s: %s", key, e)
                rows.append(info)
        return rows

    def save_upload(self, original_filename: str, content: bytes, user_id: str = "unknown") -> Dict[str, Any]:
        safe_name = Path(original_filename).name
        if not safe_name:
            safe_name = "unnamed"
        key = self._key_input(safe_name)
        if self._head_exists(key):
            stem, suffix = Path(safe_name).stem, Path(safe_name).suffix
            c = 1
            while self._head_exists(self._key_input(f"{stem}_{c}{suffix}")):
                c += 1
            safe_name = f"{stem}_{c}{suffix}"
            key = self._key_input(safe_name)
        self._client.put_object(Bucket=self.originals_bucket, Key=key, Body=content)
        head = self._client.head_object(Bucket=self.originals_bucket, Key=key)
        lm = head["LastModified"]
        if lm.tzinfo is None:
            lm = lm.replace(tzinfo=timezone.utc)
        
        uri = self._uri(self.originals_bucket, key)
        row = {
            "name": safe_name,
            "path": uri,
            "size": _human_size(len(content)),
            "modified": lm.isoformat(),
            "type": Path(safe_name).suffix.lower(),
            "storage": self.backend_name,
        }
        
        # Create and save metadata sidecar in S3 (same folder as original file)
        try:
            metadata_key = f"{key}.metadata.json"
            meta_payload = {
                "metadata_version": "1.0",
                "original_filename": original_filename,
                "file_path": uri,
                "file_size": len(content),
                "file_hash": hashlib.sha256(content).hexdigest(),
                "upload_time": datetime.now(timezone.utc).isoformat(),
                "upload_source": "api",
                "user_id": user_id,
                "status": "pending",
                "completed_stages": ["upload"],
                "processing_start_time": None,
                "processing_end_time": None,
                "error_message": None,
                "error_details": None,
            }
            self._client.put_object(
                Bucket=self.originals_bucket,
                Key=metadata_key,
                Body=json.dumps(meta_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
            row["metadata"] = {
                "status": "pending",
                "created": True,
                "path": self._uri(self.originals_bucket, metadata_key),
            }
        except Exception as e:
            logger.warning(f"Failed to create metadata for {uri}: {e}")
            row["metadata"] = {
                "status": "pending",
                "created": False,
                "error": str(e),
            }
        
        return row

    def _head_exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self.originals_bucket, Key=key)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def delete(self, path_or_uri: str) -> bool:
        parsed = parse_s3_uri(path_or_uri)
        if not parsed:
            return False
        bucket, key = parsed
        if bucket == self.originals_bucket:
            if self.input_prefix and not key.startswith(self.input_prefix):
                return False
        elif bucket == self.processed_bucket:
            if self.processing_prefix and not key.startswith(self.processing_prefix):
                return False
        else:
            return False
        
        try:
            # Clean up S3 metadata sidecar (best-effort).
            try:
                self._client.delete_object(Bucket=bucket, Key=f"{key}.metadata.json")
            except Exception as e:
                logger.warning("S3 metadata delete skipped for %s: %s", key, e)

            self._client.delete_object(Bucket=bucket, Key=key)
            return True
        except Exception as e:
            logger.warning("S3 delete failed %s: %s", key, e)
            return False

    def prepare_pipeline_input(self, local_input_dir: Path, selected_paths: Optional[List[str]] = None) -> None:
        local_input_dir.mkdir(parents=True, exist_ok=True)
        for p in local_input_dir.iterdir():
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                import shutil

                shutil.rmtree(p, ignore_errors=True)

        allowed_keys: set[str] = set()
        if selected_paths:
            for raw in selected_paths:
                parsed = parse_s3_uri(raw)
                if parsed:
                    bucket, key = parsed
                    if bucket == self.originals_bucket:
                        allowed_keys.add(key)

        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.originals_bucket, Prefix=self.input_prefix):
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                if allowed_keys and key not in allowed_keys:
                    continue
                if key.endswith("/"):
                    continue
                rel = (
                    key[len(self.input_prefix) :].lstrip("/")
                    if self.input_prefix
                    else key.lstrip("/")
                )
                if not rel or ".." in rel.split("/"):
                    continue
                dest = local_input_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                self._client.download_file(self.originals_bucket, key, str(dest))

    def publish_pipeline_output(self, local_processing_dir: Path) -> None:
        if not local_processing_dir.exists():
            return
        files = [f for f in local_processing_dir.rglob("*") if f.is_file()]
        if not files:
            return

        max_workers_raw = os.getenv("S3_UPLOAD_MAX_WORKERS", "8").strip()
        try:
            max_workers = max(1, min(32, int(max_workers_raw)))
        except ValueError:
            max_workers = 8

        def _upload_one(file_path: Path) -> None:
            rel = file_path.relative_to(local_processing_dir).as_posix()
            key = self._key_processing(rel)
            ct = _guess_content_type(file_path.name)
            if ct:
                self._client.upload_file(
                    str(file_path), self.processed_bucket, key, ExtraArgs={"ContentType": ct}
                )
            else:
                self._client.upload_file(str(file_path), self.processed_bucket, key)

        if max_workers == 1 or len(files) == 1:
            for f in files:
                _upload_one(f)
            return

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_upload_one, f) for f in files]
            for fut in as_completed(futures):
                fut.result()

    def resolve_pdf_path(
        self,
        pdf_name: str,
        local_rag_ready: Path,
        local_input_dir: Path,
    ) -> Tuple[Optional[Path], bool]:
        if not pdf_name.endswith(".pdf"):
            pdf_name = pdf_name + ".pdf"
        if local_rag_ready.exists():
            for f in local_rag_ready.rglob("*.pdf"):
                if f.name == pdf_name:
                    return f, False
        if local_input_dir.exists():
            for f in local_input_dir.rglob("*.pdf"):
                if f.name == pdf_name:
                    return f, False
        import tempfile

        paginator = self._client.get_paginator("list_objects_v2")
        candidates: List[Tuple[str, str]] = []
        for page in paginator.paginate(Bucket=self.processed_bucket, Prefix=self.processing_prefix):
            for obj in page.get("Contents") or []:
                key = obj["Key"]
                if key.lower().endswith(".pdf") and Path(key).name == pdf_name:
                    candidates.append((self.processed_bucket, key))
        if not candidates:
            for page in paginator.paginate(Bucket=self.originals_bucket, Prefix=self.input_prefix):
                for obj in page.get("Contents") or []:
                    key = obj["Key"]
                    if key.lower().endswith(".pdf") and Path(key).name == pdf_name:
                        candidates.append((self.originals_bucket, key))
        if not candidates:
            return None, False
        candidates.sort(key=lambda t: len(t[1]))
        bkt, key = candidates[0]
        fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        path = Path(tmp_path)
        try:
            self._client.download_file(bkt, key, str(path))
            return path, True
        except Exception:
            path.unlink(missing_ok=True)
            raise


def _guess_content_type(filename: str) -> Optional[str]:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith(".md"):
        return "text/markdown"
    if lower.endswith(".txt"):
        return "text/plain"
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    return None


_storage_cache: dict[str, FileStorageService] = {}


def reset_file_storage_singleton() -> None:
    """Clear cached storage backends (tests, or env change without process restart)."""
    global _storage_cache
    _storage_cache = {}


def _storage_backend_from_env() -> str:
    return os.getenv("FILE_STORAGE_BACKEND", "local").strip().lower()


def _s3_user_key_segment(sanitized_user_id: str) -> str:
    """
    Per-user S3 key prefix under the configured base prefix.

    Set S3_USER_ISOLATION=false to use a flat namespace (single-tenant / legacy layouts).
    Default: isolated ``users/{id}/`` under your input/processing prefixes.
    """
    v = os.getenv("S3_USER_ISOLATION", "true").strip().lower()
    if v in ("0", "false", "no", "off"):
        return ""
    return f"users/{sanitized_user_id}/"


def get_file_storage(user_id: str | None = None) -> FileStorageService:
    """
    Return storage for one logical user. S3 mode caches one instance per sanitized user id
    (different prefixes + local sync dirs). Local mode ignores user id for paths.
    """
    global _storage_cache

    from app.core.paths import sanitize_storage_user_id, workspace_paths_for_user

    uid = sanitize_storage_user_id(user_id)
    backend = _storage_backend_from_env()
    cache_key = f"{backend}:{uid}"
    if cache_key in _storage_cache:
        return _storage_cache[cache_key]

    paths = workspace_paths_for_user(uid)

    if backend == "s3":
        originals = os.getenv("S3_ORIGINALS_BUCKET", "").strip()
        processed = os.getenv("S3_PROCESSED_BUCKET", "").strip()
        legacy = os.getenv("S3_BUCKET", "").strip()
        if originals and processed:
            ob, pb = originals, processed
            default_in, default_proc = "", ""
        elif legacy:
            ob = pb = legacy
            default_in, default_proc = "input/", "processing/"
        else:
            raise RuntimeError(
                "FILE_STORAGE_BACKEND=s3 requires S3_BUCKET (single bucket) or both "
                "S3_ORIGINALS_BUCKET and S3_PROCESSED_BUCKET, plus AWS credentials."
            )
        base_in = _normalize_s3_prefix(os.getenv("S3_INPUT_PREFIX"), default_in)
        base_proc = _normalize_s3_prefix(os.getenv("S3_PROCESSING_PREFIX"), default_proc)
        segment = _s3_user_key_segment(uid)
        prefix_in = base_in + segment
        prefix_proc = base_proc + segment
        region = os.getenv("AWS_REGION", "").strip() or None
        inst: FileStorageService = S3FileStorage(
            originals_bucket=ob,
            processed_bucket=pb,
            input_prefix=prefix_in,
            processing_prefix=prefix_proc,
            local_input_dir=paths.input_dir,
            local_output_dir=paths.output_dir,
            region=region,
        )
        _storage_cache[cache_key] = inst
        logger.info(
            "File storage: S3 user=%s originals=%s processed=%s input_prefix=%r proc_prefix=%r local_root=%s",
            uid,
            ob,
            pb,
            prefix_in,
            prefix_proc,
            paths.input_dir.parent,
        )
        return inst

    # Local: single shared instance (ignore user id in cache key)
    local_key = "local:*"
    if local_key in _storage_cache:
        return _storage_cache[local_key]
    inst = LocalFileStorage(paths.input_dir, paths.output_dir)
    _storage_cache[local_key] = inst
    logger.info("File storage: local dirs input=%s", paths.input_dir)
    return inst
