from __future__ import annotations

from typing import Any, Dict, List, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import storage_user_id
from app.identity.routes import get_current_user
from app.identity.schemas import UserResponse
from app.services.retrieval_eval_service import DEFAULT_K_VALUES, RetrievalEvalService

router = APIRouter(prefix="/api/retrieval-eval", tags=["retrieval-eval"])


def get_current_eval_user(user: UserResponse = Depends(get_current_user)) -> UserResponse:
    role = (user.role or "").lower()
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role is required")
    if not bool(user.isActive):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    return user


class RetrievalEvalRunRequest(BaseModel):
    top_k: int = Field(10, ge=1, le=50)
    k_values: List[int] = Field(default_factory=lambda: list(DEFAULT_K_VALUES))
    retriever_type: str = Field("hybrid", description="Text retriever: bm25 | dense | hybrid")
    questions_per_category: int = Field(5, ge=1, le=10)
    selected_document_ids: List[str] = Field(default_factory=list)
    async_mode: bool = False


class HumanLabel(BaseModel):
    evidence_id: str
    relevance: int = Field(..., ge=0, le=2)
    rationale: str = ""


class HumanLabelsRequest(BaseModel):
    query_id: str
    modality: Literal["text", "image"]
    labels: List[HumanLabel] = Field(default_factory=list)
    ranked_evidence_ids: List[str] = Field(default_factory=list)


class HumanAnswerJudgmentRequest(BaseModel):
    query_id: str
    correctness: Literal["correct", "partially_correct", "incorrect"]
    faithfulness: Literal["faithful", "partially_faithful", "hallucinated"]
    answer_support: Literal["fully_supported", "partially_supported", "not_supported"]
    rationale: str = ""


def _run_eval_background(
    *,
    run_id: str,
    user_id: str,
    top_k: int,
    k_values: List[int],
    retriever_type: str,
    questions_per_category: int,
    selected_document_ids: List[str],
) -> None:
    service = RetrievalEvalService(user_id=user_id)
    try:
        service.create_run(
            run_id=run_id,
            top_k=top_k,
            k_values=k_values,
            retriever_type=retriever_type,
            questions_per_category=questions_per_category,
            selected_document_ids=selected_document_ids,
        )
    except Exception as exc:
        service.mark_run_failed(run_id, exc)


@router.post("/runs")
def create_retrieval_eval_run(
    req: RetrievalEvalRunRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(storage_user_id),
    _user: UserResponse = Depends(get_current_eval_user),
) -> Dict[str, Any]:
    try:
        if req.async_mode:
            service = RetrievalEvalService(user_id=user_id)
            run_id = service.new_run_id()
            pending = service.create_pending_run(
                run_id=run_id,
                top_k=req.top_k,
                k_values=req.k_values,
                retriever_type=req.retriever_type,
                questions_per_category=req.questions_per_category,
                selected_document_ids=req.selected_document_ids,
            )
            background_tasks.add_task(
                _run_eval_background,
                run_id=run_id,
                user_id=user_id,
                top_k=req.top_k,
                k_values=req.k_values,
                retriever_type=req.retriever_type,
                questions_per_category=req.questions_per_category,
                selected_document_ids=req.selected_document_ids,
            )
            return pending
        return RetrievalEvalService(user_id=user_id).create_run(
            top_k=req.top_k,
            k_values=req.k_values,
            retriever_type=req.retriever_type,
            questions_per_category=req.questions_per_category,
            selected_document_ids=req.selected_document_ids,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/runs/{run_id}")
def get_retrieval_eval_run(
    run_id: str,
    user_id: str = Depends(storage_user_id),
    _user: UserResponse = Depends(get_current_eval_user),
) -> Dict[str, Any]:
    try:
        return RetrievalEvalService(user_id=user_id).load_run(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Retrieval eval run not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/runs/{run_id}/labels")
def save_retrieval_eval_human_labels(
    run_id: str,
    req: HumanLabelsRequest,
    user_id: str = Depends(storage_user_id),
    _user: UserResponse = Depends(get_current_eval_user),
) -> Dict[str, Any]:
    try:
        return RetrievalEvalService(user_id=user_id).save_human_labels(
            run_id,
            query_id=req.query_id,
            modality=req.modality,
            labels=[item.model_dump() for item in req.labels],
            ranked_evidence_ids=req.ranked_evidence_ids,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Retrieval eval run not found") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="query_id not found in run") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/runs/{run_id}/answer-labels")
def save_retrieval_eval_human_answer_judgment(
    run_id: str,
    req: HumanAnswerJudgmentRequest,
    user_id: str = Depends(storage_user_id),
    _user: UserResponse = Depends(get_current_eval_user),
) -> Dict[str, Any]:
    try:
        return RetrievalEvalService(user_id=user_id).save_human_answer_judgment(
            run_id,
            query_id=req.query_id,
            correctness=req.correctness,
            faithfulness=req.faithfulness,
            answer_support=req.answer_support,
            rationale=req.rationale,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Retrieval eval run not found") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="query_id not found in run") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/runs/{run_id}/recompute")
def recompute_retrieval_eval_metrics(
    run_id: str,
    user_id: str = Depends(storage_user_id),
    _user: UserResponse = Depends(get_current_eval_user),
) -> Dict[str, Any]:
    try:
        return RetrievalEvalService(user_id=user_id).recompute(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Retrieval eval run not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
