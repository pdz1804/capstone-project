from __future__ import annotations

from app.services.search_orchestrator import SearchOrchestrator


class _FakeCacheClient:
    def __init__(self):
        self._store = {}
        self.config = type("cfg", (), {"ttl_seconds": 600})()

    def is_enabled(self) -> bool:
        return True

    def _key(self, user_id, request_payload, namespace="search"):
        return (namespace, user_id, str(sorted((request_payload or {}).items())))

    def get(self, user_id, request_payload, namespace="search"):
        return self._store.get(self._key(user_id, request_payload, namespace))

    def set(self, user_id, request_payload, result_payload, namespace="search"):
        self._store[self._key(user_id, request_payload, namespace)] = result_payload
        return True


class _Counter:
    def __init__(self):
        self.calls = 0

    def __call__(self, *_args, **_kwargs):
        self.calls += 1
        return [{"id": "chunk-1", "text": "cached chunk"}]


def _minimal_cfg():
    return {
        "pipeline": {"rag_mode": "text"},
        "generation": {"enabled": False},
        "image_retrieval": {"enabled": False},
    }


# pytest discovers via function name; explicit marker not required for this repository setup.
def test_orchestrator_reuses_retrieval_cache_across_instances(monkeypatch):
    fake_cache = _FakeCacheClient()
    search_counter = _Counter()

    monkeypatch.setattr("app.services.search_orchestrator.get_search_cache_client", lambda: fake_cache)
    monkeypatch.setattr("app.services.search_orchestrator.TextSearchService.search", search_counter)

    orch_a = SearchOrchestrator(_minimal_cfg(), user_id="u1")
    first = orch_a.run(
        query="what is rag",
        top_k=5,
        retriever_type="hybrid",
        include_images=False,
        mode="retrieval_only",
        search_scope="text",
        skip_reranker=True,
    )

    orch_b = SearchOrchestrator(_minimal_cfg(), user_id="u1")
    second = orch_b.run(
        query="what is rag",
        top_k=5,
        retriever_type="hybrid",
        include_images=False,
        mode="retrieval_only",
        search_scope="text",
        skip_reranker=True,
    )

    assert search_counter.calls == 1
    assert first["text_results"] == second["text_results"]
    assert first["telemetry"]["cache"]["retrieval"]["hit"] is False
    assert second["telemetry"]["cache"]["retrieval"]["hit"] is True


def test_orchestrator_retrieval_cache_isolated_per_user(monkeypatch):
    fake_cache = _FakeCacheClient()
    search_counter = _Counter()

    monkeypatch.setattr("app.services.search_orchestrator.get_search_cache_client", lambda: fake_cache)
    monkeypatch.setattr("app.services.search_orchestrator.TextSearchService.search", search_counter)

    orch_u1 = SearchOrchestrator(_minimal_cfg(), user_id="u1")
    orch_u1.run(
        query="same query",
        top_k=5,
        retriever_type="hybrid",
        include_images=False,
        mode="retrieval_only",
        search_scope="text",
        skip_reranker=True,
    )

    orch_u2 = SearchOrchestrator(_minimal_cfg(), user_id="u2")
    orch_u2.run(
        query="same query",
        top_k=5,
        retriever_type="hybrid",
        include_images=False,
        mode="retrieval_only",
        search_scope="text",
        skip_reranker=True,
    )

    assert search_counter.calls == 2
