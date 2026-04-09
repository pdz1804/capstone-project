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
                agent = Agent(system_prompt=system_prompt, tools=list(tools), session_manager=session_manager)
                result = agent(query, structured_output_model=StrandsChatStructuredOutput)
        except Exception as mem_err:
            logger.warning("AgentCore memory failed (%s), falling back to stateless mode", mem_err)
            agent = Agent(system_prompt=system_prompt, tools=list(tools))
            result = agent(query, structured_output_model=StrandsChatStructuredOutput)
    else:
        agent = Agent(system_prompt=system_prompt, tools=list(tools))
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


def _normalize_suggestions(raw: Any) -> list[str]:
    suggestions: list[str] = []
    if isinstance(raw, list):
        for value in raw:
            text = " ".join(str(value or "").split()).strip()
            if text:
                suggestions.append(text[:120])
    # Keep exactly up to 3 for UI consistency.
    return suggestions[:3]
