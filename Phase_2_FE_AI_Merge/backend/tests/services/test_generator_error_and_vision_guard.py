from __future__ import annotations

import pytest

from src.generation.generator import GenerationConfig, RAGGenerator


@pytest.mark.unit
def test_generate_error_path_returns_json_safe_contents(monkeypatch: pytest.MonkeyPatch):
    gen = RAGGenerator(
        GenerationConfig(
            provider="bedrock",
            model_name="google.gemma-3-27b-it",
            bedrock_region="us-west-2",
            max_tokens=128,
        )
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("synthetic generation failure")

    monkeypatch.setattr(gen, "_call_llm", _raise)

    docs = [
        {
            "id": "chunk-1",
            "text": "Natural language processing is a branch of AI.",
            "source": "NLP.txt",
            "score": 0.9,
            "retrieval_type": "hybrid_qdrant_bm25",
            "metadata": {},
        }
    ]

    out = gen.generate("what is nlp", docs)

    assert "error" in out
    assert isinstance(out.get("contents"), dict)
    assert "[1.1]" in out["contents"]
    assert all(isinstance(k, str) for k in out["contents"].keys())


@pytest.mark.unit
def test_bedrock_text_only_model_skips_vision_inputs(monkeypatch: pytest.MonkeyPatch):
    gen = RAGGenerator(
        GenerationConfig(
            provider="bedrock",
            model_name="google.gemma-3-27b-it",
            bedrock_region="us-west-2",
            max_tokens=128,
        )
    )

    seen = {"image_paths": None}

    def _fake_call(_prompt, image_paths=None):
        seen["image_paths"] = image_paths
        return "ok"

    monkeypatch.setattr(gen, "_call_llm", _fake_call)

    docs = [
        {
            "id": "chunk-1",
            "text": "Natural language processing is a branch of AI.",
            "source": "NLP.txt",
            "score": 0.9,
            "retrieval_type": "hybrid_qdrant_bm25",
            "metadata": {},
        },
        {
            "id": "img-1",
            "text": "[Image Page 1 from deck]",
            "source": "deck.pdf",
            "source_path": "C:/does-not-matter/deck.pdf",
            "page": 1,
            "score": 0.7,
            "retrieval_type": "colqwen_qdrant",
            "metadata": {},
        },
    ]

    out = gen.generate("summarize", docs)

    assert out.get("answer") == "ok"
    assert seen["image_paths"] is None
