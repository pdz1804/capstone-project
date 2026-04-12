"""Request/response models — mirrored in docs/API_SCHEMA.md."""

from __future__ import annotations

from typing import Any, Literal, Optional

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
    mode: Literal["retrieval_only", "retrieval_generation"] = Field(
        "retrieval_generation",
        description="retrieval_only = fetch chunks/images only, retrieval_generation = retrieval + LLM answer.",
    )
    search_scope: Literal["text", "image", "both"] = Field(
        "both",
        description="Which index to search: text, image, or both.",
    )
    generation_model: str | None = Field(
        None,
        description="Optional override generation model id (useful for AWS Bedrock model comparisons).",
    )
    skip_reranker: bool = Field(
        True,
        description="If true, bypass cross-encoder reranking even when enabled in config.",
    )


class FileDeleteRequest(BaseModel):
    path: str


class ProcessRequest(BaseModel):
    selected_paths: list[str] = Field(
        default_factory=list,
        description="Optional list of input file paths/URIs to process. Empty means process all input files.",
    )
    mode: Literal["standard", "fast"] = Field(
        "standard",
        description="Processing mode. fast = lower-cost/faster Docling+ASR settings.",
    )


class IndexRequest(BaseModel):
    selected_paths: list[str] = Field(
        default_factory=list,
        description="Optional list of input file paths/URIs to index. Empty means index all files.",
    )
    selected_names: list[str] = Field(
        default_factory=list,
        description="Optional list of original file names to index. Used as fallback matching for processed artifacts.",
    )
    mode: Literal["standard", "fast"] = Field(
        "standard",
        description="Indexing mode. fast = text-only indexing (skip image index).",
    )


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
    clear_text_index: bool = Field(
        False,
        description="If true, drop and recreate the text Qdrant collection and clear BM25/documents sidecars.",
    )

    @model_validator(mode="after")
    def require_some_action(self):
        ts = (self.text_source or "").strip()
        ip = (self.image_pdf_name or "").strip()
        if not self.clear_image_index and not self.clear_text_index and not ts and not ip:
            raise ValueError(
                "Provide text_source and/or image_pdf_name, or set clear_image_index=true / clear_text_index=true."
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
    use_aws_sagemaker_docling: bool = False
    sagemaker_docling_endpoint_name: Optional[str] = None
    use_aws_sagemaker_whisper: bool = False
    sagemaker_whisper_endpoint_name: Optional[str] = None
    aws_region: Optional[str] = None
    qdrant_mode: str
    text_collection: str
    image_collection: str
    generation_provider: Optional[str] = None


class ChatStreamRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language user message.")
    top_k: int = Field(8, ge=1, le=30, description="Default retrieval breadth for inline tools.")
    persona: str | None = Field(
        None,
        description="Optional preferred assistant tone/persona configured by the user profile.",
    )
    education_description: str | None = Field(
        None,
        description="Optional user education background/context to personalize explanations.",
    )
    session_id: str = Field(
        "",
        description=(
            "Chat session ID for AgentCore memory continuity. "
            "Auto-generated server-side if empty. "
            "Regenerate on the client to start a fresh memory session (e.g. after Clear Chat)."
        ),
    )


class ChatSessionCreateRequest(BaseModel):
    session_id: str | None = Field(
        None,
        description="Optional client-provided session id. If omitted, server generates one.",
    )
    title: str | None = Field(
        None,
        max_length=120,
        description="Optional custom title for this chat session.",
    )
    pinned: bool = Field(False, description="Whether to pin this chat session in the history list.")


class ChatSessionUpdateRequest(BaseModel):
    title: str | None = Field(None, max_length=120)
    pinned: bool | None = None

    @model_validator(mode="after")
    def require_any_change(self):
        if self.title is None and self.pinned is None:
            raise ValueError("Provide title and/or pinned when updating a chat session.")
        return self


class ChatSessionItem(BaseModel):
    session_id: str
    user_id: str
    title: str
    pinned: bool
    message_count: int
    created_at: str
    updated_at: str
    last_message_at: str | None = None
    last_message_preview: str | None = None
    last_message_role: Literal["user", "assistant", "system"] | None = None


class ChatSessionsListResponse(BaseModel):
    items: list[ChatSessionItem]
    next_cursor: str | None = None


class ChatMessageItem(BaseModel):
    session_id: str
    message_id: str
    user_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: str
    traces: list[dict[str, Any]] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ChatMessagesListResponse(BaseModel):
    items: list[ChatMessageItem]
    next_cursor: str | None = None


class QuizResultCreateRequest(BaseModel):
    score: int = Field(..., ge=0)
    total: int = Field(..., ge=1)
    file_id: int | None = None
    document_id: str | None = None
    quiz_topic: str | None = None


class QuizResultItem(BaseModel):
    attempt_id: str
    user_id: str
    score: int
    total: int
    file_id: int | None = None
    document_id: str | None = None
    quiz_topic: str | None = None
    created_at: str


class QuizResultsListResponse(BaseModel):
    items: list[QuizResultItem]


class FeedbackCreateRequest(BaseModel):
    vote: Literal["like", "dislike", "general"]
    query: str | None = None
    response: str | None = None
    session_id: str | None = None
    message_id: str | None = None
    reason_code: str | None = None
    reason_text: str | None = None
    scope: str | None = None
    feedback_text: str | None = None


class FeedbackItem(BaseModel):
    user_id: str
    feedback_id: str
    session_id: str | None = None
    message_id: str | None = None
    vote: Literal["like", "dislike", "general"]
    reason_code: str | None = None
    reason_text: str | None = None
    scope: str | None = None
    feedback_text: str | None = None
    query: str
    response: str
    is_active: bool = True
    category: str = "Uncategorized"
    sub_category: str = ""
    suggested_action: str = ""
    analysis_summary: str = ""
    classifier_model: str = ""
    classification_status: str = "pending"
    classification_error: str | None = None
    created_at: str
    updated_at: str
    version: int = 1


class FeedbackListResponse(BaseModel):
    items: list[FeedbackItem]
    next_cursor: str | None = None
