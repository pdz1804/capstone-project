from datetime import datetime

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
@router.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
