"""Split-and-merge verification for hybrid PDF reader on 2412.19437v2.pdf.

Checks two things:
  1. SPLIT   every PyMuPDF-ToC heading (except demoted dupes) is consumed
     by ItemSequencer (i.e., matched against a text region line from Docling).
     Missed headings are printed so we can see where matching fails.
  2. MERGE   Docling-specific content (tables as [START_TABLE_CONTENT], formulas
     as $$...$$, pictures) lands under the correct section, not the preamble.

Run:
    cd backend && python tests/test_hybrid_pdf_2412.py
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from src.processor.item_sequencer import ItemSequencer, TABLE_START, IMG_START
from src.processor.pdf_reader import CustomPdfConfig, CustomPdfReader

PDF = BACKEND / "input" / "2412.19437v2.pdf"
OUT = BACKEND / "output" / "hybrid_test_2412"
OUT.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("hybrid_test")


def count_sections(tree):
    n = 0
    for node in tree:
        n += 1
        n += count_sections(node.get("children", []))
    return n


def collect_headings(tree, acc=None):
    if acc is None:
        acc = []
    for node in tree:
        h = (node.get("heading_text") or "").strip()
        if h:
            acc.append((h, node.get("heading_level", 0)))
        collect_headings(node.get("children", []), acc)
    return acc


def find_section(tree, needle_norm):
    """Find first section whose normalized heading matches needle_norm."""
    seq = ItemSequencer()
    for node in tree:
        if seq._normalize(node.get("heading_text", "")) == needle_norm:
            return node
        hit = find_section(node.get("children", []), needle_norm)
        if hit is not None:
            return hit
    return None


def content_stats(tree):
    total_chars = 0
    tables = 0
    formulas = 0
    images = 0
    preamble_chars = 0
    nonempty_sections = 0

    def walk(nodes, depth=0):
        nonlocal total_chars, tables, formulas, images, preamble_chars, nonempty_sections
        for node in nodes:
            c = node.get("content", "") or ""
            total_chars += len(c)
            if c.strip():
                nonempty_sections += 1
            tables += c.count(TABLE_START)
            formulas += c.count("$$\n")
            images += c.count(IMG_START)
            # Preamble == node with empty heading_text at top level
            if depth == 0 and not (node.get("heading_text") or "").strip():
                preamble_chars += len(c)
            walk(node.get("children", []), depth + 1)

    walk(tree)
    return {
        "sections": count_sections(tree),
        "nonempty_sections": nonempty_sections,
        "total_chars": total_chars,
        "preamble_chars": preamble_chars,
        "tables": tables,
        "formulas": formulas,
        "images": images,
    }


def diff_toc_vs_tree(pdf_path, tree):
    """Print which ToC entries did NOT appear as section headings in the tree."""
    import fitz

    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    doc.close()

    seq = ItemSequencer()
    tree_heads = {seq._normalize(h) for h, _ in collect_headings(tree)}

    missing = []
    for lvl, title, page in toc:
        key = seq._normalize(title)
        if key and key not in tree_heads:
            missing.append((lvl, title, page))
    return toc, missing


def run(label, source):
    cfg = CustomPdfConfig(
        content_source=source,
        enable_ocr=False,       # born-digital; skip OCR for speed
        extract_images=True,    # verify image tag [START_IMAGE_PATH] flows
    )
    reader = CustomPdfReader(cfg)
    tree = reader.read(str(PDF), output_dir=str(OUT / source))

    out_json = OUT / f"parsed_{source}.json"
    out_json.write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = content_stats(tree)
    toc, missing = diff_toc_vs_tree(str(PDF), tree)

    print(f"\n===== {label} (source={source}) =====")
    print(f"  output        : {out_json}")
    print(f"  ToC entries   : {len(toc)}")
    print(f"  sections      : {stats['sections']} (nonempty={stats['nonempty_sections']})")
    print(f"  total chars   : {stats['total_chars']:,}")
    print(f"  preamble chars: {stats['preamble_chars']:,} "
          f"({100.0*stats['preamble_chars']/max(1,stats['total_chars']):.1f}% of total)")
    print(f"  tables        : {stats['tables']}")
    print(f"  formulas      : {stats['formulas']}")
    print(f"  images        : {stats['images']}")
    print(f"  ToC missed    : {len(missing)}")
    if missing[:5]:
        for lvl, t, p in missing[:5]:
            print(f"      L{lvl} p{p}   {t[:80]}")

    return tree, stats, missing


def inspect_section(tree, needle_norm, label):
    """Pretty-print first 400 chars of a target section to eyeball split+merge."""
    node = find_section(tree, needle_norm)
    print(f"\n--- {label}: section '{needle_norm}' ---")
    if node is None:
        print("   (NOT FOUND   split failed at this heading)")
        return
    content = (node.get("content") or "").strip()
    print(f"   heading_level: {node.get('heading_level')}")
    print(f"   content_len  : {len(content)}")
    print(f"   has_TABLE    : {TABLE_START in content}")
    print(f"   has_FORMULA  : '$$' in content = {'$$' in content}")
    print(f"   children     : {len(node.get('children', []))}")
    preview = content[:400].replace("\n", "\n   | ")
    print(f"   preview      : {preview}")


def main():
    if not PDF.exists():
        print(f"PDF not found: {PDF}")
        sys.exit(1)

    baseline_tree, baseline_stats, baseline_missing = run("Baseline", "pymupdf")
    hybrid_tree, hybrid_stats, hybrid_missing = run("Hybrid (Docling content)", "docling")

    print("\n===== COMPARISON =====")
    for k in ("sections", "nonempty_sections", "total_chars",
              "preamble_chars", "tables", "formulas", "images"):
        b = baseline_stats[k]
        h = hybrid_stats[k]
        delta = h - b
        sign = "+" if delta >= 0 else ""
        print(f"  {k:20s}: pymupdf={b:>8}  docling={h:>8}  delta={sign}{delta}")

    print("\n===== SPLIT CHECK =====")
    print(f"  ToC headings missed (pymupdf): {len(baseline_missing)}")
    print(f"  ToC headings missed (docling): {len(hybrid_missing)}")
    if len(hybrid_missing) > len(baseline_missing):
        print("  [WARN] Hybrid lost headings vs baseline   heading-match regression.")
    else:
        print("  [OK]   Hybrid matches or improves split.")

    print("\n===== MERGE CHECK (content placement) =====")
    # Pick a few well-known sections of the DeepSeek-V3 paper.
    for needle, label in [
        ("introduction", "Introduction"),
        ("architecture", "Architecture"),
        ("pretraining", "Pre-Training"),
        ("evaluations", "Evaluations (Pre-Training)"),
        ("conclusion, limitations, and future directions", "Conclusion"),
        ("data construction", "Data Construction (subsection)"),
        ("evaluation benchmarks", "Evaluation Benchmarks (L3)"),
    ]:
        inspect_section(hybrid_tree, needle, f"HYBRID/{label}")

    # Absolute expectations for hybrid
    failures = []
    if hybrid_stats["tables"] == 0:
        failures.append("hybrid produced 0 tables   Docling table extraction not flowing through sequencer")
    if hybrid_stats["formulas"] == 0:
        failures.append("hybrid produced 0 formulas   Docling formula extraction not flowing through sequencer")
    if hybrid_stats["preamble_chars"] > hybrid_stats["total_chars"] * 0.5:
        failures.append("hybrid preamble > 50% of content   sequencer failed to split into sections")

    print("\n===== VERDICT =====")
    if failures:
        print("  FAIL:")
        for f in failures:
            print(f"    - {f}")
        sys.exit(2)
    print("  PASS   split-and-merge works on 2412.19437v2.pdf")


if __name__ == "__main__":
    main()
