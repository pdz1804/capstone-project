"""
Summarize a JMeter CSV .jtl into a metrics table (per label + totals).

Useful for search (and any API) when you need latency columns without opening HTML reports.

Typical JTL header:
  timeStamp,elapsed,label,responseCode,...
  Optional: URL, Latency, IdleTime, Connect

*elapsed* = full response time (ms). *Latency* = time to first byte (ms), if present.

Usage:
  python jtl_metrics_csv.py results/08_search_20t_20260425_163758.jtl
  python jtl_metrics_csv.py run.jtl -o metrics.csv
  python jtl_metrics_csv.py run.jtl --out-csv-auto 08
  python jtl_metrics_csv.py run.jtl --search-only
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, DefaultDict, Dict, List, Optional


def _pctl(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    i = int((p * n + 0.999) // 1) - 1
    if i < 0:
        i = 0
    if i >= n:
        i = n - 1
    return round(sorted_vals[i], 3)


def _f(x: Any) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _is_success(row: Dict[str, str]) -> bool:
    s = (row.get("success") or "").strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    code = (row.get("responseCode") or "").strip()
    if code and code != "200" and code != "0":
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("jtl", help="JMeter JTL (CSV) file")
    p.add_argument(
        "-o",
        "--out",
        help="Write UTF-8 CSV (with BOM) for Excel. Default: print table to stdout.",
    )
    p.add_argument(
        "--out-csv-auto",
        metavar="PREFIX",
        help="Write under docs/jmeter-capacity-tests/runs/ as PREFIX_YYYYMMDD_HHMMSS_jtl_metrics.csv",
    )
    p.add_argument(
        "--search-only",
        action="store_true",
        help="Only rows whose label or URL contains /api/search (excludes auth noise).",
    )
    p.add_argument(
        "--label-regex",
        metavar="REGEX",
        help="If set, only include samples whose `label` matches this regex (case-insensitive).",
    )
    p.add_argument(
        "--script-dir",
        default=os.path.dirname(os.path.abspath(__file__)),
        help=argparse.SUPPRESS,
    )
    args = p.parse_args()

    lab_re: Optional[re.Pattern[str]] = None
    if args.label_regex:
        lab_re = re.compile(args.label_regex, re.I)

    by_label: DefaultDict[str, List[Dict[str, float]]] = defaultdict(list)

    with open(args.jtl, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            if not row:
                continue
            label = (row.get("label") or "").strip() or "<empty>"
            url = (row.get("URL") or row.get("url") or "") or ""

            if args.search_only and "/api/search" not in label and "/api/search" not in url:
                continue
            if lab_re and not lab_re.search(label):
                continue

            el = _f(row.get("elapsed"))
            if el is None:
                el = _f(row.get("time"))
            if el is None:
                continue
            lat = _f(row.get("Latency") or row.get("latency"))
            ok = _is_success(row)
            by_label[label].append({"elapsed_ms": el, "latency_ms": lat, "ok": 1.0 if ok else 0.0})

    if not by_label:
        print("No samples matched.", file=sys.stderr)
        return 1

    out_rows: List[Dict[str, Any]] = []
    file_has_lat = any(
        s.get("latency_ms") is not None
        for samples in by_label.values()
        for s in samples
    )

    def summarize(samples: List[Dict[str, float]], name: str) -> Dict[str, Any]:
        n = len(samples)
        n_err = int(sum(1 for s in samples if s["ok"] < 0.5))
        d_el = sorted(s["elapsed_ms"] for s in samples)
        row: Dict[str, Any] = {
            "label": name,
            "samples": n,
            "errors": n_err,
            "error_pct": round(100.0 * n_err / n, 2) if n else 0.0,
            "elapsed_ms_min": int(min(d_el)),
            "elapsed_ms_max": int(max(d_el)),
            "elapsed_ms_mean": round(sum(d_el) / n, 1),
            "elapsed_ms_p50": _pctl(d_el, 0.5),
            "elapsed_ms_p90": _pctl(d_el, 0.9),
            "elapsed_ms_p95": _pctl(d_el, 0.95),
            "elapsed_ms_p99": _pctl(d_el, 0.99),
        }
        if file_has_lat and any(s.get("latency_ms") is not None for s in samples):
            d_la = sorted(
                int(s["latency_ms"])
                for s in samples
                if s.get("latency_ms") is not None
            )
            if d_la:
                row["latency_ms_min"] = min(d_la)
                row["latency_ms_max"] = max(d_la)
                row["latency_ms_mean"] = round(sum(d_la) / len(d_la), 1)
                row["latency_ms_p50"] = _pctl([float(x) for x in d_la], 0.5)
                row["latency_ms_p90"] = _pctl([float(x) for x in d_la], 0.9)
                row["latency_ms_p95"] = _pctl([float(x) for x in d_la], 0.95)
                row["latency_ms_p99"] = _pctl([float(x) for x in d_la], 0.99)
        return row

    for label in sorted(by_label.keys(), key=str.lower):
        out_rows.append(summarize(by_label[label], label))

    if len(out_rows) > 1 or not args.search_only:
        all_s = [s for samples in by_label.values() for s in samples]
        out_rows.append(summarize(all_s, "TOTAL_ALL_LABELS"))

    base_fn: List[str] = [
        "label",
        "samples",
        "errors",
        "error_pct",
        "elapsed_ms_min",
        "elapsed_ms_max",
        "elapsed_ms_mean",
        "elapsed_ms_p50",
        "elapsed_ms_p90",
        "elapsed_ms_p95",
        "elapsed_ms_p99",
    ]
    lat_fn: List[str] = [
        "latency_ms_min",
        "latency_ms_max",
        "latency_ms_mean",
        "latency_ms_p50",
        "latency_ms_p90",
        "latency_ms_p95",
        "latency_ms_p99",
    ]
    include_lat = file_has_lat and any("latency_ms_mean" in r for r in out_rows)
    fieldnames: List[str] = base_fn + (lat_fn if include_lat else [])

    # Flatten: ensure all fieldnames in each row
    for row in out_rows:
        for fn in fieldnames:
            if fn not in row:
                row[fn] = ""

    out_csv: Optional[str] = args.out
    if args.out_csv_auto:
        runs = os.path.normpath(os.path.join(args.script_dir, "..", "runs"))
        os.makedirs(runs, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_csv = os.path.join(runs, f"{args.out_csv_auto}_{ts}_jtl_metrics.csv")

    def _write(stream: Any) -> None:
        w = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    if out_csv:
        with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
            _write(f)
        print(f"Wrote {out_csv}", file=sys.stderr)
    else:
        _write(sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
