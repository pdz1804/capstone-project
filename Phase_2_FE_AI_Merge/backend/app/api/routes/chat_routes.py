from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import storage_user_id
from app.api.schemas import ChatStreamRequest
from app.core.paths import merged_runtime_settings
from app.services.search_orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


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
    """
    Remove raw tool XML-like blocks that some model outputs include, because
    tool calls/results are rendered as dedicated UI trace cards.
    """
    if not text:
        return ""
    cleaned = re.sub(r"<function_calls>.*?</function_calls>\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<function_result>.*?</function_result>\s*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


@router.post("/chat/stream")
async def chat_stream(req: ChatStreamRequest, user_id: str = Depends(storage_user_id)):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    cfg = merged_runtime_settings()
    orch = SearchOrchestrator(cfg, user_id=user_id)

    async def event_stream():
        def emit(payload: Dict[str, Any]) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        yield emit({"type": "status", "message": "Planning tool calls..."})
        try:
            tool_traces: List[Dict[str, Any]] = []

            # Inline tools exposed to Strands agent.
            from strands import Agent, tool

            @tool
            def text_rag(query: str, top_k: int = req.top_k) -> str:
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
                tool_traces.append(
                    {
                        "tool": "text_rag",
                        "query": query,
                        "top_k": max(1, min(int(top_k), 30)),
                        "search_scope": "text",
                        "index_backend": "BM25 + Qdrant text collection",
                        "result_count": len(rows),
                        "result_preview": compact,
                    }
                )
                return compact

            # NOTE: image_rag is intentionally disabled for now to keep responses fast.
            # @tool
            # def image_rag(query: str, top_k: int = req.top_k) -> str:
            #     result = orch.run(
            #         query=query,
            #         top_k=max(1, min(int(top_k), 30)),
            #         retriever_type="hybrid",
            #         include_images=True,
            #         images_for_generation=0,
            #         mode="retrieval_only",
            #         search_scope="image",
            #         generation_model=None,
            #         skip_reranker=True,
            #     )
            #     rows = result.get("image_results") or []
            #     compact = _compact_image_rows(rows)
            #     tool_traces.append(
            #         {
            #             "tool": "image_rag",
            #             "query": query,
            #             "top_k": max(1, min(int(top_k), 30)),
            #             "search_scope": "image",
            #             "index_backend": "ColQwen + Qdrant image collection",
            #             "result_count": len(rows),
            #             "result_preview": compact,
            #         }
            #     )
            #     return compact

            yield emit({"type": "status", "message": "Running Strands agent..."})

            system_prompt = (
                "You are BK-MInD chat agent. Decompose user queries and call tools as needed:\n"
                "1) text_rag(query, top_k) for textual document evidence\n"
                "(image_rag is currently disabled for speed)\n\n"
                "Rules:\n"
                "- Prefer calling at least one tool before answering.\n"
                "- Use text_rag as the primary retrieval tool.\n"
                "- Cite concise evidence snippets in your answer.\n"
                "- If no evidence is found, say so and suggest next steps (Process/Index).\n"
                "- Keep responses structured and concise.\n"
                "- ALWAYS return valid markdown with clear sections, bullet lists, and bold key terms.\n"
                "- Use headings (##), bullets, and short paragraphs. Avoid wall-of-text plain output.\n"
                "- Never output raw <function_calls> or <function_result> tags in final answer."
            )
            agent = Agent(system_prompt=system_prompt, tools=[text_rag])
            out = await asyncio.to_thread(agent, query)
            final_text = _strip_raw_tool_markup(str(out or "").strip()) or "No response generated."

            # Emit tool traces so UI can render call/result blocks.
            for tr in tool_traces:
                yield emit({"type": "tool_trace", "trace": tr})
                await asyncio.sleep(0.01)

            # Stream answer word-by-word (slower, smoother UX).
            words = final_text.split(" ")
            for i, w in enumerate(words):
                suffix = " " if i < len(words) - 1 else ""
                yield emit({"type": "token", "delta": f"{w}{suffix}"})
                await asyncio.sleep(0.03)

            yield emit({"type": "done"})
        except Exception as e:
            logger.exception("chat stream failed")
            yield emit({"type": "error", "message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

