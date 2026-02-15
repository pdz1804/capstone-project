"""
File management routes: upload, list, delete.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, UploadFile, File, HTTPException

from shared import INPUT_DIR, OUTPUT_DIR, get_file_info, FileDeleteRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["files"])


@router.get("/files")
async def get_files() -> Dict[str, List[Dict]]:
    """Get all files in input, processed, and indexed directories."""
    files = {"input": [], "processed": [], "indexed": []}

    # Input files
    if INPUT_DIR.exists():
        for f in INPUT_DIR.rglob("*"):
            if f.is_file() and not f.name.startswith('.'):
                files["input"].append(get_file_info(f))

    # Processed files (from processing stages)
    processing_dir = OUTPUT_DIR / "processing"
    if processing_dir.exists():
        for stage_dir in processing_dir.iterdir():
            if stage_dir.is_dir():
                for f in stage_dir.rglob("*"):
                    if f.is_file() and f.suffix in ['.json', '.md', '.txt']:
                        info = get_file_info(f)
                        info["stage"] = stage_dir.name
                        try:
                            with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
                                content = fp.read(500)
                                info["preview"] = content[:500] + ("..." if len(content) >= 500 else "")
                        except Exception as preview_error:
                            logger.debug(f"Could not read preview for {f.name}: {preview_error}")
                        files["processed"].append(info)

    # Indexed files info
    retrieval_dir = OUTPUT_DIR / "retrieval"
    if retrieval_dir.exists():
        docs_file = retrieval_dir / "documents.json"
        if docs_file.exists():
            try:
                with open(docs_file, 'r', encoding='utf-8', errors='ignore') as f:
                    docs = json.load(f)
                sources = {}
                for doc in docs:
                    source = doc.get('source', 'unknown')
                    sources[source] = sources.get(source, 0) + 1
                for source, count in sources.items():
                    files["indexed"].append({"name": source, "chunks": count, "type": "text"})
            except Exception as e:
                logger.error(f"Failed to read indexed docs: {e}")

    # Image indexed files
    image_dir = OUTPUT_DIR / "image_retrieval"
    if image_dir.exists():
        meta_file = image_dir / "image_index_meta.json"
        if meta_file.exists():
            try:
                with open(meta_file, 'r', encoding='utf-8', errors='ignore') as f:
                    meta = json.load(f)
                colqwen_meta = image_dir / "colqwen" / "colqwen_meta.json"
                if colqwen_meta.exists():
                    with open(colqwen_meta, 'r', encoding='utf-8', errors='ignore') as f:
                        cq_meta = json.load(f)
                    files["indexed"].append({
                        "name": "Image Index (ColQwen)",
                        "pages": cq_meta.get('num_pages', 0),
                        "type": "image"
                    })
            except Exception as e:
                logger.error(f"Failed to read image index meta: {e}")

    return files


@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload files to input directory."""
    uploaded = []
    for file in files:
        try:
            file_path = INPUT_DIR / file.filename
            if file_path.exists():
                base, suffix = file_path.stem, file_path.suffix
                counter = 1
                while file_path.exists():
                    file_path = INPUT_DIR / f"{base}_{counter}{suffix}"
                    counter += 1
            with open(file_path, 'wb') as f:
                content = await file.read()
                f.write(content)
            uploaded.append({"name": file_path.name, "size": len(content)})
            logger.info(f"Uploaded: {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    return {"uploaded": uploaded, "count": len(uploaded)}


@router.delete("/files")
async def delete_file(request: FileDeleteRequest):
    """Delete a file."""
    try:
        file_path = Path(request.path)
        if file_path.exists():
            file_path.unlink()
            return {"deleted": request.path}
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
