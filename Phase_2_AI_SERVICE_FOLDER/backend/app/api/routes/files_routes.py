import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.api.schemas import FileDeleteRequest
from app.core.paths import (
    DOCUMENTS_JSON_PATH,
    INPUT_DIR,
    OUTPUT_DIR,
    ensure_data_dirs,
    merged_runtime_settings,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["files"])


def _file_info(file_path: Path) -> Dict:
    stat = file_path.stat()
    size_bytes = stat.st_size
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
    return {
        "name": file_path.name,
        "path": str(file_path),
        "size": size_str,
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "type": file_path.suffix.lower(),
    }


@router.get("/files")
async def list_files(
    quick: bool = Query(
        False,
        description="If true, only scan input/ (skip processed tree, documents.json, Qdrant). "
        "Use after upload to refresh the input list quickly.",
    ),
) -> Dict[str, List[Dict]]:
    ensure_data_dirs()
    files: Dict[str, List[Dict]] = {"input": [], "processed": [], "indexed": []}

    if INPUT_DIR.exists():
        for f in INPUT_DIR.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                files["input"].append(_file_info(f))

    if quick:
        return files

    processing_dir = OUTPUT_DIR / "processing"
    if processing_dir.exists():
        for stage_dir in processing_dir.iterdir():
            if stage_dir.is_dir():
                for f in stage_dir.rglob("*"):
                    if f.is_file() and f.suffix in [".json", ".md", ".txt"]:
                        info = _file_info(f)
                        info["stage"] = stage_dir.name
                        try:
                            with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                                content = fp.read(500)
                                info["preview"] = content + ("..." if len(content) >= 500 else "")
                        except Exception:
                            pass
                        files["processed"].append(info)

    if DOCUMENTS_JSON_PATH.exists():
        try:
            with open(DOCUMENTS_JSON_PATH, "r", encoding="utf-8") as f:
                docs = json.load(f)
            sources: Dict[str, int] = {}
            for doc in docs:
                s = doc.get("source", "unknown")
                sources[s] = sources.get(s, 0) + 1
            for source, count in sources.items():
                files["indexed"].append({"name": source, "chunks": count, "type": "text"})
        except Exception as e:
            logger.error("documents.json: %s", e)

    cfg = merged_runtime_settings()
    try:
        from app.repositories import ImageIndexRepository, build_qdrant_client

        client = build_qdrant_client(cfg)
        q = cfg.get("qdrant", {}) or {}
        ir = ImageIndexRepository(
            client,
            collection_name=q.get("image_collection", "edu_image_pages"),
            vector_name=q.get("image_vector_name", "colpali_multivec"),
            storage_quantization=q.get("image_storage_quantization", "scalar"),
        )
        n = ir.count_points()
        if n > 0:
            files["indexed"].append(
                {"name": "Image Index (ColQwen → Qdrant)", "pages": n, "type": "image"}
            )
    except Exception:
        pass

    return files


@router.post("/upload")
async def upload(files: List[UploadFile] = File(...)):
    ensure_data_dirs()
    uploaded = []
    file_rows: List[Dict] = []
    for file in files:
        try:
            dest = INPUT_DIR / file.filename
            if dest.exists():
                base, suffix = dest.stem, dest.suffix
                c = 1
                while dest.exists():
                    dest = INPUT_DIR / f"{base}_{c}{suffix}"
                    c += 1
            content = await file.read()
            with open(dest, "wb") as f:
                f.write(content)
            uploaded.append({"name": dest.name, "size": len(content)})
            file_rows.append(_file_info(dest))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
    return {"uploaded": uploaded, "count": len(uploaded), "files": file_rows}


@router.delete("/files")
async def delete_file(body: FileDeleteRequest):
    p = Path(body.path)
    try:
        if p.exists() and p.is_file():
            p.unlink()
            return {"deleted": body.path}
        raise HTTPException(status_code=404, detail="File not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
