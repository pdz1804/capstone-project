"""
utils.py — Shared Utilities for Qdrant Testing Scripts
=======================================================

This module provides helpers used across all test scripts:

1.  setup_logging()   — Configure Python logging with a readable format
2.  Timer             — Measure elapsed time for any code block
3.  LatencyTracker    — Accumulate and summarize multiple timings
4.  load_images()     — Load PIL images from a directory
5.  print_results()   — Pretty-print Qdrant search results
6.  log_tensor_stats()— Log shape/min/max/mean of an embedding tensor
"""

import time
import logging
import functools
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional

from PIL import Image


# ===========================================================
# 1. LOGGING SETUP
# ===========================================================

def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure Python's built-in 'logging' module with a clean format.

    Log levels (most → least verbose):
      DEBUG    Very detailed: tensor shapes, HTTP requests, etc.
      INFO     General progress: "Loaded model", "Stored 10 points"  ← default
      WARNING  Unexpected but non-fatal: "No images found in input/"
      ERROR    Something failed: "Connection refused"
      CRITICAL Fatal error

    Call this once at the top of your script:
        logger = setup_logging()
        logger.info("Script started")
    """
    logging.basicConfig(
        level=level,
        # Format: time | LEVEL    | module_name          | your message
        format="%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s",
        datefmt="%H:%M:%S",
        # 'force=True' re-configures even if basicConfig was already called
        force=True,
    )

    # Suppress noisy logs from HTTP and ML libraries we don't want to see
    for noisy_lib in ["httpx", "httpcore", "transformers", "urllib3", "filelock"]:
        logging.getLogger(noisy_lib).setLevel(logging.WARNING)

    return logging.getLogger(__name__)


# ===========================================================
# 2. TIMER — MEASURE ELAPSED TIME
# ===========================================================

class Timer:
    """
    Precision timer for measuring how long code takes to run.

    ColPali/Qdrant pipeline has multiple steps with very different latencies:
      - Loading model from disk    : 10-60 seconds (first run, downloads weights)
      - Model inference (embedding): 100ms – 5s per image (depends on GPU/CPU)
      - Qdrant upsert              : 10-100ms per batch (network call to cloud)
      - Qdrant search              : 10-50ms (very fast — this is Qdrant's strength!)

    USAGE OPTION 1 — Context manager (recommended):
        with Timer("embedding image") as t:
            embedding = model(image_input)
        # Timer auto-stops here and logs: "[TIMER] embedding image: 342.15 ms"
        print(f"Took {t.elapsed_ms:.1f} ms")

    USAGE OPTION 2 — Decorator:
        @Timer.measure
        def embed_images(images):
            return model(images)

    USAGE OPTION 3 — Manual start/stop:
        t = Timer("my step")
        t.start()
        do_work()
        t.stop()
        print(t.elapsed_ms)
    """

    def __init__(self, label: str = ""):
        self.label = label
        self._start_time: float = 0.0
        self.elapsed_ms: float = 0.0   # Elapsed milliseconds
        self.elapsed_s: float = 0.0    # Elapsed seconds
        self._logger = logging.getLogger("timer")

    def start(self) -> "Timer":
        """Start the timer. Returns self for chaining."""
        # time.perf_counter() is the highest-resolution clock available
        # (more accurate than time.time() for short intervals)
        self._start_time = time.perf_counter()
        return self

    def stop(self) -> "Timer":
        """Stop the timer and compute elapsed time."""
        end_time = time.perf_counter()
        self.elapsed_s = end_time - self._start_time
        self.elapsed_ms = self.elapsed_s * 1000.0
        return self

    def __enter__(self) -> "Timer":
        """Called when entering a 'with Timer() as t:' block."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Called when exiting the 'with' block (even if an exception occurred)."""
        self.stop()
        if self.label:
            self._logger.info(
                f"[TIMER] {self.label:<35} {self.elapsed_ms:>10.2f} ms"
                + (f"  ({self.elapsed_s:.3f} s)" if self.elapsed_s >= 1.0 else "")
            )
        # Return False so exceptions propagate normally
        return False

    @staticmethod
    def measure(func):
        """
        Decorator: automatically times any function and logs the result.

        Usage:
            @Timer.measure
            def my_function(x, y):
                return x + y
            # Calling my_function() will log: "[TIMER] my_function: 12.34 ms"
        """
        @functools.wraps(func)  # Preserves the original function's name/docstring
        def wrapper(*args, **kwargs):
            with Timer(func.__name__):
                return func(*args, **kwargs)
        return wrapper

    def __repr__(self) -> str:
        return f"Timer(label='{self.label}', elapsed={self.elapsed_ms:.2f} ms)"


# ===========================================================
# 3. LATENCY TRACKER — ACCUMULATE MULTIPLE TIMINGS
# ===========================================================

class LatencyTracker:
    """
    Records timing for multiple named pipeline steps, then prints a summary table.

    In a RAG system, latency is critically important.
    This class helps you understand WHERE time is spent:

      Step                           Time (ms)   % Total
      ─────────────────────────────────────────────────
      query_encoding                    287.43    84.3%
      qdrant_network_search              45.12    13.2%
      result_formatting                   8.67     2.5%
      ─────────────────────────────────────────────────
      TOTAL                             341.22   100.0%

    USAGE:
        tracker = LatencyTracker()

        with tracker.measure("model_load"):
            model = load_colqwen()

        with tracker.measure("qdrant_search"):
            results = client.query_points(...)

        tracker.print_summary()
    """

    def __init__(self):
        # Ordered dict preserves insertion order (Python 3.7+)
        self.measurements: Dict[str, float] = {}

    @contextmanager
    def measure(self, label: str):
        """
        Context manager that records elapsed time for 'label'.

        Usage:
            with tracker.measure("my_step"):
                do_something()
        """
        t = Timer()
        t.start()
        try:
            yield t           # Let the 'with' block run
        finally:
            t.stop()
            self.measurements[label] = t.elapsed_ms
            # Also log each step individually at DEBUG level
            logging.getLogger("latency").debug(
                f"[LATENCY] {label}: {t.elapsed_ms:.2f} ms"
            )

    def print_summary(self) -> None:
        """Print a formatted table showing all measured steps."""
        if not self.measurements:
            print("  [LatencyTracker] No measurements recorded.")
            return

        total_ms = sum(self.measurements.values())
        col_w = max(len(k) for k in self.measurements) + 2

        border = "─" * (col_w + 28)
        print("\n" + "=" * (col_w + 28))
        print(f"{'  LATENCY BREAKDOWN':^{col_w + 28}}")
        print("=" * (col_w + 28))
        print(f"  {'Step':<{col_w}} {'Time (ms)':>10}   {'% Total':>7}")
        print("  " + border)
        for label, ms in self.measurements.items():
            pct = (ms / total_ms * 100) if total_ms > 0 else 0.0
            print(f"  {label:<{col_w}} {ms:>10.2f}   {pct:>6.1f}%")
        print("  " + border)
        print(f"  {'TOTAL':<{col_w}} {total_ms:>10.2f}   {'100.0%':>7}")
        print("=" * (col_w + 28) + "\n")

    def get(self, label: str) -> float:
        """Return recorded ms for a label, or 0.0 if not found."""
        return self.measurements.get(label, 0.0)

    def total_ms(self) -> float:
        """Return sum of all recorded times in milliseconds."""
        return sum(self.measurements.values())


# ===========================================================
# 4. IMAGE LOADING
# ===========================================================

def load_images(
    image_dir: Path,
    extensions: tuple = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"),
    max_images: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Scan a directory and load all images as PIL.Image objects.

    Returns a sorted list of dicts, each containing:
        {
            "image"    : PIL.Image (RGB mode),
            "path"     : pathlib.Path to the file,
            "name"     : filename stem (e.g., "slide_01" for "slide_01.png"),
            "filename" : full filename with extension (e.g., "slide_01.png"),
            "index"    : zero-based position in the sorted list,
        }

    WHY RGB?
        ColPali/ColQwen was trained on RGB images.
        Some files may be RGBA (with transparency) or grayscale (L mode).
        .convert("RGB") normalises all of them to 3-channel colour.

    Args:
        image_dir   : Directory to scan
        extensions  : Lowercase file extensions to include
        max_images  : If set, only load the first N images (useful during dev)
    """
    logger = logging.getLogger("image_loader")
    image_dir = Path(image_dir)

    if not image_dir.exists():
        logger.warning(f"Image directory does not exist: {image_dir}")
        return []

    # Collect and sort image paths (case-insensitive extension match)
    all_paths = sorted([
        p for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    ])

    if max_images is not None:
        all_paths = all_paths[:max_images]
        logger.info(f"Limited to first {max_images} images for testing")

    if not all_paths:
        logger.warning(
            f"No images found in '{image_dir}'. "
            f"Add .jpg or .png files and re-run."
        )
        return []

    logger.info(f"Found {len(all_paths)} image(s) in '{image_dir}'")

    results = []
    failed = 0
    for idx, path in enumerate(all_paths):
        try:
            img = Image.open(path).convert("RGB")
            results.append({
                "image":    img,
                "path":     path,
                "name":     path.stem,
                "filename": path.name,
                "index":    idx,
            })
            logger.debug(
                f"  [{idx:03d}] {path.name}  "
                f"({img.size[0]}×{img.size[1]} px, mode={img.mode})"
            )
        except Exception as e:
            logger.error(f"  Failed to load '{path.name}': {e}")
            failed += 1

    logger.info(
        f"Loaded {len(results)}/{len(all_paths)} images"
        + (f"  ({failed} failed)" if failed else "")
    )
    return results


# ===========================================================
# 5. PRETTY-PRINT SEARCH RESULTS
# ===========================================================

def print_results(
    results: List[Any],
    query: str,
    show_payload: bool = True,
) -> None:
    """
    Pretty-print the ScoredPoint objects returned by Qdrant search.

    Each Qdrant ScoredPoint has:
      .id      — the point's unique identifier (integer or UUID)
      .score   — similarity score (higher = more similar)
      .payload — the metadata dict you stored when upserting
      .vector  — the stored vector (None unless you requested it)

    Args:
        results     : List of ScoredPoint from client.query_points()
        query       : The text query (for display only)
        show_payload: Whether to print the metadata attached to each result
    """
    width = 68
    print("\n" + "═" * width)
    print(f"  SEARCH RESULTS  —  query: \"{query}\"")
    print(f"  Returned {len(results)} result(s)")
    print("═" * width)

    if not results:
        print("  (no results — try adjusting score_threshold or top_k)\n")
        print("═" * width + "\n")
        return

    for rank, point in enumerate(results, start=1):
        # Score bar: visual representation of the score (assuming scores 0–1 range)
        bar_len = max(1, min(30, int(point.score * 30)))
        bar = "█" * bar_len + "░" * (30 - bar_len)

        print(f"\n  #{rank}  ID={point.id}  Score={point.score:.6f}")
        print(f"       [{bar}]")

        if show_payload and point.payload:
            print(f"       Metadata:")
            for key, val in point.payload.items():
                print(f"         {key:<20}: {val}")

    print("\n" + "═" * width + "\n")


# ===========================================================
# 6. EMBEDDING TENSOR DIAGNOSTICS
# ===========================================================

def log_tensor_stats(tensor: Any, label: str = "tensor") -> None:
    """
    Log key statistics about a PyTorch tensor — very useful for debugging embeddings.

    For a ColQwen image embedding of shape [num_patches, 128]:
      - shape  : tells you how many patches the image produced
      - dtype  : should be torch.bfloat16 or torch.float32
      - min/max: should be in roughly [-1, 1] range (model normalises outputs)
      - norm   : average L2 norm per patch (should be ~1.0 for normalised vectors)

    Args:
        tensor: A torch.Tensor
        label : A descriptive name shown in the log message
    """
    import torch

    if tensor is None:
        logging.getLogger("stats").warning(f"[STATS] {label}: tensor is None")
        return

    if not isinstance(tensor, torch.Tensor):
        logging.getLogger("stats").warning(
            f"[STATS] {label}: expected torch.Tensor, got {type(tensor)}"
        )
        return

    # Compute on CPU to avoid device issues
    t = tensor.float().cpu()

    logging.getLogger("stats").info(
        f"[STATS] {label}:\n"
        f"         shape  = {list(t.shape)}\n"
        f"         dtype  = {tensor.dtype}\n"
        f"         device = {tensor.device}\n"
        f"         min    = {t.min().item():.4f}\n"
        f"         max    = {t.max().item():.4f}\n"
        f"         mean   = {t.mean().item():.4f}\n"
        f"         L2norm = {t.norm(dim=-1).mean().item():.4f}  "
        "(should be ~1.0 for normalised vectors)"
    )
