"""
File metadata tracking system for monitoring upload status, processing progress, and file integrity.

Each uploaded file gets a companion .json metadata file stored alongside it with:
- Upload timestamp (ISO 8601)
- Processing status (pending, processing, completed, failed)
- File hash (SHA256) for integrity verification
- Processing stages completed
- Error messages and diagnostics
- User and session information
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Literal

logger = logging.getLogger(__name__)

ProcessingStatus = Literal["pending", "processing", "completed", "failed"]
Stage = Literal["upload", "normalize", "extract_media", "docling", "chunking", "indexing"]


class FileMetadata:
    """Metadata container for a single file."""

    def __init__(
        self,
        original_filename: str,
        file_path: str,
        file_size: int,
        user_id: str,
        upload_source: str = "api",
    ):
        self.original_filename = original_filename
        self.file_path = file_path
        self.file_size = file_size
        self.user_id = user_id
        self.upload_source = upload_source
        self.upload_time = datetime.now(timezone.utc).isoformat()
        self.status: ProcessingStatus = "pending"
        self.file_hash = ""
        self.completed_stages: list[Stage] = []
        self.error_message = ""
        self.error_details = ""
        self.processing_start_time = ""
        self.processing_end_time = ""
        self.metadata_version = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "metadata_version": self.metadata_version,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_hash": self.file_hash,
            "upload_time": self.upload_time,
            "upload_source": self.upload_source,
            "user_id": self.user_id,
            "status": self.status,
            "completed_stages": self.completed_stages,
            "processing_start_time": self.processing_start_time or None,
            "processing_end_time": self.processing_end_time or None,
            "error_message": self.error_message or None,
            "error_details": self.error_details or None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileMetadata":
        """Create instance from dictionary."""
        obj = cls(
            original_filename=data.get("original_filename", ""),
            file_path=data.get("file_path", ""),
            file_size=data.get("file_size", 0),
            user_id=data.get("user_id", ""),
            upload_source=data.get("upload_source", "api"),
        )
        obj.upload_time = data.get("upload_time", obj.upload_time)
        obj.status = data.get("status", "pending")
        obj.file_hash = data.get("file_hash", "")
        obj.completed_stages = data.get("completed_stages", [])
        obj.error_message = data.get("error_message", "")
        obj.error_details = data.get("error_details", "")
        obj.processing_start_time = data.get("processing_start_time", "")
        obj.processing_end_time = data.get("processing_end_time", "")
        obj.metadata_version = data.get("metadata_version", "1.0")
        return obj


class FileMetadataService:
    """Service for managing file metadata JSON files."""

    METADATA_SUFFIX = ".metadata.json"

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _get_metadata_path(file_path: str | Path) -> Path:
        """Get the metadata file path for a given file."""
        file_p = Path(file_path)
        metadata_name = f"{file_p.name}{FileMetadataService.METADATA_SUFFIX}"
        return file_p.parent / metadata_name

    @staticmethod
    def compute_file_hash(file_path: str | Path, algorithm: str = "sha256") -> str:
        """Compute file hash for integrity verification."""
        file_p = Path(file_path)
        if not file_p.exists():
            return ""

        hash_obj = hashlib.new(algorithm)
        try:
            with open(file_p, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except OSError as e:
            logger.warning(f"Failed to compute hash for {file_p}: {e}")
            return ""

    def create_metadata(
        self,
        original_filename: str,
        file_path: str | Path,
        file_content: bytes,
        user_id: str,
        upload_source: str = "api",
    ) -> FileMetadata:
        """Create and save metadata for a newly uploaded file."""
        metadata = FileMetadata(
            original_filename=original_filename,
            file_path=str(file_path),
            file_size=len(file_content),
            user_id=user_id,
            upload_source=upload_source,
        )

        metadata.file_hash = hashlib.sha256(file_content).hexdigest()
        metadata.status = "pending"
        metadata.completed_stages = ["upload"]

        self.save_metadata(metadata)
        return metadata

    def save_metadata(self, metadata: FileMetadata) -> None:
        """Persist metadata to JSON file."""
        metadata_path = self._get_metadata_path(metadata.file_path)
        try:
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata.to_dict(), f, indent=2)
            self.logger.debug(f"Saved metadata: {metadata_path}")
        except OSError as e:
            self.logger.error(f"Failed to save metadata {metadata_path}: {e}")

    def load_metadata(self, file_path: str | Path) -> Optional[FileMetadata]:
        """Load metadata from JSON file."""
        metadata_path = self._get_metadata_path(file_path)
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return FileMetadata.from_dict(data)
        except Exception as e:
            self.logger.error(f"Failed to load metadata {metadata_path}: {e}")
            return None

    def update_status(
        self,
        file_path: str | Path,
        status: ProcessingStatus,
        completed_stages: Optional[list[Stage]] = None,
        error_message: str = "",
        error_details: str = "",
    ) -> None:
        """Update the processing status of a file."""
        metadata = self.load_metadata(file_path)
        if not metadata:
            self.logger.warning(f"No metadata found for {file_path}")
            return

        metadata.status = status
        if completed_stages:
            metadata.completed_stages = completed_stages

        if status == "processing" and not metadata.processing_start_time:
            metadata.processing_start_time = datetime.now(timezone.utc).isoformat()

        if status in ("completed", "failed"):
            metadata.processing_end_time = datetime.now(timezone.utc).isoformat()

        if error_message:
            metadata.error_message = error_message
        if error_details:
            metadata.error_details = error_details

        self.save_metadata(metadata)

    def mark_stage_complete(
        self,
        file_path: str | Path,
        stage: Stage,
    ) -> None:
        """Mark a processing stage as complete."""
        metadata = self.load_metadata(file_path)
        if not metadata:
            self.logger.warning(f"No metadata found for {file_path}")
            return

        if stage not in metadata.completed_stages:
            metadata.completed_stages.append(stage)

        metadata.status = "processing"
        self.save_metadata(metadata)

    def mark_complete(self, file_path: str | Path) -> None:
        """Mark file as fully processed."""
        self.update_status(
            file_path,
            status="completed",
            completed_stages=["upload", "normalize", "extract_media", "docling", "chunking", "indexing"],
        )

    def mark_failed(
        self,
        file_path: str | Path,
        error_message: str,
        error_details: str = "",
    ) -> None:
        """Mark file as failed during processing."""
        self.update_status(
            file_path,
            status="failed",
            error_message=error_message,
            error_details=error_details,
        )

    def get_file_status(self, file_path: str | Path) -> Dict[str, Any]:
        """Get current status of a file."""
        metadata = self.load_metadata(file_path)
        if not metadata:
            return {"status": "unknown", "error": "No metadata found"}

        return {
            "status": metadata.status,
            "upload_time": metadata.upload_time,
            "completed_stages": metadata.completed_stages,
            "processing_duration": self._calculate_duration(
                metadata.processing_start_time,
                metadata.processing_end_time,
            ),
            "error_message": metadata.error_message or None,
            "file_hash": metadata.file_hash,
        }

    @staticmethod
    def _calculate_duration(start: str, end: str) -> Optional[float]:
        """Calculate processing duration in seconds."""
        if not start or not end:
            return None

        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
            return (end_dt - start_dt).total_seconds()
        except Exception:
            return None

    def list_file_metadata(
        self,
        directory: str | Path,
        status_filter: Optional[ProcessingStatus] = None,
    ) -> list[FileMetadata]:
        """List all files with metadata in a directory."""
        dir_p = Path(directory)
        if not dir_p.exists():
            return []

        all_metadata = []
        for metadata_file in dir_p.glob(f"*{self.METADATA_SUFFIX}"):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                metadata = FileMetadata.from_dict(data)

                if status_filter is None or metadata.status == status_filter:
                    all_metadata.append(metadata)
            except Exception as e:
                logger.error(f"Failed to load metadata {metadata_file}: {e}")

        return all_metadata

    def cleanup_metadata(self, file_path: str | Path) -> bool:
        """Delete metadata file (when deleting the original file)."""
        metadata_path = self._get_metadata_path(file_path)
        if not metadata_path.exists():
            return False

        try:
            metadata_path.unlink()
            self.logger.debug(f"Deleted metadata: {metadata_path}")
            return True
        except OSError as e:
            self.logger.error(f"Failed to delete metadata {metadata_path}: {e}")
            return False

    def get_processing_stats(self, directory: str | Path) -> Dict[str, Any]:
        """Get aggregate statistics for all files in a directory."""
        all_metadata = self.list_file_metadata(directory)

        stats = {
            "total_files": len(all_metadata),
            "by_status": {
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
            },
            "total_size_bytes": 0,
            "average_processing_time_seconds": None,
            "failed_files": [],
        }

        processing_times = []
        for metadata in all_metadata:
            stats["by_status"][metadata.status] += 1
            stats["total_size_bytes"] += metadata.file_size

            if metadata.status == "failed":
                stats["failed_files"].append({
                    "name": metadata.original_filename,
                    "error": metadata.error_message,
                })

            duration = self._calculate_duration(
                metadata.processing_start_time,
                metadata.processing_end_time,
            )
            if duration is not None:
                processing_times.append(duration)

        if processing_times:
            stats["average_processing_time_seconds"] = sum(processing_times) / len(processing_times)

        return stats
