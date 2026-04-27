"""
Read job rows from DynamoDB (bk_mind_app_jobs) and print duration metrics.

Prereq: pip install boto3, AWS creds (env, profile, or IAM), AWS_REGION set.

Env:
  DYNAMODB_JOBS_TABLE  (default: bk_mind_app_jobs)
  AWS_REGION

Usage:
  # By explicit job ids (one UUID per line in file)
  python dynamo_job_metrics.py --ids-file job_ids.txt

  # By time window: scan and filter by created_at (epoch string in item)
  python dynamo_job_metrics.py --since-epoch 1777077000

  # From stdin (one job_id per line)
  type ids.txt | python dynamo_job_metrics.py --stdin

  # Auto timestamped CSV under docs/jmeter-capacity-tests/runs/
  python dynamo_job_metrics.py --ids-file job_ids.txt --out-csv-auto 06
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

# Match standard UUID; avoids BOM / stray chars / wrong hyphens in clipboard lines.
_UUID_LINE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def _normalize_job_id_line(raw: str) -> str:
    s = (raw or "").replace("\ufeff", "").strip()
    m = _UUID_LINE.search(s)
    return m.group(0) if m else s.split("#", 1)[0].strip()


def _s(item: Dict[str, Any], key: str) -> str:
    v = item.get(key)
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict) and "S" in v:
        return str(v.get("S") or "").strip()
    return str(v).strip()


def _parse_epoch(s: str) -> Optional[int]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _duration_sec(item: Dict[str, Any]) -> Optional[float]:
    c = _parse_epoch(_s(item, "created_at"))
    s = _parse_epoch(_s(item, "started_at"))
    e = _parse_epoch(_s(item, "completed_at"))
    if e is None:
        return None
    start = s if s is not None and s > 0 else c
    if start is None:
        return None
    return float(e - start)


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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--table", default=os.getenv("DYNAMODB_JOBS_TABLE", "bk_mind_app_jobs"))
    p.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    p.add_argument("--ids-file", help="File with one job_id (UUID) per line")
    p.add_argument("--stdin", action="store_true", help="Read job_ids from stdin")
    p.add_argument("--since-epoch", type=int, help="Scan table; include rows with created_at >= this (string compare ok for same-width epoch)")
    p.add_argument("--max-scan", type=int, default=2000, help="Max items to scan when using --since-epoch")
    p.add_argument(
        "--out-csv",
        help="Write all rows + summary to this CSV (UTF-8). Parent dirs are created if needed.",
    )
    p.add_argument(
        "--out-csv-auto",
        metavar="PREFIX",
        help="Write CSV under docs/jmeter-capacity-tests/runs/ with name PREFIX_YYYYMMDD_HHMMSS_dynamo_metrics.csv (local time).",
    )
    p.add_argument(
        "--script-dir",
        default=os.path.dirname(os.path.abspath(__file__)),
        help=argparse.SUPPRESS,
    )
    args = p.parse_args()

    try:
        import boto3
    except ImportError:
        print("Install boto3: python -m pip install boto3", file=sys.stderr)
        return 1

    ddb = boto3.client("dynamodb", region_name=args.region)
    table = args.table
    job_ids: List[str] = []
    requested_ids: Set[str] = set()

    if args.ids_file:
        with open(args.ids_file, "r", encoding="utf-8-sig") as f:
            job_ids = [
                _normalize_job_id_line(ln)
                for ln in f
                if (ln2 := (ln or "").lstrip("\ufeff").strip()) and not ln2.startswith("#")
            ]
        job_ids = [j for j in job_ids if j]

    if args.stdin and not job_ids:
        job_ids = [
            _normalize_job_id_line(ln)
            for ln in sys.stdin
            if (ln2 := (ln or "").lstrip("\ufeff").strip()) and not ln2.startswith("#")
        ]
        job_ids = [j for j in job_ids if j]

    requested_ids = set(job_ids)

    items: List[Dict[str, Any]] = []
    missing_ids: List[str] = []

    def _get_item_try_variants(jid: str) -> Optional[Dict[str, Any]]:
        """Dynamo string keys are case-sensitive; try a few normalizations."""
        seen: Set[str] = set()
        for candidate in (jid, jid.lower(), jid.upper()):
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            r = ddb.get_item(
                TableName=table,
                Key={"job_id": {"S": candidate}},
                ConsistentRead=True,
            )
            it = r.get("Item")
            if it:
                return it
        return None

    if job_ids:
        for jid in job_ids:
            it = _get_item_try_variants(jid)
            if it:
                items.append(it)
            else:
                missing_ids.append(jid)
                print(
                    f"MISSING\t{jid}\t(repr={jid!r} len={len(jid)})",
                    file=sys.stderr,
                )
    elif args.since_epoch is not None:
        since_s = str(int(args.since_epoch))
        scanned = 0
        lek: Optional[Dict[str, Any]] = None
        while scanned < args.max_scan:
            kw: Dict[str, Any] = {"TableName": table, "Limit": min(100, args.max_scan - scanned)}
            if lek:
                kw["ExclusiveStartKey"] = lek
            resp = ddb.scan(**kw)
            for it in resp.get("Items") or []:
                ca = _s(it, "created_at")
                if ca and ca >= since_s:
                    items.append(it)
            scanned += len(resp.get("Items") or [])
            lek = resp.get("LastEvaluatedKey")
            if not lek:
                break
    else:
        print("Provide --ids-file, --stdin, or --since-epoch", file=sys.stderr)
        return 2

    rows: List[Dict[str, Any]] = []
    durs: List[float] = []
    for it in items:
        jid = _s(it, "job_id")
        jt = _s(it, "job_type")
        st = _s(it, "status")
        du = _duration_sec(it)
        if du is not None:
            durs.append(du)
        rows.append(
            {
                "job_id": jid,
                "job_type": jt,
                "status": st,
                "created_at": _s(it, "created_at"),
                "started_at": _s(it, "started_at"),
                "completed_at": _s(it, "completed_at"),
                "duration_sec": du,
                "dynamo_presence": "ok",
            }
        )
    for mid in missing_ids:
        rows.append(
            {
                "job_id": mid,
                "job_type": "",
                "status": "MISSING_IN_DYNAMO",
                "created_at": "",
                "started_at": "",
                "completed_at": "",
                "duration_sec": None,
                "dynamo_presence": "missing",
            }
        )

    durs.sort()
    avg = sum(durs) / len(durs) if durs else 0.0
    p95 = _pctl(durs, 0.95) if durs else 0.0
    p99 = _pctl(durs, 0.99) if durs else 0.0

    print(
        "job_id\tjob_type\tstatus\tcreated_at\tstarted_at\tcompleted_at\tduration_sec\tdynamo_presence"
    )
    for r in rows:
        print(
            f"{r['job_id']}\t{r['job_type']}\t{r['status']}\t"
            f"{r['created_at']}\t{r['started_at']}\t{r['completed_at']}\t"
            f"{r['duration_sec'] if r['duration_sec'] is not None else ''}\t"
            f"{r.get('dynamo_presence', 'ok')}"
        )
    print("---", file=sys.stderr)
    n_req = len(requested_ids) if requested_ids else len(rows)
    n_miss = len(missing_ids)
    print(
        f"n_ok={len(durs)}  n_missing_dynamo={n_miss}  n_requested={n_req}  "
        f"avg_sec={round(avg,3)}  p95_sec={p95}  p99_sec={p99}  "
        f"(duration = completed - started, else completed - created)",
        file=sys.stderr,
    )

    out_csv: Optional[str] = args.out_csv
    if args.out_csv_auto:
        runs = os.path.normpath(
            os.path.join(args.script_dir, "..", "runs")
        )
        os.makedirs(runs, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_csv = os.path.join(
            runs, f"{args.out_csv_auto}_{ts}_dynamo_metrics.csv"
        )

    if out_csv:
        fieldnames = [
            "job_id",
            "job_type",
            "status",
            "created_at",
            "started_at",
            "completed_at",
            "duration_sec",
            "dynamo_presence",
        ]
        os.makedirs(os.path.dirname(os.path.abspath(out_csv)) or ".", exist_ok=True)
        with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                row = {k: r.get(k) for k in fieldnames}
                if row.get("duration_sec") is not None:
                    row["duration_sec"] = str(row["duration_sec"])
                w.writerow(row)
            w.writerow(
                {
                    "job_id": "SUMMARY",
                    "job_type": table,
                    "status": f"n_ok={len(durs)} n_missing={n_miss} n_requested={n_req}",
                    "created_at": "",
                    "started_at": "",
                    "completed_at": "",
                    "duration_sec": f"avg={round(avg,3)} p95={p95} p99={p99}",
                    "dynamo_presence": args.region,
                }
            )
        print(f"Wrote CSV: {out_csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
