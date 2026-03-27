"""Request/response models — mirrored in docs/API_SCHEMA.md."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


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


class RemoveFromIndexRequest(BaseModel):
    """Drop vectors from Qdrant and sync sparse index (``documents.json`` + BM25) for text."""

    text_source: str | None = Field(
        None,
        description="Exact ``source`` string from indexed text rows (path to chunk, as in /api/files).",
    )
    image_pdf_name: str | None = Field(
        None,
        description="PDF basename (e.g. report.pdf) to remove from the image index only.",
    )
    clear_image_index: bool = Field(
        False,
        description="If true, drop and recreate the image Qdrant collection (all vision pages).",
    )

    @model_validator(mode="after")
    def require_some_action(self):
        ts = (self.text_source or "").strip()
        ip = (self.image_pdf_name or "").strip()
        if not self.clear_image_index and not ts and not ip:
            raise ValueError(
                "Provide text_source and/or image_pdf_name, or set clear_image_index=true."
            )
        return self


class SummaryRequest(BaseModel):
    focus_query: str = Field(
        "",
        description="Optional themes to stress in the summary; does not select chunks (context is full processed .md).",
    )
    depth: str = Field("detailed", description="brief | detailed | comprehensive")
    top_k: int = Field(
        12,
        ge=1,
        le=50,
        description="Ignored for summary: content comes from processed markdown files, not vector top-k.",
    )
    document_id: str | None = Field(
        None,
        description="Document folder name under stage3_document_processed (or stage4); scopes which .md files are read.",
    )
    tone: str = Field(
        "neutral",
        description="neutral | formal | friendly — style guidance for the summary.",
    )
    target_length: str = Field(
        "medium",
        description="short | medium | long — approximate output length.",
    )


class McqRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    num_questions: int = Field(5, ge=1, le=20)
    difficulty: str = Field("intermediate", description="basic | intermediate | advanced")
    document_id: str | None = Field(
        None,
        description="Scope to this document folder under stage3/stage4 processed markdown.",
    )
    question_style: str = Field(
        "exam",
        description="exam | conceptual | mixed — how questions should read.",
    )
    include_explanations: bool = Field(
        True,
        description="If false, omit per-question explanations in the JSON contract.",
    )


class RoadmapRequest(BaseModel):
    student_profile: str = ""
    goals: str = Field(..., min_length=1)
    document_id: str | None = Field(
        None,
        description="Optional scope: only use processed markdown under this document folder.",
    )


class InferenceProbeResponse(BaseModel):
    use_aws_sagemaker_inference: bool
    sagemaker_endpoint_name: Optional[str] = None
    aws_region: Optional[str] = None
    qdrant_mode: str
    text_collection: str
    image_collection: str
