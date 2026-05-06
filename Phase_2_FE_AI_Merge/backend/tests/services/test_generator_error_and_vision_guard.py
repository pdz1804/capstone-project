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
def test_bedrock_text_only_model_falls_back_for_vision_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    gen = RAGGenerator(
        GenerationConfig(
            provider="bedrock",
            model_name="google.gemma-3-27b-it",
            bedrock_region="us-west-2",
            max_tokens=128,
        )
    )

    seen = {"image_paths": None, "model": None}

    def _fake_call(_prompt, image_paths=None):
        seen["image_paths"] = image_paths
        seen["model"] = gen.config.model_name
        return "ok"

    monkeypatch.setattr(gen, "_call_llm", _fake_call)
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"fake-image-bytes")

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
            "source_path": str(image_path),
            "page": 1,
            "score": 0.7,
            "retrieval_type": "colqwen_qdrant",
            "metadata": {},
        },
    ]

    out = gen.generate("summarize", docs)

    assert out.get("answer") == "ok"
    assert seen["model"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert seen["image_paths"] == [str(image_path)]
