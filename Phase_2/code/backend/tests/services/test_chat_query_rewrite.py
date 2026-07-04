from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.strands_chat_runtime import QueryRewriteStructuredOutput, rewrite_retrieval_query_with_history


@pytest.mark.unit
def test_query_rewrite_skips_when_no_history():
    def _raise_if_called(**_kwargs):
        raise AssertionError("agent should not be constructed without history")

    out = rewrite_retrieval_query_with_history(
        query="What is BM25?",
        history_messages=[],
        region="us-west-2",
        model_id="test-model",
        agent_factory=_raise_if_called,
    )

    assert out["query"] == "What is BM25?"
    assert out["applied"] is False


@pytest.mark.unit
def test_query_rewrite_turns_follow_up_into_standalone_query():
    class FakeAgent:
        def __init__(self, **_kwargs):
            pass

        def __call__(self, _prompt, structured_output_model=None):
            payload = structured_output_model(
                should_rewrite=True,
                rewritten_query="How does BM25 retrieval differ from dense retrieval?",
                reason="resolves pronoun from previous turn",
            )
            return SimpleNamespace(structured_output=payload)

    out = rewrite_retrieval_query_with_history(
        query="How does it differ from dense retrieval?",
        history_messages=[
            {"role": "user", "content": "What is BM25 retrieval?"},
            {"role": "assistant", "content": "BM25 is a sparse lexical retrieval method."},
        ],
        region="us-west-2",
        model_id="test-model",
        agent_factory=FakeAgent,
    )

    assert out["query"] == "How does BM25 retrieval differ from dense retrieval?"
    assert out["applied"] is True
    assert "pronoun" in out["reason"]


@pytest.mark.unit
def test_query_rewrite_keeps_standalone_query():
    class FakeAgent:
        def __init__(self, **_kwargs):
            pass

        def __call__(self, _prompt, structured_output_model=None):
            return SimpleNamespace(
                structured_output=QueryRewriteStructuredOutput(
                    should_rewrite=False,
                    rewritten_query="Explain hybrid retrieval in RAG systems.",
                    reason="query already standalone",
                )
            )

    out = rewrite_retrieval_query_with_history(
        query="Explain hybrid retrieval in RAG systems.",
        history_messages=[{"role": "user", "content": "What is RAG?"}],
        region="us-west-2",
        model_id="test-model",
        agent_factory=FakeAgent,
    )

    assert out["query"] == "Explain hybrid retrieval in RAG systems."
    assert out["applied"] is False


@pytest.mark.unit
def test_query_rewrite_falls_back_on_model_error():
    class FailingAgent:
        def __init__(self, **_kwargs):
            raise RuntimeError("boom")

    out = rewrite_retrieval_query_with_history(
        query="What about that method?",
        history_messages=[{"role": "assistant", "content": "We discussed BM25."}],
        region="us-west-2",
        model_id="test-model",
        agent_factory=FailingAgent,
    )

    assert out["query"] == "What about that method?"
    assert out["applied"] is False
    assert out["reason"] == "rewrite failed"
