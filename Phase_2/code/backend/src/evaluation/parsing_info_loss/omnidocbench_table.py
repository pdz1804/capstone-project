"""Adapter for OmniDocBench official table metrics."""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
from typing import Optional, Tuple


_TEDS_INSTANCE = None


def _repo_root() -> Path:
    # backend/src/evaluation/parsing_info_loss -> repo root
    return Path(__file__).resolve().parents[4]


def _ensure_omnidocbench_path() -> None:
    omni_root = _repo_root() / "third_party" / "OmniDocBench"
    if omni_root.exists() and str(omni_root) not in sys.path:
        sys.path.insert(0, str(omni_root))


def official_teds_available() -> bool:
    try:
        get_official_teds()
        return True
    except Exception:
        return False


def get_official_teds():
    """Return the official OmniDocBench TEDS evaluator instance.

    This imports `metrics.table_metric.TEDS` from the cloned OmniDocBench repo.
    The dependency set is intentionally the same as OmniDocBench's implementation:
    `apted`, `Levenshtein`, and `lxml`.
    """

    global _TEDS_INSTANCE
    if _TEDS_INSTANCE is not None:
        return _TEDS_INSTANCE
    table_metric_path = _repo_root() / "third_party" / "OmniDocBench" / "metrics" / "table_metric.py"
    if not table_metric_path.exists():
        raise FileNotFoundError(f"OmniDocBench table_metric.py not found: {table_metric_path}")
    spec = importlib.util.spec_from_file_location("omnidocbench_table_metric", table_metric_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load OmniDocBench table metric from {table_metric_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    TEDS = module.TEDS

    _TEDS_INSTANCE = TEDS(structure_only=False)
    return _TEDS_INSTANCE


def _wrap_table_html(html: str) -> str:
    stripped = (html or "").strip()
    if not stripped:
        return ""
    lowered = stripped.lower()
    if "<html" in lowered or "<body" in lowered:
        return stripped
    return f"<html><body>{stripped}</body></html>"


def official_table_scores(pred_html: str, gt_html: str) -> Tuple[Optional[float], str]:
    """Compute official OmniDocBench TEDS, returning `(score, error)`."""

    try:
        score = float(get_official_teds().evaluate(_wrap_table_html(pred_html), _wrap_table_html(gt_html)))
        return score, ""
    except Exception as exc:
        return None, str(exc)
