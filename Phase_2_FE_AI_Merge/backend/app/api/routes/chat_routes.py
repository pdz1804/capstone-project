from __future__ import annotations

import asyncio
import base64
import contextlib
import io
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List

from agent.strands_chat_runtime import build_query_with_history, run_chat_agent


@contextlib.contextmanager
def _suppress_pipeline_noise():
    """Temporarily raise all log levels to ERROR and swallow stdout/stderr
    during SearchOrchestrator calls so pipeline logs, stats, and metadata
    never leak into the Strands tool return value."""
    _root = logging.root
    _orig_level = _root.level
    _root.setLevel(logging.ERROR)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            yield
    finally:
        _root.setLevel(_orig_level)


from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import storage_user_id
from app.api.schemas import ChatStreamRequest
from app.core.paths import merged_runtime_settings
from app.repositories.chat_history_repository_dynamo import allocate_chat_message_id
from app.services.chat_attachment_storage import persist_chat_visualization_png
from app.services.chat_history_service import ChatHistoryService
from app.services.processed_markdown_service import (
    gather_processed_markdown_context,
    sanitize_insights_document_id,
)
from app.services.search_orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])

MEM_ID = (os.getenv("AGENTCORE_MEMORY_ID") or "memory_K2P_chat_assistant_stm-0nESTA48sz").strip()
AGENTCORE_REGION = (os.getenv("AGENTCORE_REGION") or "us-west-2").strip()
CHAT_AGENT_RUNTIME = (os.getenv("CHAT_AGENT_RUNTIME") or "local").strip().lower()
AGENTCORE_RUNTIME_ARN = (os.getenv("AGENTCORE_RUNTIME_ARN") or "").strip()

# Folder/file name fragments that indicate pipeline system artefacts — not learnable content.
_SYSTEM_FOLDER_TOKENS = frozenset({
    "log", "logs", "logging",
    "metadata", "meta", "stats", "statistics",
    "pipeline", "pipeline-wide", "pipeline_wide",
    "debug", "trace", "error", "warning",
    "cache", "tmp", "temp", "checkpoint",
    "__pycache__", ".git",
})


def _is_content_document(folder_name: str, display_name: str = "") -> bool:
    """Return True only for real educational content folders.
    Rejects system/pipeline artefact folders (logs, metadata, stats, etc.)."""
    raw = (folder_name or display_name or "").strip()
    # Normalise: lower, replace separators with spaces
    normalised = raw.lower().replace("-", " ").replace("_", " ").replace("·", " ")
    tokens = set(normalised.split())
    # Reject if any token exactly matches a known system keyword
    if tokens & _SYSTEM_FOLDER_TOKENS:
        return False
    # Also reject very short or suspiciously generic names
    if len(raw) < 3:
        return False
    return True

DEFAULT_SUGGESTIONS = [
    "What documents do I have in my knowledge base?",
    "Show me my quiz performance and learning analytics",
    "Quiz me on the key topics from my lectures",
]


def _compact_text_rows(rows: List[Dict[str, Any]], limit: int = 6) -> str:
    parts: List[str] = []
    for i, r in enumerate(rows[:limit], start=1):
        txt = str(r.get("text") or "").strip().replace("\n", " ")
        src = str(r.get("source") or "")
        if len(txt) > 360:
            txt = txt[:360] + "..."
        if src:
            parts.append(f"[{i}] {txt}\nsource: {src}")
        else:
            parts.append(f"[{i}] {txt}")
    return "\n\n".join(parts) if parts else "(no text matches)"


def _compact_image_rows(rows: List[Dict[str, Any]], limit: int = 6) -> str:
    parts: List[str] = []
    for i, r in enumerate(rows[:limit], start=1):
        cap = str(r.get("caption") or r.get("text") or "").strip().replace("\n", " ")
        src = str(r.get("source") or r.get("source_path") or r.get("storage_uri") or "")
        page = r.get("page")
        if len(cap) > 280:
            cap = cap[:280] + "..."
        page_str = f" page={page}" if page is not None else ""
        parts.append(f"[{i}] {cap or '(no caption)'}{page_str}\nsource: {src}")
    return "\n\n".join(parts) if parts else "(no image matches)"


def _strip_raw_tool_markup(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<function_calls>.*?</function_calls>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<function_result>.*?</function_result>\s*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _scrub_data_image_markdown_for_history(text: str) -> str:
    """Avoid persisting huge base64 payloads in chat history."""
    if not text or "data:image/" not in text:
        return text
    return re.sub(
        r"!\[([^\]]*)\]\(data:image/[^)]+\)",
        r"*[BK-MInD visualization was shown in this reply; images are not stored — ask again to regenerate.]*",
        text,
    )


def _strip_data_url_images(text: str) -> str:
    """Remove markdown data-URL images from streamed text (avoids huge SSE / duplicate images)."""
    if not text or "data:image/" not in text:
        return text
    return re.sub(r"!\[[^\]]*\]\(data:image/[^)]+\)\s*", "", text).strip()


def _get_chat_history_service() -> ChatHistoryService | None:
    try:
        return ChatHistoryService.from_env()
    except Exception:
        return None


@router.post("/chat/stream")
async def chat_stream(req: ChatStreamRequest, user_id: str = Depends(storage_user_id)):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    logger.info("chat_stream: STARTING user_id=%s query_len=%d session_id=%s", user_id, len(query), req.session_id)

    cfg = merged_runtime_settings()
    orch = SearchOrchestrator(cfg, user_id=user_id)
    session_id = req.session_id.strip() if req.session_id.strip() else str(uuid.uuid4())
    logger.info("chat_stream: Using session_id=%s (new=%s)", session_id, not req.session_id.strip())
    preferred_persona = (req.persona or "").strip()
    education_context = (req.education_description or "").strip()
    history_svc = _get_chat_history_service()
    prior_messages: list[dict[str, Any]] = []

    if history_svc is not None:
        try:
            logger.info("chat_stream: Ensuring session user_id=%s session_id=%s", user_id, session_id)
            history_svc.ensure_session(
                user_id=user_id,
                session_id=session_id,
                title=query,
                pinned=False,
            )
            logger.info("chat_stream: Session ensured, retrieving prior messages")
            prior_messages = history_svc.list_recent_messages(
                user_id=user_id,
                session_id=session_id,
                limit=8,
            )
            logger.info("chat_stream: Retrieved %d prior messages from session", len(prior_messages))
            history_svc.put_message(
                user_id=user_id,
                session_id=session_id,
                role="user",
                content=query,
            )
            logger.info("chat_stream: User message saved to session")
        except Exception as history_err:
            logger.warning("Chat history persistence unavailable for this request: %s", history_err)
            history_svc = None

    async def event_stream():
        def emit(payload: Dict[str, Any]) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        yield emit({"type": "session", "session_id": session_id})
        yield emit({"type": "status", "message": "Planning tool calls..."})
        try:
            tool_traces: List[Dict[str, Any]] = []
            # Infographic bytes must NOT be returned in tool strings — Bedrock/Strands context overflows.
            chat_viz_attachments: List[Dict[str, str]] = []
            # Same chat turn: require get_processed_markdown before generate_learning_visualization per document_id.
            viz_markdown_prefetched: set[str] = set()

            from strands import tool

            # ── Tool 1: Text RAG ──────────────────────────────────────────────
            @tool
            def text_rag(query: str, top_k: int = req.top_k) -> str:
                """Search the knowledge base using hybrid text retrieval (BM25 + semantic).
                Use for any question about lecture content, documents, notes, or course materials."""
                with _suppress_pipeline_noise():
                    result = orch.run(
                        query=query,
                        top_k=max(1, min(int(top_k), 30)),
                        retriever_type="hybrid",
                        include_images=False,
                        images_for_generation=0,
                        mode="retrieval_only",
                        search_scope="text",
                        generation_model=None,
                        skip_reranker=True,
                    )
                rows = result.get("text_results") or []
                compact = _compact_text_rows(rows)
                tool_traces.append({
                    "tool": "text_rag",
                    "query": query,
                    "top_k": max(1, min(int(top_k), 30)),
                    "search_scope": "text",
                    "index_backend": "BM25 + Qdrant text collection",
                    "result_count": len(rows),
                    "result_preview": compact,
                })
                return compact

            # ── Tool 2: Image RAG ─────────────────────────────────────────────
            @tool
            def image_rag(query: str, top_k: int = 4) -> str:
                """Search the visual knowledge base using vision-language retrieval (ColQwen).
                Use when the user asks about diagrams, charts, slides, figures, or visual content."""
                with _suppress_pipeline_noise():
                    result = orch.run(
                        query=query,
                        top_k=max(1, min(int(top_k), 10)),
                        retriever_type="hybrid",
                        include_images=True,
                        images_for_generation=0,
                        mode="retrieval_only",
                        search_scope="image",
                        generation_model=None,
                        skip_reranker=True,
                    )
                rows = result.get("image_results") or []
                compact = _compact_image_rows(rows)
                tool_traces.append({
                    "tool": "image_rag",
                    "query": query,
                    "top_k": max(1, min(int(top_k), 10)),
                    "search_scope": "image",
                    "index_backend": "ColQwen + Qdrant image collection",
                    "result_count": len(rows),
                    "result_preview": compact,
                })
                return compact

            # ── Tool 3: Quiz Performance Analytics ───────────────────────────
            @tool
            def get_quiz_performance() -> str:
                """Retrieve the student's quiz performance analytics: overall accuracy, topic-level
                breakdown with pass/fail indicators, and the 5 most recent quiz attempts.
                Use when the user asks about their progress, scores, strengths, weaknesses, or learning analytics."""
                try:
                    from app.services.quiz_results_service import QuizResultsService
                    svc = QuizResultsService.from_env()
                    items = svc.list_for_user(user_id=user_id, limit=200)
                    if not items:
                        return (
                            "No quiz attempts recorded yet. "
                            "Take quizzes in the Learning Path section to start tracking your progress."
                        )

                    def _get(item: Any, key: str, default: Any = 0) -> Any:
                        return getattr(item, key, None) if not isinstance(item, dict) else item.get(key, default)

                    total = len(items)
                    avg_pct = sum(_get(i, "score", 0) / max(_get(i, "total", 1), 1) for i in items) / total * 100

                    by_topic: Dict[str, list] = {}
                    for item in items:
                        key = str(_get(item, "quiz_topic") or _get(item, "document_id") or "General")
                        by_topic.setdefault(key, []).append(item)

                    lines = [
                        f"## Quiz Performance ({total} attempts)",
                        f"**Overall accuracy: {avg_pct:.1f}%**",
                        "",
                        "### By Topic",
                    ]
                    for topic, results in sorted(by_topic.items()):
                        t_scores = [_get(r, "score", 0) / max(_get(r, "total", 1), 1) for r in results]
                        t_avg = sum(t_scores) / len(t_scores) * 100
                        emoji = "✅" if t_avg >= 70 else "⚠️" if t_avg >= 50 else "❌"
                        lines.append(f"- {emoji} **{topic}**: {t_avg:.1f}% ({len(results)} attempts)")

                    recent = sorted(items, key=lambda x: str(_get(x, "created_at") or ""), reverse=True)[:5]
                    lines += ["", "### Recent Attempts"]
                    for r in recent:
                        sc = _get(r, "score", 0)
                        tot = max(_get(r, "total", 1), 1)
                        pct = sc / tot * 100
                        topic = _get(r, "quiz_topic") or _get(r, "document_id") or "Quiz"
                        date = str(_get(r, "created_at") or "")[:10]
                        lines.append(f"- **{topic}**: {sc}/{tot} ({pct:.0f}%) — {date}")

                    return "\n".join(lines)
                except RuntimeError:
                    return "Quiz results storage is not configured (DynamoDB not set up)."
                except Exception as e:
                    logger.warning("get_quiz_performance failed: %s", e)
                    return f"Could not load quiz performance: {e}"

            # ── Tool 4: List My Documents ─────────────────────────────────────
            @tool
            def list_my_documents() -> str:
                """List all processed documents and files available in the knowledge base,
                including their document_id values needed for other tools.
                Use when the user asks what content is available, or needs a document_id."""
                try:
                    from app.api.routes.files_routes import list_files_with_metadata

                    logger.info("list_my_documents: Starting document list for user=%s", user_id)

                    # Use the same function as the UI's file list tab
                    metadata_response = list_files_with_metadata(user_id)
                    files = metadata_response.get("files") or []

                    logger.info(
                        "list_my_documents: Retrieved %d files from list_files_with_metadata. "
                        "Total count: %d, Pipeline docs: %d",
                        len(files),
                        metadata_response.get("count", 0),
                        metadata_response.get("pipeline_document_count", 0),
                    )

                    if not files:
                        logger.warning("list_my_documents: No files returned")
                        return "No documents found. Upload files to get started!"

                    # Build display with file names, pipeline document_id (for tools), and statuses
                    lines = [
                        f"**Your Knowledge Base** ({len(files)} files):",
                        "",
                        "For **get_processed_markdown** / **generate_learning_visualization**, copy `document_id` exactly from the line below (or pass the **file_name** — it will be resolved).",
                        "",
                    ]

                    for file_info in files[:50]:
                        file_name = file_info.get("file_name") or file_info.get("name") or "unknown"
                        doc_id_tool = str(file_info.get("document_id") or "").strip() or "—"
                        status = file_info.get("status") or "unknown"
                        index_status = file_info.get("index_status") or ""
                        st_counts = file_info.get("processed_stage_counts") or {}
                        s3c = int((st_counts.get("stage3_document_processed") or 0) or 0)

                        # Build status string
                        if status == "indexed":
                            if index_status == "all":
                                status_str = "Indexed (All)"
                            elif index_status == "text":
                                status_str = "Indexed (Text)"
                            elif index_status == "image":
                                status_str = "Indexed (Image)"
                            else:
                                status_str = "Indexed"
                        elif status == "processed":
                            status_str = "Processed"
                        else:
                            status_str = "Uploaded"

                        entry = (
                            f"- **{file_name}** | **document_id=`{doc_id_tool}`** | {status_str} "
                            f"| stage3_files={s3c}"
                        )
                        lines.append(entry)

                    if len(files) > 50:
                        lines.append(f"... and {len(files) - 50} more")

                    result = "\n".join(lines)
                    logger.info("list_my_documents: Returning %d files for display", len(files))
                    return result

                except Exception as e:
                    logger.exception("list_my_documents failed: %s", e)
                    return f"Could not list documents: {e}"

            # ── Tool: Full processed markdown (pipeline .md, not vector snippets) ──
            @tool
            def get_processed_markdown(document_id: str, max_chars: int = 120_000) -> str:
                """Load full processed markdown for ONE document (pipeline stage3/stage4 .md) — not vector RAG snippets.

                Pass **document_id** exactly as shown in list_my_documents (`document_id=...`), **or** the upload
                **file_name** (e.g. `Report.pdf`) — same resolution as the Lecture viewer /files metadata.

                **Mandatory before generate_learning_visualization** for named files: call once per document.
                max_chars: cap on returned characters (default 120000)."""
                from pathlib import Path

                from app.api.routes.files_routes import _find_document_entry_for_input_name
                from app.services.processed_documents_service import build_processed_documents_snapshot

                raw = (document_id or "").strip()
                if not raw:
                    return "Invalid: provide document_id from list_my_documents or the upload file_name."

                try:
                    cap = max(4_000, min(int(float(max_chars)), 200_000))
                except Exception:
                    cap = 120_000

                snap = build_processed_documents_snapshot(user_id, include_preview=False)
                resolved: str | None = None

                cand = sanitize_insights_document_id(raw or None)
                if cand:
                    probe = gather_processed_markdown_context(user_id, cand, min(cap, 6_000))
                    if probe.strip():
                        resolved = cand

                if not resolved:
                    entry = _find_document_entry_for_input_name(snap, raw)
                    if not entry:
                        entry = _find_document_entry_for_input_name(snap, Path(raw.replace("\\", "/")).name)
                    if entry:
                        rid = str(entry.get("id") or "").strip()
                        resolved = sanitize_insights_document_id(rid or None)

                if not resolved:
                    return (
                        "Could not map that value to a pipeline document. Use list_my_documents and copy "
                        "**document_id=`...`** exactly, or pass the exact **file_name** of the upload."
                    )

                ctx = gather_processed_markdown_context(user_id, resolved, cap)
                if not ctx.strip():
                    return (
                        f"No processed markdown under pipeline folder `{resolved}` (stage3/stage4 .md). "
                        "Indexed text can exist without markdown on disk — run **Process** in Knowledge Management, "
                        "then try again. Check list_my_documents `stage3_files=` for that row."
                    )
                viz_markdown_prefetched.add(resolved)
                return ctx

            # ── Tool 5: Document Summary ──────────────────────────────────────
            @tool
            def get_document_summary(document_id: str, focus_query: str = "", depth: str = "brief") -> str:
                """Generate a summary of a specific document.
                Get document_id from list_my_documents first.
                depth: 'brief' (quick overview), 'detailed' (sections + key concepts), 'comprehensive' (full analysis).
                focus_query: optional topic or concept to emphasize in the summary."""
                try:
                    from app.services.insights_service import InsightsService
                    svc = InsightsService(cfg, user_id=user_id)
                    result = svc.lecture_summary(
                        focus_query=focus_query,
                        depth=depth,
                        document_id=document_id or None,
                        tone="neutral",
                        target_length="short" if depth == "brief" else "medium",
                    )
                    if result.get("error"):
                        return f"Summary error: {result['error']}"
                    summary = (result.get("summary") or "").strip()
                    return summary[:4000] if summary else "No summary could be generated. Ensure the document is processed."
                except Exception as e:
                    logger.warning("get_document_summary failed: %s", e)
                    return f"Could not generate summary: {e}"

            # ── Tool 6: Generate Quiz ─────────────────────────────────────────
            @tool
            def generate_quiz(
                topic: str,
                num_questions: int = 4,
                difficulty: str = "intermediate",
                document_id: str = "",
            ) -> str:
                """Generate multiple-choice quiz questions on any topic from the knowledge base.
                Use when the user wants to be tested, practice, or generate study questions.
                difficulty: 'basic', 'intermediate', or 'advanced'.
                document_id: optional — scope to a specific document (use list_my_documents to find it)."""
                try:
                    from app.services.insights_service import InsightsService
                    svc = InsightsService(cfg, user_id=user_id)
                    result = svc.mcq_quiz(
                        topic=topic,
                        num_questions=max(1, min(int(num_questions), 10)),
                        difficulty=difficulty,
                        document_id=document_id or None,
                        question_style="exam",
                        include_explanations=True,
                    )
                    if result.get("error"):
                        return f"Quiz generation error: {result['error']}"

                    questions = result.get("questions") or []
                    if not questions:
                        raw = result.get("raw", "")
                        return raw[:2000] if raw else f"Could not generate questions on '{topic}'. Ensure content is processed and indexed."

                    lines = [f"## Quiz: {topic}", f"*{difficulty.capitalize()} — {len(questions)} questions*", ""]
                    for i, q in enumerate(questions, 1):
                        lines.append(f"**Q{i}. {q.get('question', '')}**")
                        options = q.get("options") or []
                        correct = q.get("correct_index", 0)
                        for j, opt in enumerate(options):
                            marker = "✅" if j == correct else "○"
                            lines.append(f"  {marker} {chr(65 + j)}. {opt}")
                        if q.get("explanation"):
                            lines.append(f"  > 💡 {q['explanation']}")
                        lines.append("")
                    return "\n".join(lines)
                except Exception as e:
                    logger.warning("generate_quiz failed: %s", e)
                    return f"Could not generate quiz: {e}"

            # ── Tool 7: Learning infographic (Gemini image, KB-only context) ──
            @tool
            def generate_learning_visualization(topic: str, document_id: str = "") -> str:
                """Generate one infographic from the student's learning materials (Gemini image).

                **Required workflow when the user names file(s) or wants a visualization of specific uploads:**
                1) list_my_documents (if you need the folder id)
                2) get_processed_markdown(document_id) — **once per file** that is in scope
                3) then call this tool with the same document_id

                Do **not** use text_rag as a substitute for step 2 for named lecture files.
                If document_id is omitted, retrieval snippets are used only for broad/topic-only requests (indexed text).
                topic: what the graphic should emphasize."""
                try:
                    from pathlib import Path

                    from app.api.routes.files_routes import _find_document_entry_for_input_name
                    from app.services.insights_service import InsightsService
                    from app.services.processed_documents_service import build_processed_documents_snapshot

                    raw_doc = (document_id or "").strip()
                    doc: str | None = None
                    if raw_doc:
                        snap_v = build_processed_documents_snapshot(user_id, include_preview=False)
                        entry_v = _find_document_entry_for_input_name(snap_v, raw_doc)
                        if not entry_v:
                            entry_v = _find_document_entry_for_input_name(
                                snap_v, Path(raw_doc.replace("\\", "/")).name
                            )
                        if entry_v:
                            rid = str(entry_v.get("id") or "").strip()
                            doc = sanitize_insights_document_id(rid or None)
                        if doc is None:
                            doc = sanitize_insights_document_id(raw_doc or None)
                    if raw_doc and doc is None:
                        return (
                            "Invalid document_id: use **document_id** from list_my_documents, the pipeline folder id, "
                            "or the upload file name (no path segments or `..`)."
                        )
                    if doc is not None and doc not in viz_markdown_prefetched:
                        return (
                            "Workflow: call get_processed_markdown first for this document, then retry visualization.\n"
                            f"Run: get_processed_markdown(document_id=\"{raw_doc or doc}\") "
                            "(same value you pass here — file name or folder id). "
                            "For multiple files, call get_processed_markdown once per document before this tool."
                        )

                    retrieved: str | None = None
                    if doc is None:
                        with _suppress_pipeline_noise():
                            result = orch.run(
                                query=(topic or "course materials").strip() or "course materials",
                                top_k=14,
                                retriever_type="hybrid",
                                include_images=False,
                                images_for_generation=0,
                                mode="retrieval_only",
                                search_scope="text",
                                generation_model=None,
                                skip_reranker=True,
                            )
                        rows = result.get("text_results") or []
                        compact = _compact_text_rows(rows, limit=14)
                        if not compact or compact == "(no text matches)":
                            return (
                                "No indexed text found for that topic. Try list_my_documents, a different topic, "
                                "or pass document_id after materials are processed and indexed."
                            )
                        retrieved = compact

                    svc = InsightsService(cfg, user_id=user_id)
                    out = svc.lecture_visualization(
                        document_id=doc,
                        topic=topic,
                        retrieved_context=retrieved,
                    )
                    tool_traces.append({
                        "tool": "generate_learning_visualization",
                        "query": topic,
                        "top_k": 0,
                        "search_scope": "text",
                        "index_backend": "processed markdown and/or hybrid text retrieval",
                        "result_count": 1 if (out.get("image_base64") or "").strip() else 0,
                        "result_preview": "Gemini infographic (base64 omitted from trace)",
                    })
                    if out.get("error"):
                        err = str(out["error"])
                        mt = (out.get("model_text") or "").strip()
                        if mt:
                            return f"Visualization error: {err}\n\nModel text (before failure):\n\n{mt[:4000]}"
                        return f"Visualization error: {err}"
                    b64 = (out.get("image_base64") or "").strip()
                    mime = (out.get("mime_type") or "image/png").strip()
                    if not b64:
                        mt = (out.get("model_text") or "").strip()
                        if mt:
                            return (
                                "Model did not return an image. Check GEMINI_API_KEY and GEMINI_IMAGE_MODEL.\n\n"
                                f"Model text:\n\n{mt[:4000]}"
                            )
                        return "Model did not return an image. Check GEMINI_API_KEY and GEMINI_IMAGE_MODEL."
                    topic_short = (topic or "your materials").strip()[:120] or "your materials"
                    model_txt = (out.get("model_text") or "").strip()
                    chat_viz_attachments.append({
                        "mime": mime,
                        "data_base64": b64,
                        "model_text": model_txt[:8000],
                    })
                    cap = model_txt[:2000] + ("…" if len(model_txt) > 2000 else "")
                    return (
                        "VISUALIZATION_OK: An infographic PNG was generated from the student's learning materials "
                        f"(focus: {topic_short}). The chat UI will display it under your reply.\n"
                        "Summarize in a few sentences what the graphic conveys. "
                        "Do not use markdown images, data URLs, or base64 — the client renders the picture separately.\n\n"
                        f"Optional caption from the image model:\n{cap if cap else '(none)'}"
                    )
                except Exception as e:
                    logger.warning("generate_learning_visualization failed: %s", e)
                    return f"Could not generate visualization: {e}"

            # ── Build and run the agent ───────────────────────────────────────
            yield emit({"type": "status", "message": "Running Strands agent..."})

            all_tools = [
                text_rag,
                # image_rag,
                get_quiz_performance,
                list_my_documents,
                get_processed_markdown,
                get_document_summary,
                generate_quiz,
                generate_learning_visualization,
            ]

            system_prompt = (
                "You are BK-MInD, an intelligent educational assistant for a university learning platform.\n"
                "You help students understand lecture content, track progress, and prepare for assessments.\n\n"
                "Rules:\n"
                "- Always call at least one tool unless the message is a simple greeting\n"
                "- Cite evidence from tool results using source references\n"
                "- For performance/progress questions → use get_quiz_performance\n"
                "- For quiz/practice requests → use generate_quiz\n"
                "- For 'what documents do I have' → use list_my_documents\n"
                "- For full lecture text / verbatim grounding → use get_processed_markdown with document_id from list_my_documents or the file name\n"
                "- For document summaries → call list_my_documents first, then get_document_summary\n"
                "- **Infographic / visual summary / mind map (mandatory order when user names file(s) or slide/PDF/lecture):**\n"
                "  1) list_my_documents if you need the pipeline folder id\n"
                "  2) get_processed_markdown(document_id) — **call once per file** that is in scope (confirms Process output exists)\n"
                "  3) only then generate_learning_visualization(topic=..., document_id=...)\n"
                "  Do **not** skip step 2. Do **not** use text_rag instead of get_processed_markdown for this workflow.\n"
                "  If step 2 returns no markdown, tell the user to run **Process** — do not fall back to text_rag for that file.\n"
                "  Multiple files: fetch markdown for **each** document_id first; the visualization tool uses one document_id "
                "per image (call visualization again if the user needs separate graphics per file).\n"
                "- If a tool returns VISUALIZATION_OK, the image is shown automatically in the chat UI — never paste base64 or ![image](data:...) in your answer\n"
                "- If no relevant content found, suggest running Process + Build Index\n"
                "- Format in clean markdown: ## headings, - bullets, **bold** key terms\n"
                "- Never output raw <function_calls> or <function_result> tags\n"
                "- Never include system logs, pipeline statistics, processing metadata, timing data, "
                "or any internal debug information in your response — only present clean educational content"
            )

            profile_instructions: list[str] = []
            if preferred_persona:
                profile_instructions.append(
                    f"Preferred response tone/persona: {preferred_persona[:120]}"
                )
            if education_context:
                profile_instructions.append(
                    f"Student education background/context: {education_context[:800]}"
                )
            if profile_instructions:
                system_prompt = system_prompt + "\n\nUser profile guidance:\n- " + "\n- ".join(profile_instructions)

            agent_query = build_query_with_history(query=query, history_messages=prior_messages)
            logger.info(
                "chat_stream: Built agent query with history (original_query_len=%d, history_count=%d, agent_query_len=%d)",
                len(query),
                len(prior_messages),
                len(agent_query),
            )
            agent_result = await asyncio.to_thread(
                run_chat_agent,
                runtime_mode=CHAT_AGENT_RUNTIME,
                query=agent_query,
                system_prompt=system_prompt,
                tools=all_tools,
                user_id=user_id,
                session_id=session_id,
                memory_id=MEM_ID,
                region=AGENTCORE_REGION,
                runtime_arn=AGENTCORE_RUNTIME_ARN,
            )
            logger.info("chat_stream: Agent returned result, processing...")

            final_text = _strip_data_url_images(
                _strip_raw_tool_markup(str(agent_result.get("answer") or "").strip())
            ) or "No response generated."
            suggestions = [x for x in (agent_result.get("suggestions") or []) if isinstance(x, str) and x.strip()][:3]
            if not suggestions:
                suggestions = list(DEFAULT_SUGGESTIONS)

            for tr in tool_traces:
                yield emit({"type": "tool_trace", "trace": tr})
                await asyncio.sleep(0.01)

            words = final_text.split(" ")
            for i, w in enumerate(words):
                suffix = " " if i < len(words) - 1 else ""
                yield emit({"type": "token", "delta": f"{w}{suffix}"})
                await asyncio.sleep(0.03)

            for va in chat_viz_attachments:
                yield emit({
                    "type": "inline_image",
                    "mime": va.get("mime") or "image/png",
                    "data_base64": va.get("data_base64") or "",
                    "model_text": (va.get("model_text") or "").strip(),
                })
                await asyncio.sleep(0.01)

            if history_svc is not None:
                try:
                    stored_text = _scrub_data_image_markdown_for_history(final_text)
                    persisted_attachments: List[Dict[str, Any]] = []
                    assistant_message_id: str | None = None
                    if chat_viz_attachments:
                        assistant_message_id = allocate_chat_message_id()
                        for idx, va in enumerate(chat_viz_attachments):
                            try:
                                raw = base64.standard_b64decode((va.get("data_base64") or "").strip())
                                mime = (va.get("mime") or "image/png").strip()
                                rel = persist_chat_visualization_png(
                                    user_id,
                                    session_id,
                                    assistant_message_id,
                                    idx,
                                    raw,
                                    mime,
                                )
                                persisted_attachments.append({
                                    "type": "image",
                                    "rel_path": rel,
                                    "mime": mime,
                                    "model_text": (va.get("model_text") or "")[:8000],
                                })
                            except Exception as att_err:
                                logger.warning("Could not persist chat visualization: %s", att_err)
                    logger.info("chat_stream: Saving assistant message to session (len=%d)", len(stored_text))
                    history_svc.put_message(
                        user_id=user_id,
                        session_id=session_id,
                        role="assistant",
                        content=stored_text,
                        traces=tool_traces,
                        suggestions=suggestions,
                        message_id=assistant_message_id,
                        attachments=persisted_attachments if persisted_attachments else None,
                    )
                    logger.info("chat_stream: Assistant message successfully saved to session")
                except Exception as history_err:
                    logger.warning("Failed to persist assistant message: %s", history_err)

            yield emit({"type": "suggestions", "questions": suggestions})
            yield emit({"type": "done"})

        except Exception as e:
            logger.exception("chat stream failed")
            yield emit({"type": "error", "message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
