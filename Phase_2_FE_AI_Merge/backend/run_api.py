"""Run backend API from backend/.

Examples:
- Dev hot-reload (single worker): python run_api.py
- Multi-worker test (no reload): python run_api.py --workers 4 --no-reload
"""

from __future__ import annotations

import argparse
import os

import uvicorn


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FastAPI backend")
    parser.add_argument("--host", default=os.getenv("RUN_API_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("RUN_API_PORT", "5001")))
    parser.add_argument("--workers", type=int, default=int(os.getenv("RUN_API_WORKERS", "1")))
    parser.add_argument(
        "--reload",
        action="store_true",
        default=_env_bool("RUN_API_RELOAD", True),
        help="Enable auto-reload (single worker only)",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (required for workers > 1)",
    )

    args = parser.parse_args()
    workers = max(1, int(args.workers))
    reload_enabled = bool(args.reload) and not bool(args.no_reload)

    if reload_enabled and workers > 1:
        print("run_api.py: --reload cannot be used with --workers > 1; disabling reload.")
        reload_enabled = False

    kwargs = {
        "app": "app.main:app",
        "host": args.host,
        "port": args.port,
    }
    if reload_enabled:
        kwargs["reload"] = True
        kwargs["reload_dirs"] = ["app", "src", "config"]
    else:
        kwargs["workers"] = workers

    uvicorn.run(**kwargs)
