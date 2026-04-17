from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import os
import re
import uuid
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
from app.services.chat_history_service import ChatHistoryService
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

    cfg = merged_runtime_settings()
    orch = SearchOrchestrator(cfg, user_id=user_id)
    session_id = req.session_id.strip() if req.session_id.strip() else str(uuid.uuid4())
    preferred_persona = (req.persona or "").strip()
    education_context = (req.education_description or "").strip()
    history_svc = _get_chat_history_service()
    prior_messages: list[dict[str, Any]] = []

    if history_svc is not None:
        try:
            history_svc.ensure_session(
                user_id=user_id,
                session_id=session_id,
                title=query,
                pinned=False,
            )
            prior_messages = history_svc.list_recent_messages(
                user_id=user_id,
                session_id=session_id,
                limit=8,
            )
            history_svc.put_message(
                user_id=user_id,
                session_id=session_id,
                role="user",
                content=query,
            )
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
                    from app.services.processed_documents_service import build_processed_documents_snapshot
                    processed = build_processed_documents_snapshot(user_id, include_preview=False)
                    raw_docs = processed.get("documents") or []

                    # Filter out pipeline system artefacts (logs, metadata, stats folders)
                    docs = [
                        d for d in raw_docs
                        if _is_content_document(
                            d.get("folder_name") or "",
                            d.get("display_name") or "",
                        )
                    ]

                    if not docs:
                        from app.core.paths import workspace_paths_for_user
                        from app.repositories import load_documents_snapshot
                        paths = workspace_paths_for_user(user_id)
                        doc_snap = load_documents_snapshot(paths.documents_json_path, user_id=paths.user_id)
                        sources: set[str] = set()
                        for d in doc_snap:
                            src = str(d.get("source") or "")
                            if src:
                                fname = src.replace("\\", "/").split("/")[-1]
                                # Skip log/metadata filenames in the fallback list too
                                if fname and _is_content_document(fname):
                                    sources.add(fname)
                        if not sources:
                            return "No documents found. Upload files and run **Run Pipeline** + **Build Index** in Knowledge Management. Your documents need to be in **Indexed** status to be available for search and insights tools."
                        lines = [f"**Indexed Files** ({len(sources)}):"]
                        for s in sorted(sources)[:20]:
                            lines.append(f"- {s}")
                        return "\n".join(lines)

                    lines = [f"**Available Documents** ({len(docs)}):"]
                    for doc in docs[:20]:
                        name = doc.get("display_name") or doc.get("folder_name") or "unknown"
                        folder = doc.get("folder_name") or ""
                        stage = doc.get("max_stage") or ""
                        entry = f"- **{name}**"
                        if folder:
                            entry += f" | document_id: `{folder}`"
                        if stage:
                            entry += f" | stage: {stage}"
                        lines.append(entry)
                    if len(docs) > 20:
                        lines.append(f"... and {len(docs) - 20} more")
                    return "\n".join(lines)
                except Exception as e:
                    logger.warning("list_my_documents failed: %s", e)
                    return f"Could not list documents: {e}"

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

            # ── Build and run the agent ───────────────────────────────────────
            yield emit({"type": "status", "message": "Running Strands agent..."})

            all_tools = [
                text_rag,
                # image_rag,
                get_quiz_performance,
                list_my_documents,
                get_document_summary,
                generate_quiz,
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
                "- For document summaries → call list_my_documents first, then get_document_summary\n"
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

            final_text = _strip_raw_tool_markup(str(agent_result.get("answer") or "").strip()) or "No response generated."
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

            if history_svc is not None:
                try:
                    history_svc.put_message(
                        user_id=user_id,
                        session_id=session_id,
                        role="assistant",
                        content=final_text,
                        traces=tool_traces,
                        suggestions=suggestions,
                    )
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
