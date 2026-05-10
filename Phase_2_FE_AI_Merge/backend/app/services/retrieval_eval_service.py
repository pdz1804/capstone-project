"""Retrieval evaluation with LLM and human relevance judgments."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence, TypeVar

from app.core.paths import BACKEND_ROOT, merged_runtime_settings, sanitize_storage_user_id, workspace_paths_for_user
from app.services.knowledge_service import KnowledgeService
from app.services.processed_documents_service import build_processed_documents_snapshot
from app.services.processed_markdown_service import gather_processed_markdown_context
from app.services.search_orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)

QUESTION_CATEGORIES = ("simple", "complex_intent", "reasoning", "cross_file_reasoning")
DEFAULT_K_VALUES = (1, 3, 5, 7, 10)
MAX_CONTEXT_CHARS_PER_DOC = 80_000
MAX_SUMMARY_CONTEXT_CHARS = 45_000
LLM_EVAL_CONCURRENCY = 10
LOG_LLM_PROMPTS = str(os.getenv("RETRIEVAL_EVAL_LOG_LLM_PROMPTS", "false")).strip().lower() in {"1", "true", "yes", "on"}
try:
    LOG_LLM_PROMPT_CHARS = max(200, int(os.getenv("RETRIEVAL_EVAL_LOG_LLM_PROMPT_CHARS", "1200") or "1200"))
except ValueError:
    LOG_LLM_PROMPT_CHARS = 1200

_T = TypeVar("_T")

_JSON_BLOCK_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL | re.IGNORECASE)
_IMAGE_ARTIFACT_RE = re.compile(
    r"\[START_IMAGE(?:_PATH)?\]\s*(.*?)\s*\[END_IMAGE(?:_PATH)?\]|!\[[^\]]*\]\(([^)]+)\)|<img[^>]+src=[\"']([^\"']+)[\"']",
    re.IGNORECASE | re.DOTALL,
)
_REFUSAL_RE = re.compile(
    r"\b(sorry|cannot|can't|unable|violates?\s+our\s+polic|policy|guardrail|i\s+can'?t)\b",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_or_empty(raw: str) -> Dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"items": parsed}
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
        return parsed if isinstance(parsed, dict) else {"items": parsed}
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clip(text: Any, limit: int) -> str:
    value = str(text or "").strip()
    # if len(value) <= limit:
    #     return value
    # return value[:limit].rstrip() + "\n\n[TRUNCATED]"
    return value


def _clip_for_log(text: Any, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + " [TRUNCATED]"


def _looks_like_refusal(raw: Any) -> bool:
    text = str(raw or "").strip()
    return bool(text and _REFUSAL_RE.search(text))


def _clean_context_lines(text: Any, limit: int = 8) -> List[str]:
    lines: List[str] = []
    seen: set[str] = set()
    for raw_line in str(text or "").splitlines():
        line = re.sub(r"<!--.*?-->", " ", raw_line).strip()
        line = re.sub(r"^#{1,6}\s*", "", line).strip()
        line = re.sub(r"\s+", " ", line)
        if (
            len(line) < 24
            or line.startswith(("File:", "Path:", "---", "|"))
            or line.lower().startswith(("table_", "image_"))
        ):
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(line[:360])
        if len(lines) >= limit:
            break
    return lines


def _fallback_questions_for_doc(doc: Dict[str, Any], questions_per_category: int) -> List[Dict[str, Any]]:
    lines = _clean_context_lines(doc.get("context"), limit=max(8, questions_per_category * len(QUESTION_CATEGORIES) + 2))
    if not lines:
        return []

    display = str(doc.get("display_name") or doc.get("doc_id") or "the selected document")
    templates = {
        "simple": "What key point is stated in {display} about this excerpt: {snippet}",
        "complex_intent": "What does {display} explain about this topic, and which detail supports it: {snippet}",
        "reasoning": "Based on {display}, what conclusion can be drawn from this excerpt: {snippet}",
        "cross_file_reasoning": "Within the active evaluation set, how is this part of {display} relevant to the broader document context: {snippet}",
    }
    out: List[Dict[str, Any]] = []
    for category in QUESTION_CATEGORIES:
        for idx in range(questions_per_category):
            snippet = lines[(len(out) + idx) % len(lines)]
            out.append(
                {
                    "query_id": f"{doc['doc_id']}:{category}:{idx + 1}",
                    "doc_id": doc["doc_id"],
                    "category": category,
                    "question": templates[category].format(display=display, snippet=snippet),
                    "reference_answer": snippet,
                    "expected_evidence_hint": snippet,
                    "generation_raw": "fallback: generated from processed markdown because the judge model did not return valid question JSON",
                    "generation_source": "fallback",
                }
            )
    return out


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _stdev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    m = _mean(values)
    return float(math.sqrt(sum((x - m) ** 2 for x in values) / len(values)))


def _norm_doc_key(value: Any) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return ""
    name = Path(raw).name
    stem = Path(name).stem
    key = re.sub(r"[^a-z0-9]+", " ", stem or name, flags=re.IGNORECASE).strip().lower()
    return re.sub(r"\s+", " ", key)


def _doc_key_candidates(value: Any) -> set[str]:
    raw = str(value or "").strip().replace("\\", "/")
    out = {_norm_doc_key(raw)}
    name = Path(raw).name
    stem = Path(name).stem
    out.add(_norm_doc_key(name))
    out.add(_norm_doc_key(stem))
    out.add(_norm_doc_key(re.sub(r"[_\s-]+\d+$", "", stem)))
    return {x for x in out if x}


def _without_normalizer_hash(key: str) -> str:
    """
    Stage 1 truncates long filenames and appends an 8-char md5 suffix.
    After ``_norm_doc_key`` that suffix is a trailing token, e.g.
    ``real time object detection in disaster zo ca6faaea``.
    """
    tokens = str(key or "").strip().split()
    if len(tokens) >= 2 and re.fullmatch(r"[0-9a-f]{8}", tokens[-1] or ""):
        return " ".join(tokens[:-1]).strip()
    return str(key or "").strip()


def _doc_keys_match(left: set[str], right: set[str]) -> bool:
    if left & right:
        return True
    left_clean = {_without_normalizer_hash(x) for x in left if x}
    right_clean = {_without_normalizer_hash(x) for x in right if x}
    if left_clean & right_clean:
        return True
    # Long original filenames may only share the un-hashed truncated prefix
    # with the processed folder id. Require a substantial prefix to avoid
    # matching unrelated short titles.
    for a in left_clean:
        if len(a) < 24:
            continue
        for b in right_clean:
            if len(b) < 24:
                continue
            shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
            if longer.startswith(shorter):
                return True
    return False


def _knowledge_doc_keys(row: Dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for field in ("title", "source_path", "file_path", "original_filename", "document_id", "doc_id"):
        keys.update(_doc_key_candidates(row.get(field)))
    return keys


def _generation_config(cfg: Dict[str, Any]):
    from src.generation.generator import GenerationConfig, RAGGenerator

    gyaml = cfg.get("generation", {}) or {}
    eval_model = str(
        os.getenv("RETRIEVAL_EVAL_GENERATION_MODEL")
        or gyaml.get("model")
        or "gpt-4o-mini"
    ).strip()
    eval_provider = str(
        os.getenv("RETRIEVAL_EVAL_GENERATION_PROVIDER")
        or gyaml.get("provider")
        or "openai"
    ).strip()
    disable_guardrail = str(os.getenv("RETRIEVAL_EVAL_DISABLE_GUARDRAIL", "false")).lower() in {"true", "1", "yes"}
    gc = GenerationConfig(
        provider=eval_provider,
        model_name=eval_model or str(gyaml.get("model", "gpt-4o-mini")),
        api_key=gyaml.get("api_key"),
        base_url=gyaml.get("base_url"),
        bedrock_region=(gyaml.get("bedrock_region") or None),
        temperature=0.0,
        max_tokens=int(gyaml.get("max_tokens", 3000)),
        enable_citations=False,
        base_dir=str(BACKEND_ROOT),
        enable_guardrails=not disable_guardrail,
    )
    return gc, RAGGenerator(gc)


def _evidence_id(modality: str, row: Dict[str, Any]) -> str:
    if modality == "text":
        return f"text:{str(row.get('id') or '').strip()}"
    source = str(row.get("source") or row.get("source_path") or row.get("id") or "").strip()
    page = _safe_int(row.get("page"), 0)
    return f"image:{source}#page={page}"


def _normalize_evidence(modality: str, rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, raw in enumerate(rows, start=1):
        row = dict(raw or {})
        meta = dict(row.get("metadata") or {})
        text = str(row.get("full_text") or row.get("text") or "")
        image_artifact_paths: List[str] = []
        if modality == "text" and text:
            seen_paths = set()
            for match in _IMAGE_ARTIFACT_RE.finditer(text):
                raw_path = next((g for g in match.groups() if g), "")
                image_path = str(raw_path or "").split("|", 1)[0].strip()
                if image_path and image_path not in seen_paths:
                    seen_paths.add(image_path)
                    image_artifact_paths.append(image_path)
        if modality == "image":
            text = text or f"Image/page evidence from {row.get('source') or row.get('source_path')}, page {row.get('page') or '-'}"
        out.append(
            {
                "evidence_id": _evidence_id(modality, row),
                "modality": modality,
                "rank": _safe_int(row.get("rank"), idx) or idx,
                "score": _safe_float(row.get("score"), 0.0),
                "retrieval_type": str(row.get("retrieval_type") or ""),
                "source": str(row.get("source") or ""),
                "source_path": str(row.get("source_path") or meta.get("source_path") or meta.get("preview_source_path") or meta.get("original_file") or ""),
                "storage_uri": str(row.get("storage_uri") or meta.get("storage_uri") or meta.get("original_storage_uri") or ""),
                "page": row.get("page") or meta.get("page") or meta.get("page_number"),
                "image_artifact_paths": image_artifact_paths,
                "text": _clip(text, 6000),
                "text_preview": _clip(text.replace("\n", " "), 700),
                "metadata": meta,
            }
        )
    return out


def _compact_evidence_for_prompt(evidence: Sequence[Dict[str, Any]], max_items: int = 15) -> str:
    lines: List[str] = []
    for item in evidence[:max_items]:
        loc = item.get("source") or item.get("source_path") or ""
        page = item.get("page")
        page_text = f", page={page}" if page not in (None, "", 0) else ""
        # Use full text instead of preview for better LLM context, but limit to reasonable length
        text_content = item.get("text") or item.get("text_preview") or ""
        lines.append(
            f"- evidence_id: {item['evidence_id']}\n"
            f"  content: {text_content}"
        )
    return "\n".join(lines)


def _labels_to_relevance(labels: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in labels or []:
        eid = str(item.get("evidence_id") or "").strip()
        if not eid:
            continue
        rel = max(0, min(2, _safe_int(item.get("relevance"), 0)))
        out[eid] = rel
    return out


def _rank_map_from_judgment(judgment: Dict[str, Any]) -> Dict[str, int]:
    raw = judgment.get("ranked_evidence_ids") or []
    out: Dict[str, int] = {}
    for idx, eid in enumerate(raw, start=1):
        key = str(eid or "").strip()
        if key and key not in out:
            out[key] = idx
    return out


def _dcg(rels: Sequence[int]) -> float:
    return float(sum((2**rel - 1) / math.log2(idx + 2) for idx, rel in enumerate(rels)))


def _metrics_for_one(evidence: Sequence[Dict[str, Any]], labels: Sequence[Dict[str, Any]], k_values: Sequence[int]) -> Dict[str, float]:
    relevance = _labels_to_relevance(labels)
    relevant_total = sum(1 for value in relevance.values() if value > 0)
    ranked_ids = [str(item.get("evidence_id") or "") for item in evidence]
    out: Dict[str, float] = {}
    ideal = sorted((value for value in relevance.values() if value > 0), reverse=True)
    for k in k_values:
        top_ids = ranked_ids[:k]
        hits = sum(1 for eid in top_ids if relevance.get(eid, 0) > 0)
        out[f"recall@{k}"] = float(hits / relevant_total) if relevant_total else 0.0
        dcg = _dcg([relevance.get(eid, 0) for eid in top_ids])
        idcg = _dcg(ideal[:k])
        out[f"ndcg@{k}"] = float(dcg / idcg) if idcg > 0 else 0.0
    return out


def _aggregate_metric_rows(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    values: Dict[str, List[float]] = {}
    for row in rows:
        for key, value in (row.get("metrics") or {}).items():
            values.setdefault(key, []).append(float(value))
    return {
        key: {
            "mean": _mean(vals),
            "std": _stdev(vals),
            "min": min(vals) if vals else 0.0,
            "max": max(vals) if vals else 0.0,
            "count": len(vals),
        }
        for key, vals in sorted(values.items())
    }


def _grouped_metric_summary(rows: Sequence[Dict[str, Any]], group_key: str) -> Dict[str, Any]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(group_key) or ""), []).append(row)
    return {key: _aggregate_metric_rows(items) for key, items in sorted(grouped.items())}


def _sum_ms(items: Sequence[Dict[str, Any]], key: str) -> int:
    total = 0
    for item in items:
        total += _safe_int(item.get(key), 0)
    return total


def _normalize_selected_doc_ids(values: Sequence[Any] | None) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for value in values or []:
        doc_id = str(value or "").strip()
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        out.append(doc_id)
    return out


class RetrievalEvalService:
    def __init__(self, yaml_config: Dict[str, Any] | None = None, user_id: str | None = None):
        self.cfg = merged_runtime_settings(yaml_config)
        self.user_id = sanitize_storage_user_id(user_id)
        self.paths = workspace_paths_for_user(self.user_id)
        self.root = self.paths.output_dir / "evaluation" / "retrieval_eval"
        self._llm_semaphore = threading.BoundedSemaphore(LLM_EVAL_CONCURRENCY)
        self._progress_lock = threading.Lock()
        self._progress_counts: Dict[str, int] = {}
        self._current_run_id = ""

    def _parallel_map(self, funcs: Sequence[Callable[[], _T]]) -> List[_T]:
        if not funcs:
            return []
        if len(funcs) == 1:
            return [funcs[0]()]
        with ThreadPoolExecutor(max_workers=min(LLM_EVAL_CONCURRENCY, len(funcs))) as executor:
            futures = [executor.submit(func) for func in funcs]
            return [future.result() for future in futures]

    def _next_progress(self, key: str) -> int:
        with self._progress_lock:
            value = self._progress_counts.get(key, 0) + 1
            self._progress_counts[key] = value
            return value

    def _log_llm_prompt(
        self,
        *,
        phase: str,
        prompt: str,
        run_id: str = "",
        doc_id: str = "",
        query_id: str = "",
        category: str = "",
        modality: str = "",
    ) -> None:
        logger.info(
            "retrieval eval LLM prompt phase=%s run_id=%s user_id=%s doc_id=%s query_id=%s category=%s modality=%s chars=%d",
            phase,
            run_id or self._current_run_id,
            self.user_id,
            doc_id,
            query_id,
            category,
            modality,
            len(prompt),
        )
        if LOG_LLM_PROMPTS:
            logger.info(
                "retrieval eval LLM prompt body phase=%s run_id=%s preview=%r",
                phase,
                run_id or self._current_run_id,
                _clip_for_log(prompt, LOG_LLM_PROMPT_CHARS),
            )

    def _call_llm_bounded(
        self,
        gen: Any,
        prompt: str,
        image_paths: List[str] | None = None,
        *,
        phase: str = "llm",
        run_id: str = "",
        doc_id: str = "",
        query_id: str = "",
        category: str = "",
        modality: str = "",
    ) -> str:
        self._log_llm_prompt(
            phase=phase,
            prompt=prompt,
            run_id=run_id,
            doc_id=doc_id,
            query_id=query_id,
            category=category,
            modality=modality,
        )
        with self._llm_semaphore:
            return gen._call_llm(prompt, image_paths=image_paths)

    def _run_path(self, run_id: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", str(run_id or "").strip())
        if not safe:
            raise ValueError("run_id is required")
        return self.root / safe / "report.json"

    def load_run(self, run_id: str) -> Dict[str, Any]:
        path = self._run_path(run_id)
        if not path.exists():
            raise FileNotFoundError(run_id)
        return _read_json(path)

    def save_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        path = self._run_path(str(run.get("run_id") or ""))
        run["artifact_path"] = str(path)
        _write_json(path, run)
        return run

    def new_run_id(self) -> str:
        return f"retrieval_eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def create_pending_run(
        self,
        *,
        run_id: str,
        top_k: int,
        k_values: Sequence[int] | None,
        retriever_type: str,
        search_scope: str,
        questions_per_category: int,
        selected_document_ids: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        k_values = tuple(sorted({int(k) for k in (k_values or DEFAULT_K_VALUES) if int(k) > 0})) or DEFAULT_K_VALUES
        top_k = max(int(top_k or 10), max(k_values))
        search_scope = search_scope if search_scope in {"text", "image", "both"} else "both"
        selected_doc_ids = _normalize_selected_doc_ids(selected_document_ids)
        run = {
            "run_id": run_id,
            "user_id": self.user_id,
            "status": "running",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "config": {
                "top_k": top_k,
                "k_values": list(k_values),
                "retriever_type": retriever_type,
                "search_scope": search_scope,
                "questions_per_category": questions_per_category,
                "selected_document_ids": selected_doc_ids,
                "async_mode": True,
            },
            "active_files": [],
            "document_summaries": [],
            "questions": [],
            "results": [],
            "metrics": {},
        }
        return self.save_run(run)

    def mark_run_failed(self, run_id: str, error: Exception | str) -> Dict[str, Any]:
        try:
            run = self.load_run(run_id)
        except FileNotFoundError:
            run = {"run_id": run_id, "user_id": self.user_id, "created_at": _utc_now()}
        run["status"] = "failed"
        run["updated_at"] = _utc_now()
        run["error"] = str(error)
        return self.save_run(run)

    def _active_knowledge_rows(self) -> List[Dict[str, Any]] | None:
        """
        Return the Knowledge Explorer active rows for this user.

        None means no knowledge repository/storage metadata source is available, so callers may
        fall back to the processed tree. An empty list means the source is available but this user
        currently has no active knowledge rows.
        """
        knowledge = KnowledgeService.from_env_optional()
        try:
            rows = knowledge.list(user_id=self.user_id, is_active=True, limit=None)
        except Exception as exc:
            if getattr(knowledge, "repo", None) is not None:
                logger.warning("failed to list active knowledge rows for retrieval eval user=%s: %s", self.user_id, exc)
                return []
            return None
        if getattr(knowledge, "repo", None) is None and not rows:
            return None
        return [
            dict(row)
            for row in rows
            if bool(row.get("is_active", True))
            and str(row.get("knowledge_type") or "document").lower() in {"document", "other", ""}
        ]

    def _active_documents(
        self,
        max_documents: int | None = None,
        skip_knowledge_lookup: bool = False,
        selected_document_ids: Sequence[str] | None = None,
    ) -> List[Dict[str, Any]]:
        """Get processed documents available for retrieval evaluation."""
        snapshot = build_processed_documents_snapshot(self.user_id, include_preview=False)
        selected_doc_ids = set(_normalize_selected_doc_ids(selected_document_ids))
        selected_doc_keys: set[str] = set()
        for selected in selected_doc_ids:
            selected_doc_keys.update(_doc_key_candidates(selected))
        active_rows = None if skip_knowledge_lookup else self._active_knowledge_rows()
        active_keys: set[str] = set()
        active_by_key: Dict[str, Dict[str, Any]] = {}
        if active_rows is not None:
            for row in active_rows:
                for key in _knowledge_doc_keys(row):
                    active_keys.add(key)
                    active_by_key.setdefault(key, row)

        docs: List[Dict[str, Any]] = []
        for doc in snapshot.get("documents") or []:
            doc_id = str(doc.get("id") or "").strip()
            if not doc_id or doc_id.startswith("__"):
                continue
            doc_keys = set()
            doc_keys.update(_doc_key_candidates(doc_id))
            doc_keys.update(_doc_key_candidates(doc.get("display_name")))
            if selected_doc_ids and doc_id not in selected_doc_ids and not _doc_keys_match(doc_keys, selected_doc_keys):
                continue
            knowledge_row: Dict[str, Any] | None = None
            if active_rows is not None:
                matches = doc_keys & active_keys
                if matches:
                    knowledge_row = active_by_key.get(sorted(matches)[0])
                else:
                    knowledge_row = next(
                        (row for row in active_rows if _doc_keys_match(doc_keys, _knowledge_doc_keys(row))),
                        None,
                    )
                if knowledge_row is None:
                    continue
            ctx = gather_processed_markdown_context(self.user_id, doc_id, MAX_CONTEXT_CHARS_PER_DOC)
            if not ctx.strip():
                continue
            docs.append(
                {
                    "doc_id": doc_id,
                    "display_name": str(doc.get("display_name") or doc_id),
                    "total_files": int(doc.get("total_files") or 0),
                    "knowledge": {
                        "knowledge_id": str((knowledge_row or {}).get("knowledge_id") or ""),
                        "title": str((knowledge_row or {}).get("title") or ""),
                        "source_path": str((knowledge_row or {}).get("source_path") or ""),
                    } if knowledge_row else {},
                    "context": ctx,
                }
            )
            if max_documents and len(docs) >= max_documents:
                break
        return docs

    def _summarize_doc(self, gen: Any, doc: Dict[str, Any]) -> Dict[str, Any]:
        idx = self._next_progress("summaries")
        logger.info(
            "retrieval eval summarizing document %d doc_id=%s display_name=%s context_chars=%d",
            idx,
            doc.get("doc_id"),
            doc.get("display_name"),
            len(str(doc.get("context") or "")),
        )
        prompt = f"""
Summarize this processed document markdown for retrieval-evaluation question generation.

Return JSON only:
{{"summary": "short but specific summary", "key_topics": ["..."], "important_entities": ["..."]}}

Document id: {doc['doc_id']}
Markdown:
{_clip(doc.get('context'), MAX_SUMMARY_CONTEXT_CHARS)}
""".strip()
        raw = ""
        try:
            raw = self._call_llm_bounded(
                gen,
                prompt,
                phase="summarize_document",
                doc_id=str(doc.get("doc_id") or ""),
            )
            payload = _json_or_empty(raw)
            logger.info(
                "retrieval eval summarized document doc_id=%s raw_chars=%d summary_chars=%d topics=%d",
                doc["doc_id"],
                len(raw),
                len(str(payload.get("summary") or "")),
                len(payload.get("key_topics") or []),
            )
            return {
                "doc_id": doc["doc_id"],
                "summary": str(payload.get("summary") or "").strip() or _clip(raw, 1200),
                "key_topics": [str(x) for x in (payload.get("key_topics") or [])][:12],
                "important_entities": [str(x) for x in (payload.get("important_entities") or [])][:12],
                "raw": raw,
            }
        except Exception as exc:
            logger.warning("summary generation failed for %s: %s", doc["doc_id"], exc)
            return {
                "doc_id": doc["doc_id"],
                "summary": _clip(doc.get("context"), 1200),
                "key_topics": [],
                "important_entities": [],
                "raw": raw,
                "error": str(exc),
            }

    def _generate_questions(
        self,
        gen: Any,
        doc: Dict[str, Any],
        all_summaries: Sequence[Dict[str, Any]],
        questions_per_category: int,
        missing_counts: Dict[str, int] | None = None,
    ) -> List[Dict[str, Any]]:
        summary_text = "\n".join(
            f"- {s.get('doc_id')}: {s.get('summary')}" for s in all_summaries if str(s.get("summary") or "").strip()
        )
        category_guidance = {
            "simple": "direct factual lookup from the target document.",
            "complex_intent": "multi-part or intent-rich question answerable from the target document.",
            "reasoning": "requires logical, mathematical, or conceptual inference from the target document.",
            "cross_file_reasoning": "relates the target document to one or more other active documents using the active-document summaries.",
        }
        out: List[Dict[str, Any]] = []
        counts = {cat: 0 for cat in QUESTION_CATEGORIES}

        def generate_category(category: str) -> tuple[str, List[Dict[str, Any]], str]:
            needed = missing_counts.get(category, questions_per_category) if missing_counts else questions_per_category
            if needed <= 0:
                return category, [], ""
            logger.info(
                "retrieval eval generating questions doc_id=%s category=%s needed=%d context_chars=%d",
                doc["doc_id"],
                category,
                needed,
                len(str(doc.get("context") or "")),
            )
            prompt = f"""
Generate retrieval-evaluation questions for the target document.

Return JSON only:
{{
  "items": [
    {{
      "category": "{category}",
      "question": "...",
      "reference_answer": "...",
      "expected_evidence_hint": "what evidence should be retrieved"
    }}
  ]
}}

Requirements:
- Generate exactly {needed} questions.
- Every item must have category exactly "{category}".
- Category meaning: {category_guidance[category]}
- Keep questions precise enough for retrieval evaluation.
- Reference answers must be concise.

Target document id: {doc['doc_id']}

All active document summaries:
{summary_text}

Target document processed markdown:
{_clip(doc.get('context'), MAX_CONTEXT_CHARS_PER_DOC)}
""".strip()
            raw = ""
            try:
                raw = self._call_llm_bounded(
                    gen,
                    prompt,
                    phase="generate_questions",
                    doc_id=str(doc.get("doc_id") or ""),
                    category=category,
                )
                payload = _json_or_empty(raw)
                items = payload.get("items") if isinstance(payload, dict) else []
                logger.info(
                    "retrieval eval generated questions doc_id=%s category=%s requested=%d received=%d raw_chars=%d",
                    doc["doc_id"],
                    category,
                    needed,
                    len(items or []),
                    len(raw),
                )
                if not items:
                    logger.warning(
                        "question generation returned no items for %s/%s reason=%s raw=%s",
                        doc["doc_id"],
                        category,
                        "refusal" if _looks_like_refusal(raw) else "empty_json",
                        _clip(raw, 240),
                    )
            except Exception as exc:
                logger.warning("question generation failed for %s/%s: %s", doc["doc_id"], category, exc)
                items = []
                raw = f"ERROR: {exc}"
            return category, list(items or []), raw

        category_results = self._parallel_map(
            [lambda category=category: generate_category(category) for category in QUESTION_CATEGORIES]
        )
        for category, items, raw in category_results:
            for item in items or []:
                cat = str(item.get("category") or "").strip() or category
                needed = missing_counts.get(category, questions_per_category) if missing_counts else questions_per_category
                if cat != category or counts[category] >= needed:
                    continue
                question = str(item.get("question") or "").strip()
                if not question:
                    continue
                counts[category] += 1
                out.append(
                    {
                        "query_id": f"{doc['doc_id']}:{category}:{counts[category]}",
                        "doc_id": doc["doc_id"],
                        "category": category,
                        "question": question,
                        "reference_answer": str(item.get("reference_answer") or "").strip(),
                        "expected_evidence_hint": str(item.get("expected_evidence_hint") or "").strip(),
                        "generation_raw": raw if counts[category] == 1 else "",
                        "generation_source": "llm",
                    }
                )
        missing_categories = []
        for category, count in counts.items():
            needed = missing_counts.get(category, questions_per_category) if missing_counts else questions_per_category
            if count < needed:
                missing_categories.append((category, needed, count))

        if missing_categories:
            logger.warning(
                "using fallback retrieval eval questions for %s missing_categories=%s",
                doc["doc_id"],
                ",".join(cat for cat, _, _ in missing_categories),
            )
            fallback = _fallback_questions_for_doc(doc, questions_per_category)
            fallback_by_id = {str(item.get("query_id") or ""): item for item in fallback}
            for category, needed, count in missing_categories:
                for idx in range(count + 1, needed + 1):
                    item = fallback_by_id.get(f"{doc['doc_id']}:{category}:{idx}")
                    if item:
                        out.append(item)
        return out

    def _judge_relevance(
        self,
        gen: Any,
        question: Dict[str, Any],
        modality: str,
        evidence: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not evidence:
            logger.info(
                "retrieval eval relevance judge skipped query_id=%s modality=%s evidence=0",
                question.get("query_id"),
                modality,
            )
            return {"labels": [], "raw": "", "error": ""}
        prompt = f"""
Judge retrieval relevance for one query and one modality.

Return JSON only:
{{"items": [{{"evidence_id": "...", "relevance": 0, "rationale": "short"}}]}}

Relevance scale:
- 0 = irrelevant, completely different topic
- 1 = slightly relevant, same topic, but could not solely answer any part of the question
- 2 = partially relevant, same topic, could answer partial of a question but needs another to validate
- 3 = highly relevant and useful for completely and correctly answering the question

Question: {question.get('question')}
Reference answer: {question.get('reference_answer')}
Expected evidence hint: {question.get('expected_evidence_hint')}
Modality: {modality}

Evidence:
{_compact_evidence_for_prompt(evidence)}
""".strip()
        raw = ""
        try:
            raw = self._call_llm_bounded(
                gen,
                prompt,
                phase="judge_relevance",
                query_id=str(question.get("query_id") or ""),
                doc_id=str(question.get("doc_id") or ""),
                modality=modality,
            )
            payload = _json_or_empty(raw)
            labels = []
            for item in payload.get("items") or []:
                eid = str(item.get("evidence_id") or "").strip()
                if not eid:
                    continue
                labels.append(
                    {
                        "evidence_id": eid,
                        "relevance": max(0, min(2, _safe_int(item.get("relevance"), 0))),
                        "rationale": str(item.get("rationale") or "").strip(),
                    }
                )
            logger.info(
                "retrieval eval relevance judged query_id=%s modality=%s evidence=%d labels=%d raw_chars=%d",
                question.get("query_id"),
                modality,
                len(evidence),
                len(labels),
                len(raw),
            )
            return {"labels": labels, "raw": raw, "error": ""}
        except Exception as exc:
            logger.warning("relevance judge failed for %s/%s: %s", question.get("query_id"), modality, exc)
            return {"labels": [], "raw": raw, "error": str(exc)}

    def _judge_ranking(
        self,
        gen: Any,
        question: Dict[str, Any],
        modality: str,
        evidence: Sequence[Dict[str, Any]],
        labels: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        relevant_ids = [str(x.get("evidence_id")) for x in labels if _safe_int(x.get("relevance"), 0) > 0]
        if not relevant_ids:
            logger.info(
                "retrieval eval ranking judge skipped query_id=%s modality=%s relevant=0",
                question.get("query_id"),
                modality,
            )
            return {"ranked_evidence_ids": [], "raw": "", "error": ""}
        relevant_evidence = [e for e in evidence if e.get("evidence_id") in set(relevant_ids)]
        prompt = f"""
Rank relevant retrieval evidence by usefulness for answering the question.

Return JSON only:
{{"ranked_evidence_ids": ["best_evidence_id", "..."], "rationale": "short"}}

Question: {question.get('question')}
Reference answer: {question.get('reference_answer')}
Modality: {modality}

Relevant evidence:
{_compact_evidence_for_prompt(relevant_evidence)}
""".strip()
        raw = ""
        try:
            raw = self._call_llm_bounded(
                gen,
                prompt,
                phase="judge_ranking",
                query_id=str(question.get("query_id") or ""),
                doc_id=str(question.get("doc_id") or ""),
                modality=modality,
            )
            payload = _json_or_empty(raw)
            ranked = [str(x).strip() for x in (payload.get("ranked_evidence_ids") or []) if str(x).strip()]
            known = set(relevant_ids)
            ranked = [x for x in ranked if x in known]
            for eid in relevant_ids:
                if eid not in ranked:
                    ranked.append(eid)
            logger.info(
                "retrieval eval ranking judged query_id=%s modality=%s relevant=%d ranked=%d raw_chars=%d",
                question.get("query_id"),
                modality,
                len(relevant_ids),
                len(ranked),
                len(raw),
            )
            return {
                "ranked_evidence_ids": ranked,
                "rationale": str(payload.get("rationale") or "").strip(),
                "raw": raw,
                "error": "",
            }
        except Exception as exc:
            logger.warning("ranking judge failed for %s/%s: %s", question.get("query_id"), modality, exc)
            return {"ranked_evidence_ids": relevant_ids, "raw": raw, "error": str(exc)}

    def _generate_answer(self, gen: Any, question: Dict[str, Any], retrieved: Dict[str, Any]) -> Dict[str, Any]:
        evidence_text = "\n\n".join(
            [
                "Text evidence:\n" + _compact_evidence_for_prompt(retrieved.get("text") or [], max_items=10),
                "Image/page evidence:\n" + _compact_evidence_for_prompt(retrieved.get("image") or [], max_items=10),
            ]
        )
        prompt = f"""
Answer the evaluation question using only the retrieved evidence.

Return JSON only:
{{"answer": "concise answer", "rationale": "short note about which evidence supports it"}}

Question: {question.get('question')}
Reference answer for calibration: {question.get('reference_answer')}

Retrieved evidence:
{evidence_text}
""".strip()
        raw = ""
        try:
            raw = self._call_llm_bounded(
                gen,
                prompt,
                phase="generate_answer",
                query_id=str(question.get("query_id") or ""),
                doc_id=str(question.get("doc_id") or ""),
            )
            payload = _json_or_empty(raw)
            logger.info(
                "retrieval eval answer generated query_id=%s text_evidence=%d image_evidence=%d raw_chars=%d",
                question.get("query_id"),
                len(retrieved.get("text") or []),
                len(retrieved.get("image") or []),
                len(raw),
            )
            return {
                "answer": str(payload.get("answer") or "").strip() or _clip(raw, 1600),
                "rationale": str(payload.get("rationale") or "").strip(),
                "raw": raw,
                "error": "",
            }
        except Exception as exc:
            logger.warning("answer generation failed for %s: %s", question.get("query_id"), exc)
            return {"answer": "", "rationale": "", "raw": raw, "error": str(exc)}

    def _judge_answer(
        self,
        gen: Any,
        question: Dict[str, Any],
        generated_answer: str,
        retrieved: Dict[str, Any],
    ) -> Dict[str, Any]:
        evidence_text = "\n\n".join(
            [
                "Text evidence:\n" + _compact_evidence_for_prompt(retrieved.get("text") or [], max_items=10),
                "Image/page evidence:\n" + _compact_evidence_for_prompt(retrieved.get("image") or [], max_items=10),
            ]
        )
        prompt = f"""
Judge the generated answer for one retrieval-evaluation query.

Return JSON only:
{{
  "correctness": "correct | partially_correct | incorrect",
  "faithfulness": "faithful | partially_faithful | hallucinated",
  "answer_support": "fully_supported | partially_supported | not_supported",
  "rationale": "short"
}}

Definitions:
- correctness: whether the answer matches the reference answer.
- faithfulness: whether the answer avoids unsupported claims.
- answer_support: whether retrieved evidence supports the answer.

Question: {question.get('question')}
Reference answer: {question.get('reference_answer')}
Generated answer: {generated_answer}

Retrieved evidence:
{evidence_text}
""".strip()
        raw = ""
        try:
            raw = self._call_llm_bounded(
                gen,
                prompt,
                phase="judge_answer",
                query_id=str(question.get("query_id") or ""),
                doc_id=str(question.get("doc_id") or ""),
            )
            payload = _json_or_empty(raw)
            logger.info(
                "retrieval eval answer judged query_id=%s correctness=%s support=%s raw_chars=%d",
                question.get("query_id"),
                payload.get("correctness"),
                payload.get("answer_support"),
                len(raw),
            )
            return {
                "correctness": str(payload.get("correctness") or "incorrect").strip(),
                "faithfulness": str(payload.get("faithfulness") or "hallucinated").strip(),
                "answer_support": str(payload.get("answer_support") or "not_supported").strip(),
                "rationale": str(payload.get("rationale") or "").strip(),
                "raw": raw,
                "error": "",
            }
        except Exception as exc:
            logger.warning("answer judge failed for %s: %s", question.get("query_id"), exc)
            return {
                "correctness": "incorrect",
                "faithfulness": "hallucinated",
                "answer_support": "not_supported",
                "rationale": "",
                "raw": raw,
                "error": str(exc),
            }

    def _run_retrieval(self, question: Dict[str, Any], top_k: int, retriever_type: str, search_scope: str) -> Dict[str, Any]:
        search_scope = search_scope if search_scope in {"text", "image", "both"} else "both"
        text_retriever = retriever_type if retriever_type in {"bm25", "dense", "hybrid"} else "hybrid"
        logger.info(
            "retrieval eval retrieving query_id=%s doc_id=%s top_k=%d retriever=%s scope=%s question=%r",
            question.get("query_id"),
            question.get("doc_id"),
            top_k,
            text_retriever,
            search_scope,
            _clip_for_log(question.get("question"), 220),
        )
        out = SearchOrchestrator(self.cfg, user_id=self.user_id).run(
            query=str(question.get("question") or ""),
            top_k=top_k,
            retriever_type=text_retriever,
            include_images=True,
            images_for_generation=0,
            mode="retrieval_only",
            search_scope=search_scope,
            generation_model=None,
            skip_reranker=True,
        )
        normalized = {
            "text": _normalize_evidence("text", out.get("text_results") or []),
            "image": _normalize_evidence("image", out.get("image_results") or []),
            "telemetry": out.get("telemetry") or {},
        }
        logger.info(
            "retrieval eval retrieved query_id=%s text=%d image=%d telemetry=%s",
            question.get("query_id"),
            len(normalized["text"]),
            len(normalized["image"]),
            normalized["telemetry"],
        )
        return normalized

    def _evaluate_question(
        self,
        gen: Any,
        question: Dict[str, Any],
        *,
        top_k: int,
        retriever_type: str,
        search_scope: str,
        modalities: Sequence[str],
        question_index: int = 0,
        total_questions: int = 0,
    ) -> Dict[str, Any]:
        logger.info(
            "retrieval eval evaluating question %d/%d query_id=%s doc_id=%s category=%s",
            question_index,
            total_questions,
            question.get("query_id"),
            question.get("doc_id"),
            question.get("category"),
        )
        retrieved = self._run_retrieval(question, top_k, retriever_type, search_scope)

        def judge_modality(modality: str) -> tuple[str, Dict[str, Any], Dict[str, Any]]:
            relevance = self._judge_relevance(gen, question, modality, retrieved[modality])
            ranking = self._judge_ranking(gen, question, modality, retrieved[modality], relevance.get("labels") or [])
            return modality, relevance, ranking

        judgment_rows = self._parallel_map([lambda modality=modality: judge_modality(modality) for modality in modalities])
        answer = self._generate_answer(gen, question, retrieved)
        answer_judgment = self._judge_answer(gen, question, answer.get("answer") or "", retrieved)

        llm_judgments: Dict[str, Any] = {}
        human_judgments: Dict[str, Any] = {}
        for modality, relevance, ranking in judgment_rows:
            llm_judgments[modality] = {
                "labels": relevance.get("labels") or [],
                "ranked_evidence_ids": ranking.get("ranked_evidence_ids") or [],
                "relevance_raw": relevance.get("raw") or "",
                "ranking_raw": ranking.get("raw") or "",
                "relevance_error": relevance.get("error") or "",
                "ranking_error": ranking.get("error") or "",
            }
            human_judgments[modality] = {"labels": [], "ranked_evidence_ids": []}

        logger.info(
            "retrieval eval evaluated question %d/%d query_id=%s modalities=%s",
            question_index,
            total_questions,
            question.get("query_id"),
            ",".join(str(m) for m in modalities),
        )
        return {
            "query_id": question["query_id"],
            "question": question,
            "generated_answer": answer,
            "llm_answer_judgment": answer_judgment,
            "human_answer_judgment": {},
            "retrieved": retrieved,
            "llm_judgments": llm_judgments,
            "human_judgments": human_judgments,
        }

    def create_run(
        self,
        *,
        run_id: str | None = None,
        top_k: int = 10,
        k_values: Sequence[int] | None = None,
        retriever_type: str = "hybrid",
        search_scope: str = "both",
        questions_per_category: int = 5,
        max_documents: int | None = None,
        selected_document_ids: Sequence[str] | None = None,
        skip_knowledge_lookup: bool = False,
        reuse_generated_questions: bool = True,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        k_values = tuple(sorted({int(k) for k in (k_values or DEFAULT_K_VALUES) if int(k) > 0}))
        if not k_values:
            k_values = DEFAULT_K_VALUES
        top_k = max(int(top_k or 10), max(k_values))
        retriever_type = retriever_type if retriever_type in {"bm25", "dense", "hybrid"} else "hybrid"
        search_scope = search_scope if search_scope in {"text", "image", "both"} else "both"
        modalities = ("text", "image") if search_scope == "both" else (search_scope,)
        questions_per_category = max(1, min(10, int(questions_per_category or 5)))
        run_id = run_id or self.new_run_id()
        self._current_run_id = run_id
        self._progress_counts = {}
        gc, gen = _generation_config(self.cfg)
        logger.info(
            "retrieval eval starting run_id=%s user_id=%s selected=%s scope=%s retriever=%s q_per_category=%d top_k=%d concurrency=%d",
            run_id,
            self.user_id,
            selected_document_ids or [],
            search_scope,
            retriever_type,
            questions_per_category,
            top_k,
            LLM_EVAL_CONCURRENCY,
        )

        selected_doc_ids = _normalize_selected_doc_ids(selected_document_ids)
        docs = self._active_documents(
            max_documents=max_documents,
            skip_knowledge_lookup=skip_knowledge_lookup,
            selected_document_ids=selected_doc_ids,
        )
        if not docs:
            if selected_doc_ids:
                raise ValueError(
                    "Selected file is not ready for retrieval evaluation. Make sure it is processed and indexed."
                )
            raise ValueError("No processed documents found for retrieval evaluation")
        logger.info(
            "retrieval eval active documents run_id=%s count=%d docs=%s",
            run_id,
            len(docs),
            [
                {
                    "doc_id": d.get("doc_id"),
                    "display_name": d.get("display_name"),
                    "context_chars": len(str(d.get("context") or "")),
                    "knowledge_id": (d.get("knowledge") or {}).get("knowledge_id"),
                }
                for d in docs
            ],
        )
        logger.info("retrieval eval summarizing %d document(s) run_id=%s", len(docs), run_id)
        summaries = self._parallel_map([lambda doc=doc: self._summarize_doc(gen, doc) for doc in docs])
        logger.info("retrieval eval summaries complete run_id=%s count=%d", run_id, len(summaries))
        
        reused_questions_by_doc: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
        if reuse_generated_questions and self.root.exists():
            for p in sorted(self.root.glob("*/report.json"), key=lambda x: x.stat().st_mtime, reverse=True):
                try:
                    prev_run = _read_json(p)
                    for q in prev_run.get("questions") or []:
                        doc_id = str(q.get("doc_id") or "")
                        cat = str(q.get("category") or "")
                        if doc_id and cat:
                            cat_dict = reused_questions_by_doc.setdefault(doc_id, {})
                            cat_dict.setdefault(cat, []).append(q)
                except Exception:
                    pass

        def questions_for_doc(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
            doc_id = doc["doc_id"]
            existing = reused_questions_by_doc.get(doc_id, {})
            # extract reusable ones up to requested counts
            reused_for_doc: List[Dict[str, Any]] = []
            counts = {cat: 0 for cat in QUESTION_CATEGORIES}
            for cat in QUESTION_CATEGORIES:
                for eq in existing.get(cat, []):
                    if counts[cat] < questions_per_category:
                        counts[cat] += 1
                        clone = dict(eq)
                        clone["query_id"] = f"{doc_id}:{cat}:{counts[cat]}"
                        reused_for_doc.append(clone)
            reused_count = len(reused_for_doc)
            if reused_count:
                logger.info("retrieval eval reused questions doc_id=%s count=%d", doc_id, reused_count)

            # generate missing if any
            if sum(counts.values()) < questions_per_category * len(QUESTION_CATEGORIES):
                needed_per_cat = {cat: questions_per_category - counts[cat] for cat in QUESTION_CATEGORIES}
                new_questions = self._generate_questions(gen, doc, summaries, questions_per_category, missing_counts=needed_per_cat)
                for nq in new_questions:
                    cat = str(nq.get("category"))
                    if counts.get(cat, 0) < questions_per_category:
                        counts[cat] = counts.get(cat, 0) + 1
                        nq["query_id"] = f"{doc_id}:{cat}:{counts[cat]}"
                        reused_for_doc.append(nq)
            logger.info(
                "retrieval eval questions ready doc_id=%s total=%d reused=%d generated_or_fallback=%d",
                doc_id,
                len(reused_for_doc),
                reused_count,
                max(len(reused_for_doc) - reused_count, 0),
            )
            return reused_for_doc

        questions: List[Dict[str, Any]] = []
        logger.info("retrieval eval preparing questions run_id=%s docs=%d", run_id, len(docs))
        for doc_questions in self._parallel_map([lambda doc=doc: questions_for_doc(doc) for doc in docs]):
            questions.extend(doc_questions)

        if not questions:
            raise RuntimeError(
                "Retrieval eval could not generate any questions from the selected processed document. "
                "Check the judge model response and processed markdown content."
            )
        logger.info(
            "retrieval eval generated question set run_id=%s total=%d by_doc=%s",
            run_id,
            len(questions),
            {
                doc["doc_id"]: sum(1 for q in questions if q.get("doc_id") == doc["doc_id"])
                for doc in docs
            },
        )

        logger.info("retrieval eval evaluating %d question(s) run_id=%s", len(questions), run_id)
        results = self._parallel_map(
            [
                lambda question=question, idx=idx: self._evaluate_question(
                    gen,
                    question,
                    top_k=top_k,
                    retriever_type=retriever_type,
                    search_scope=search_scope,
                    modalities=modalities,
                    question_index=idx,
                    total_questions=len(questions),
                )
                for idx, question in enumerate(questions, start=1)
            ]
        )

        run = {
            "run_id": run_id,
            "user_id": self.user_id,
            "status": "completed",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "config": {
                "top_k": top_k,
                "k_values": list(k_values),
                "retriever_type": retriever_type,
                "search_scope": search_scope,
                "questions_per_category": questions_per_category,
                "max_documents": max_documents,
                "selected_document_ids": selected_doc_ids,
                "judge_provider": gc.provider,
                "judge_model": gc.model_name,
                "judge_guardrail_enabled": bool(getattr(gc, "enable_guardrails", True)),
            },
            "active_files": [
                {
                    "doc_id": d["doc_id"],
                    "display_name": d["display_name"],
                    "total_files": d["total_files"],
                    "knowledge": d.get("knowledge") or {},
                }
                for d in docs
            ],
            "document_summaries": summaries,
            "questions": questions,
            "results": results,
            "metrics": {},
        }
        run["metrics"] = self.compute_metrics(run)
        run["timings_ms"] = self.compute_timing_summary(run)
        run["timings_ms"]["wall_total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "retrieval eval completed run_id=%s user_id=%s questions=%d results=%d wall_total_ms=%.2f",
            run_id,
            self.user_id,
            len(questions),
            len(results),
            run["timings_ms"]["wall_total_ms"],
        )
        return self.save_run(run)

    def compute_timing_summary(self, run: Dict[str, Any]) -> Dict[str, Any]:
        text_rows: List[Dict[str, Any]] = []
        image_rows: List[Dict[str, Any]] = []
        retrieval_wall_total_ms = 0
        for result in run.get("results") or []:
            telemetry = (((result.get("retrieved") or {}).get("telemetry") or {}) if isinstance(result, dict) else {})
            details = telemetry.get("retrieval_details_ms") or {}
            steps = telemetry.get("steps_ms") or {}
            retrieval_wall_total_ms += _safe_int((details or {}).get("total_ms"), _safe_int((steps or {}).get("retrieval_total"), 0))
            text_rows.append(dict((details or {}).get("text") or {}))
            image_rows.append(dict((details or {}).get("image") or {}))

        return {
            "retrieval": {
                "query_count": len(run.get("results") or []),
                "wall_total_ms": retrieval_wall_total_ms,
                "text": {
                    "total_ms": _sum_ms(text_rows, "total_ms"),
                    "embed_ms": _sum_ms(text_rows, "embed_ms") + _sum_ms(text_rows, "dense_embed_ms"),
                    "bm25_ms": _sum_ms(text_rows, "bm25_search_ms") + _sum_ms(text_rows, "bm25_bm25_search_ms"),
                    "dense_qdrant_ms": _sum_ms(text_rows, "qdrant_search_ms") + _sum_ms(text_rows, "dense_qdrant_search_ms"),
                    "rerank_ms": _sum_ms(text_rows, "rerank_ms"),
                },
                "image": {
                    "total_ms": _sum_ms(image_rows, "total_ms"),
                    "embed_ms": _sum_ms(image_rows, "embed_ms"),
                    "qdrant_ms": _sum_ms(image_rows, "qdrant_search_ms"),
                    "rerank_ms": _sum_ms(image_rows, "rerank_ms"),
                },
            }
        }

    def compute_metrics(self, run: Dict[str, Any]) -> Dict[str, Any]:
        k_values = [int(k) for k in ((run.get("config") or {}).get("k_values") or DEFAULT_K_VALUES)]
        search_scope = str((run.get("config") or {}).get("search_scope") or "both")
        modalities = ("text", "image") if search_scope == "both" else (search_scope if search_scope in {"text", "image"} else "text",)
        metrics: Dict[str, Any] = {}
        for source in ("llm", "human"):
            rows: Dict[str, List[Dict[str, Any]]] = {modality: [] for modality in modalities}
            for result in run.get("results") or []:
                question = result.get("question") or {}
                judgment_key = f"{source}_judgments"
                judgments = result.get(judgment_key) or {}
                for modality in modalities:
                    evidence = ((result.get("retrieved") or {}).get(modality) or [])
                    labels = ((judgments.get(modality) or {}).get("labels") or [])
                    if source == "human" and not labels:
                        continue
                    rows[modality].append(
                        {
                            "query_id": result.get("query_id"),
                            "doc_id": question.get("doc_id"),
                            "category": question.get("category"),
                            "metrics": _metrics_for_one(evidence, labels, k_values),
                        }
                    )
            metrics[source] = {}
            for modality in modalities:
                metrics[source][modality] = {
                    "aggregate": _aggregate_metric_rows(rows[modality]),
                    "by_category": _grouped_metric_summary(rows[modality], "category"),
                    "by_file": _grouped_metric_summary(rows[modality], "doc_id"),
                    "per_query": rows[modality],
                }
        return metrics

    def save_human_labels(
        self,
        run_id: str,
        *,
        query_id: str,
        modality: str,
        labels: Sequence[Dict[str, Any]],
        ranked_evidence_ids: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        run = self.load_run(run_id)
        modality = "image" if modality == "image" else "text"
        normalized_labels: List[Dict[str, Any]] = []
        for label in labels or []:
            eid = str(label.get("evidence_id") or "").strip()
            if not eid:
                continue
            normalized_labels.append(
                {
                    "evidence_id": eid,
                    "relevance": max(0, min(2, _safe_int(label.get("relevance"), 0))),
                    "rationale": str(label.get("rationale") or "").strip(),
                    "updated_at": _utc_now(),
                }
            )
        ranked = [str(x).strip() for x in (ranked_evidence_ids or []) if str(x).strip()]
        for result in run.get("results") or []:
            if str(result.get("query_id") or "") != str(query_id):
                continue
            hj = result.setdefault("human_judgments", {})
            hj[modality] = {
                "labels": normalized_labels,
                "ranked_evidence_ids": ranked,
                "updated_at": _utc_now(),
            }
            run["updated_at"] = _utc_now()
            run["metrics"] = self.compute_metrics(run)
            run["timings_ms"] = self.compute_timing_summary(run)
            return self.save_run(run)
        raise KeyError(query_id)

    def save_human_answer_judgment(
        self,
        run_id: str,
        *,
        query_id: str,
        correctness: str,
        faithfulness: str,
        answer_support: str,
        rationale: str = "",
    ) -> Dict[str, Any]:
        run = self.load_run(run_id)
        valid_correctness = {"correct", "partially_correct", "incorrect"}
        valid_faithfulness = {"faithful", "partially_faithful", "hallucinated"}
        valid_support = {"fully_supported", "partially_supported", "not_supported"}
        for result in run.get("results") or []:
            if str(result.get("query_id") or "") != str(query_id):
                continue
            result["human_answer_judgment"] = {
                "correctness": correctness if correctness in valid_correctness else "incorrect",
                "faithfulness": faithfulness if faithfulness in valid_faithfulness else "hallucinated",
                "answer_support": answer_support if answer_support in valid_support else "not_supported",
                "rationale": str(rationale or "").strip(),
                "updated_at": _utc_now(),
            }
            run["updated_at"] = _utc_now()
            return self.save_run(run)
        raise KeyError(query_id)

    def recompute(self, run_id: str) -> Dict[str, Any]:
        run = self.load_run(run_id)
        run["metrics"] = self.compute_metrics(run)
        run["timings_ms"] = self.compute_timing_summary(run)
        run["updated_at"] = _utc_now()
        return self.save_run(run)
