from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Sequence

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StrandsChatStructuredOutput(BaseModel):
    """Single-call structured output for the main Strands response.

    This keeps follow-up suggestions in the same Strands invocation so the
    API does not run a second LLM call after the final answer.
    """

    answer: str = Field(description="Final markdown response for the student")
    follow_up_questions: list[str] = Field(
        default_factory=list,
        description="Three concise follow-up questions related to the same learning context.",
    )


class QueryRewriteStructuredOutput(BaseModel):
    """Structured output for context-aware retrieval query rewrite."""

    should_rewrite: bool = Field(
        default=False,
        description="Whether the current query depends on conversation context and was rewritten.",
    )
    rewritten_query: str = Field(
        default="",
        description="Standalone retrieval query preserving the student's intent.",
    )
    reason: str = Field(
        default="",
        description="Brief reason for the rewrite decision.",
    )


def _chat_model_id(model_id: str | None = None) -> str:
    return (
        model_id
        or os.getenv("CHAT_AGENT_MODEL")
        or os.getenv("GENERATION_MODEL")
        or os.getenv("BEDROCK_MODEL_ID")
        or ""
    ).strip()


def _build_bedrock_model(region: str, model_id: str | None = None) -> Any:
    model_id = _chat_model_id(model_id)
    if not model_id:
        return None
    try:
        from strands.models.bedrock import BedrockModel

        return BedrockModel(region_name=region, model_id=model_id)
    except Exception as exc:
        logger.warning("Could not build explicit Strands Bedrock model %s: %s", model_id, exc)
        return model_id


def build_query_with_history(query: str, history_messages: Sequence[Dict[str, Any]]) -> str:
    if not history_messages:
        return query

    lines: List[str] = [
        "Conversation memory (most recent turns):",
    ]
    # Keep prompt bounded to avoid token blow-up.
    for msg in history_messages[-8:]:
        role = str(msg.get("role") or "assistant").strip().lower()
        role_label = "Student" if role == "user" else "Assistant"
        content = " ".join(str(msg.get("content") or "").split())
        if len(content) > 420:
            content = content[:420] + "..."
        if content:
            lines.append(f"- {role_label}: {content}")

    lines.append("")
    lines.append(f"Current student request: {query}")
    return "\n".join(lines)


def _compact_history_for_rewrite(history_messages: Sequence[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for msg in history_messages[-8:]:
        role = str(msg.get("role") or "assistant").strip().lower()
        role_label = "Student" if role == "user" else "Assistant"
        content = " ".join(str(msg.get("content") or "").split())
        if len(content) > 360:
            content = content[:360] + "..."
        if content:
            lines.append(f"{role_label}: {content}")
    return "\n".join(lines)


def rewrite_retrieval_query_with_history(
    *,
    query: str,
    history_messages: Sequence[Dict[str, Any]],
    region: str,
    model_id: str | None = None,
    agent_factory: Any | None = None,
) -> Dict[str, Any]:
    """Rewrite a chat follow-up into a standalone retrieval query.

    The helper is intentionally fail-open: retrieval must continue with the
    original query if the rewrite model or structured output is unavailable.
    """

    original = " ".join(str(query or "").split()).strip()
    if not original or not history_messages:
        return {
            "query": original,
            "original_query": original,
            "rewritten_query": original,
            "applied": False,
            "reason": "no conversation history",
        }

    history = _compact_history_for_rewrite(history_messages)
    if not history:
        return {
            "query": original,
            "original_query": original,
            "rewritten_query": original,
            "applied": False,
            "reason": "empty conversation history",
        }

    system_prompt = (
        "You rewrite retrieval queries for a university learning chat assistant.\n"
        "Use the conversation only to resolve references in the current request.\n"
        "Do not answer the question. Do not add facts not present in the conversation.\n"
        "Keep the student's language. If the current request is already standalone, keep it unchanged."
    )
    user_prompt = (
        "Conversation so far:\n"
        f"{history}\n\n"
        f"Current retrieval query: {original}\n\n"
        "Return a standalone retrieval query. Set should_rewrite=true only when the current query "
        "uses context-dependent wording such as pronouns, 'that topic', 'continue', or comparisons "
        "whose entities come from the conversation."
    )

    try:
        if agent_factory is None:
            from strands import Agent

            agent_factory = Agent
        model = _build_bedrock_model(region, model_id)
        agent = agent_factory(model=model, system_prompt=system_prompt)
        result = agent(user_prompt, structured_output_model=QueryRewriteStructuredOutput)
        return _normalize_query_rewrite_result(result, original)
    except Exception as exc:
        logger.warning("Query rewrite failed (%s), using original query", exc)
        return {
            "query": original,
            "original_query": original,
            "rewritten_query": original,
            "applied": False,
            "reason": "rewrite failed",
        }


def run_chat_agent(
    *,
    runtime_mode: str,
    query: str,
    system_prompt: str,
    tools: Sequence[Any],
    user_id: str,
    session_id: str,
    memory_id: str,
    region: str,
    runtime_arn: str | None = None,
    model_id: str | None = None,
) -> Dict[str, Any]:
    mode = (runtime_mode or "local").strip().lower()
    if mode == "agentcore-runtime":
        return _run_agentcore_runtime(
            runtime_arn=runtime_arn,
            query=query,
            session_id=session_id,
            user_id=user_id,
            region=region,
        )
    return _run_local_strands(
        query=query,
        system_prompt=system_prompt,
        tools=tools,
        user_id=user_id,
        session_id=session_id,
        memory_id=memory_id,
        region=region,
        model_id=model_id,
    )


def _run_local_strands(
    *,
    query: str,
    system_prompt: str,
    tools: Sequence[Any],
    user_id: str,
    session_id: str,
    memory_id: str,
    region: str,
    model_id: str | None = None,
) -> Dict[str, Any]:
    from strands import Agent

    has_agentcore_memory = False
    AgentCoreMemoryConfig = None
    AgentCoreMemorySessionManager = None

    # Import lazily so local mode still works when agentcore package is absent.
    try:
        from bedrock_agentcore.memory.integrations.strands.config import (  # type: ignore
            AgentCoreMemoryConfig,
        )
        from bedrock_agentcore.memory.integrations.strands.session_manager import (  # type: ignore
            AgentCoreMemorySessionManager,
        )

        has_agentcore_memory = True
    except Exception:
        has_agentcore_memory = False

    result: Any
    model = _build_bedrock_model(region, model_id)
    if has_agentcore_memory and AgentCoreMemoryConfig and AgentCoreMemorySessionManager:
        mem_cfg = AgentCoreMemoryConfig(
            memory_id=memory_id,
            session_id=session_id,
            actor_id=user_id,
        )
        try:
            with AgentCoreMemorySessionManager(
                agentcore_memory_config=mem_cfg,
                region_name=region,
            ) as session_manager:
                agent = Agent(model=model, system_prompt=system_prompt, tools=list(tools), session_manager=session_manager)
                result = agent(query, structured_output_model=StrandsChatStructuredOutput)
        except Exception as mem_err:
            logger.warning("AgentCore memory failed (%s), falling back to stateless mode", mem_err)
            agent = Agent(model=model, system_prompt=system_prompt, tools=list(tools))
            result = agent(query, structured_output_model=StrandsChatStructuredOutput)
    else:
        agent = Agent(model=model, system_prompt=system_prompt, tools=list(tools))
        result = agent(query, structured_output_model=StrandsChatStructuredOutput)

    return _normalize_agent_result(result)


def _run_agentcore_runtime(
    *,
    runtime_arn: str | None,
    query: str,
    session_id: str,
    user_id: str,
    region: str,
) -> Dict[str, Any]:
    arn = (runtime_arn or os.getenv("AGENTCORE_RUNTIME_ARN") or "").strip()
    if not arn:
        raise RuntimeError("CHAT_AGENT_RUNTIME=agentcore-runtime requires AGENTCORE_RUNTIME_ARN")

    import boto3

    client = boto3.client("bedrock-agentcore", region_name=region)

    payload_bytes = json.dumps(
        {
            "prompt": query,
            "user_id": user_id,
        }
    ).encode("utf-8")

    response = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=session_id,
        payload=payload_bytes,
    )

    raw_payload = response.get("payload")
    raw_bytes: bytes
    if hasattr(raw_payload, "read"):
        raw_bytes = raw_payload.read()  # type: ignore[assignment]
    elif isinstance(raw_payload, (bytes, bytearray)):
        raw_bytes = bytes(raw_payload)
    elif raw_payload is None:
        raw_bytes = b""
    else:
        raw_bytes = str(raw_payload).encode("utf-8")

    raw = raw_bytes.decode("utf-8", errors="ignore")
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"result": raw}
    else:
        data = {}
    answer = str(data.get("result") or data.get("answer") or "").strip()
    suggestions_raw = data.get("follow_up_questions") or data.get("suggestions") or []
    suggestions = _normalize_suggestions(suggestions_raw)
    if not answer:
        answer = "No response generated."
    return {"answer": answer, "suggestions": suggestions}


def _normalize_agent_result(result: Any) -> Dict[str, Any]:
    structured = getattr(result, "structured_output", None)
    if structured is not None:
        answer = str(getattr(structured, "answer", "") or "").strip()
        suggestions = _normalize_suggestions(getattr(structured, "follow_up_questions", []) or [])
        if answer:
            return {
                "answer": answer,
                "suggestions": suggestions,
            }

    # Fallback for older Strands return objects.
    fallback = str(getattr(result, "message", None) or result or "").strip()
    if not fallback:
        fallback = "No response generated."
    return {
        "answer": fallback,
        "suggestions": [],
    }


def _normalize_query_rewrite_result(result: Any, original_query: str) -> Dict[str, Any]:
    original = " ".join(str(original_query or "").split()).strip()
    structured = getattr(result, "structured_output", None)
    if structured is None and isinstance(result, QueryRewriteStructuredOutput):
        structured = result

    should_rewrite = False
    rewritten = ""
    reason = ""
    if structured is not None:
        should_rewrite = bool(getattr(structured, "should_rewrite", False))
        rewritten = " ".join(str(getattr(structured, "rewritten_query", "") or "").split()).strip()
        reason = " ".join(str(getattr(structured, "reason", "") or "").split()).strip()
    elif isinstance(result, dict):
        should_rewrite = bool(result.get("should_rewrite"))
        rewritten = " ".join(str(result.get("rewritten_query") or result.get("query") or "").split()).strip()
        reason = " ".join(str(result.get("reason") or "").split()).strip()

    if not rewritten or len(rewritten) > 600:
        rewritten = original
        should_rewrite = False
        reason = reason or "invalid rewrite output"

    applied = bool(should_rewrite and rewritten.casefold() != original.casefold())
    return {
        "query": rewritten if applied else original,
        "original_query": original,
        "rewritten_query": rewritten,
        "applied": applied,
        "reason": reason or ("rewritten for conversational context" if applied else "query already standalone"),
    }


def _normalize_suggestions(raw: Any) -> list[str]:
    suggestions: list[str] = []
    if isinstance(raw, list):
        for value in raw:
            text = " ".join(str(value or "").split()).strip()
            if text:
                suggestions.append(text[:120])
    # Keep exactly up to 3 for UI consistency.
    return suggestions[:3]
