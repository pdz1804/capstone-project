"""Classify Qdrant client failures for clearer API responses."""

from __future__ import annotations

from typing import Any, Dict


def _exception_chain(exc: BaseException):
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        yield cur
        nxt = cur.__cause__ or cur.__context__
        cur = nxt if nxt is not cur else None


def is_qdrant_unreachable(exc: BaseException) -> bool:
    """True when Qdrant HTTP client cannot open a TCP connection."""
    for e in _exception_chain(exc):
        name = type(e).__name__
        if name in ("ConnectError", "ConnectTimeout", "ReadTimeout", "ResponseHandlingException"):
            return True
        s = str(e).lower()
        if any(
            t in s
            for t in (
                "10061",
                "actively refused",
                "connection refused",
                "cannot assign requested address",
                "failed to establish",
                "name or service not known",
                "no route to host",
                "nodename nor servname",
                "network is unreachable",
                "temporary failure in name resolution",
            )
        ):
            return True
    return False


def qdrant_setup_hint(cfg: Dict[str, Any]) -> str:
    q = cfg.get("qdrant", {}) or {}
    mode = (q.get("mode") or "docker").lower()
    if mode == "cloud":
        url = q.get("url") or "(set QDRANT_URL)"
        return f"Qdrant Cloud URL: {url}. Verify QDRANT_API_KEY and outbound HTTPS."
    host = q.get("host", "localhost")
    port = q.get("port", 6333)
    docker_hint = ""
    if str(host).strip().lower() in ("localhost", "127.0.0.1", "::1"):
        docker_hint = (
            " If the API is running inside Docker, `localhost` points to the container itself; "
            "use `host.docker.internal` or your Qdrant service/container name instead."
        )
    return (
        f"Expecting Qdrant at {host}:{port}. Start it locally, e.g. "
        "`docker run -p 6333:6333 qdrant/qdrant`, or set QDRANT_MODE=cloud and QDRANT_URL."
        f"{docker_hint}"
    )
