"""
Extract unique job_id UUIDs from a JMeter CSV .jtl for index/process 1-loop plans.

Those plans poll GET /api/index/status/{job_id}; the id appears in the URL/label, not
in response data (JTL does not store bodies by default).

Usage:
  python jtl_extract_job_ids.py path/to/run.jtl
  python jtl_extract_job_ids.py run.jtl -o ../job_ids_05_process.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import List

_RE = re.compile(
    r"/api/index/status/"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


def extract_ordered_unique(text: str) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for m in _RE.finditer(text):
        u = m.group(1)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("jtl", help="Path to JTL (CSV format)")
    p.add_argument(
        "-o",
        "--out",
        help="Write ids one per line (UTF-8). Default: print to stdout.",
    )
    args = p.parse_args()
    with open(args.jtl, "r", encoding="utf-8-sig", errors="replace") as f:
        text = f.read()
    ids = extract_ordered_unique(text)
    if not ids:
        print("No job ids found (expected /api/index/status/... in URL or label).", file=sys.stderr)
        return 1
    body = "\n".join(ids) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        print(f"Wrote {len(ids)} unique job_id(s) to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
