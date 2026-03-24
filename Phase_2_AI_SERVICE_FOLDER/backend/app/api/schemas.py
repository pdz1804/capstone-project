"""Request/response models — mirrored in docs/API_SCHEMA.md."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language query")
    top_k: int = Field(10, ge=1, le=100)
    retriever_type: str = Field(
        "hybrid",
        description="One of: bm25 | dense | hybrid (dense = Qdrant only; hybrid = BM25 + Qdrant)",
    )
    include_images: bool = True
    images_for_generation: int = Field(5, ge=0, le=20)


class FileDeleteRequest(BaseModel):
    path: str


class SummaryRequest(BaseModel):
    focus_query: str = ""
    depth: str = Field("detailed", description="brief | detailed | comprehensive")
    top_k: int = Field(12, ge=1, le=50)


class McqRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    num_questions: int = Field(5, ge=1, le=20)
    difficulty: str = Field("intermediate", description="basic | intermediate | advanced")


class RoadmapRequest(BaseModel):
    student_profile: str = ""
    goals: str = Field(..., min_length=1)


class InferenceProbeResponse(BaseModel):
    use_aws_sagemaker_inference: bool
    sagemaker_endpoint_name: Optional[str] = None
    aws_region: Optional[str] = None
    qdrant_mode: str
    text_collection: str
    image_collection: str
