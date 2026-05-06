"""Generate span-level pseudo ground truth for chunking retrieval eval.

This script adapts the SyntheticEvaluation idea from
brandonstarxel/chunking_evaluation to this project's stage4_rag_ready corpus.

It can:
1. generate query/reference CSV directly with the OpenAI API;
2. verify each reference against the original markdown corpus; and
3. export a normalized eval set:
   query + relevant_excerpt + doc_id + start_char + end_char.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.paths import workspace_paths_for_user


@dataclass(frozen=True)
class CorpusDoc:
    doc_id: str
    path: Path
    text: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _stable_doc_id(path: Path, corpus_root: Path) -> str:
    try:
        rel = path.relative_to(corpus_root)
    except ValueError:
        return path.stem
    if len(rel.parts) >= 2:
        return rel.parts[0]
    return path.stem


def discover_corpus_docs(input_path: Path, max_documents: Optional[int] = None) -> List[CorpusDoc]:
    """Discover markdown documents to use as the canonical eval corpus."""
    input_path = input_path.resolve()
    if input_path.is_file():
        candidates = [input_path]
        corpus_root = input_path.parent
    else:
        corpus_root = input_path
        direct_named = []
        if input_path.exists():
            for doc_dir in sorted(p for p in input_path.iterdir() if p.is_dir()):
                named = doc_dir / f"{doc_dir.name}.md"
                if named.exists():
                    direct_named.append(named)
        candidates = direct_named or sorted(input_path.rglob("*.md"))

    docs: List[CorpusDoc] = []
    for md_path in candidates:
        if md_path.name.startswith("."):
            continue
        text = _read_text(md_path)
        if not text.strip():
            continue
        docs.append(
            CorpusDoc(
                doc_id=_stable_doc_id(md_path, corpus_root),
                path=md_path.resolve(),
                text=text,
            )
        )
        if max_documents is not None and len(docs) >= max_documents:
            break
    return docs


@dataclass(frozen=True)
class SourceSegment:
    doc: CorpusDoc
    text: str
    start_char: int
    end_char: int


def make_source_segments(
    docs: List[CorpusDoc],
    *,
    window_chars: int,
    max_segments_per_document: Optional[int],
) -> List[SourceSegment]:
    segments: List[SourceSegment] = []
    for doc in docs:
        raw_parts: List[tuple[int, int]] = []
        cursor = 0
        for block in doc.text.split("\n\n"):
            start = doc.text.find(block, cursor)
            if start < 0:
                cursor += len(block) + 2
                continue
            end = start + len(block)
            cursor = end
            if len(block.strip()) >= 300:
                raw_parts.append((start, end))

        if not raw_parts:
            step = max(1, window_chars)
            raw_parts = [
                (start, min(start + window_chars, len(doc.text)))
                for start in range(0, len(doc.text), step)
            ]

        merged: List[SourceSegment] = []
        current_start: Optional[int] = None
        current_end: Optional[int] = None
        for start, end in raw_parts:
            if current_start is None:
                current_start, current_end = start, end
                continue
            assert current_end is not None
            if end - current_start <= window_chars:
                current_end = end
            else:
                text = doc.text[current_start:current_end].strip()
                if text:
                    merged.append(SourceSegment(doc, text, current_start, current_end))
                current_start, current_end = start, end
        if current_start is not None and current_end is not None:
            text = doc.text[current_start:current_end].strip()
            if text:
                merged.append(SourceSegment(doc, text, current_start, current_end))

        if max_segments_per_document is not None:
            merged = merged[:max_segments_per_document]
        segments.extend(merged)
    return segments


def _extract_json_object(text: str) -> Dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end < start:
            raise
        parsed = json.loads(raw[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("OpenAI response JSON must be an object")
    return parsed


def _call_openai_json(
    *,
    client: Any,
    model: str,
    segment: SourceSegment,
    queries_per_segment: int,
) -> Dict[str, Any]:
    prompt = f"""You generate retrieval evaluation data.

Given a source excerpt, create exactly {queries_per_segment} factual search queries.
Each query must be answerable directly from the source excerpt.

For each query, return one relevant_excerpt copied VERBATIM from the source excerpt.
The relevant_excerpt must be a contiguous exact substring. Do not paraphrase it.
Prefer excerpts of 80-260 characters that contain the answer.

Return JSON only with this schema:
{{
  "items": [
    {{
      "query": "...",
      "relevant_excerpt": "exact substring copied from source"
    }}
  ]
}}

SOURCE EXCERPT:
{segment.text}
"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Return valid JSON only. Never invent text that is not in the source excerpt.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or ""
    return _extract_json_object(content)


def run_native_openai_generation(
    *,
    docs: List[CorpusDoc],
    raw_csv_path: Path,
    openai_api_key: Optional[str],
    model: str,
    queries_per_segment: int,
    source_window_chars: int,
    max_source_segments_per_document: Optional[int],
) -> None:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is required for --generate.") from exc

    api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --generate.")

    segments = make_source_segments(
        docs,
        window_chars=source_window_chars,
        max_segments_per_document=max_source_segments_per_document,
    )
    if not segments:
        raise RuntimeError("No suitable source segments found for generation.")

    client = OpenAI(api_key=api_key)
    raw_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with raw_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["question", "corpus_id", "references"])
        writer.writeheader()
        for segment_index, segment in enumerate(segments):
            try:
                payload = _call_openai_json(
                    client=client,
                    model=model,
                    segment=segment,
                    queries_per_segment=queries_per_segment,
                )
            except Exception as exc:
                print(f"Generation failed for {segment.doc.doc_id} segment {segment_index}: {exc}")
                continue

            items = payload.get("items") or []
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("query") or item.get("question") or "").strip()
                excerpt = str(item.get("relevant_excerpt") or item.get("excerpt") or "").strip()
                if not question or not excerpt:
                    continue
                local_start = segment.text.find(excerpt)
                if local_start < 0:
                    # Keep the raw row out: downstream eval must be exact-match.
                    continue
                start = segment.start_char + local_start
                refs = [{"content": excerpt, "start_index": start, "end_index": start + len(excerpt)}]
                writer.writerow(
                    {
                        "question": question,
                        "corpus_id": str(segment.doc.path),
                        "references": json.dumps(refs, ensure_ascii=False),
                    }
                )


def _load_raw_csv(raw_csv_path: Path) -> List[Dict[str, str]]:
    with raw_csv_path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _parse_references(raw: str) -> List[Dict[str, Any]]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _find_exact_span(text: str, excerpt: str, preferred_start: Optional[int]) -> Optional[tuple[int, int]]:
    if not excerpt:
        return None
    if preferred_start is not None and preferred_start >= 0:
        end = preferred_start + len(excerpt)
        if text[preferred_start:end] == excerpt:
            return preferred_start, end
    start = text.find(excerpt)
    if start < 0:
        return None
    return start, start + len(excerpt)


def build_span_eval_rows(raw_rows: Iterable[Dict[str, str]], corpus_docs: List[CorpusDoc]) -> List[Dict[str, Any]]:
    by_path = {str(doc.path): doc for doc in corpus_docs}
    by_name = {doc.path.name: doc for doc in corpus_docs}
    by_doc_id = {doc.doc_id: doc for doc in corpus_docs}

    out: List[Dict[str, Any]] = []
    skipped = 0
    for row_idx, row in enumerate(raw_rows):
        query = (row.get("question") or row.get("query") or "").strip()
        corpus_id = (row.get("corpus_id") or row.get("doc_id") or row.get("source_doc_id") or "").strip()
        references = _parse_references(row.get("references", ""))
        if not query or not references:
            skipped += 1
            continue

        corpus_key = str(Path(corpus_id).resolve()) if corpus_id else ""
        doc = by_path.get(corpus_key) or by_name.get(Path(corpus_id).name) or by_doc_id.get(corpus_id)
        if doc is None:
            skipped += 1
            continue

        query_id = f"q_{row_idx:06d}"
        for ref_idx, ref in enumerate(references):
            excerpt = str(ref.get("content") or ref.get("excerpt") or "").strip()
            preferred_start = ref.get("start_index", ref.get("start_char"))
            try:
                preferred_start_int = int(preferred_start) if preferred_start is not None else None
            except Exception:
                preferred_start_int = None
            span = _find_exact_span(doc.text, excerpt, preferred_start_int)
            if span is None:
                skipped += 1
                continue
            start_char, end_char = span
            out.append(
                {
                    "sample_id": f"{query_id}_r{ref_idx}",
                    "query_id": query_id,
                    "query": query,
                    "relevant_excerpt": excerpt,
                    "doc_id": doc.doc_id,
                    "source_doc_path": str(doc.path),
                    "start_char": start_char,
                    "end_char": end_char,
                    "reference_index": ref_idx,
                    "reference_count": len(references),
                    "raw_corpus_id": corpus_id,
                }
            )

    if skipped:
        print(f"Skipped {skipped} raw rows/references that could not be verified exactly.")
    return out


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "sample_id",
        "query_id",
        "query",
        "relevant_excerpt",
        "doc_id",
        "source_doc_path",
        "start_char",
        "end_char",
        "reference_index",
        "reference_count",
        "raw_corpus_id",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_manifest(path: Path, docs: List[CorpusDoc], raw_csv: Path, output_jsonl: Path, output_csv: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "raw_csv": str(raw_csv),
        "output_jsonl": str(output_jsonl),
        "output_csv": str(output_csv),
        "documents": [
            {
                "doc_id": doc.doc_id,
                "path": str(doc.path),
                "chars": len(doc.text),
            }
            for doc in docs
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    paths = workspace_paths_for_user()
    default_output = paths.processing_dir.parent / "evaluation" / "chunking_eval"
    parser = argparse.ArgumentParser(
        description="Generate query/excerpt span eval set for chunking strategy evaluation."
    )
    parser.add_argument("--input", default=str(paths.rag_ready_dir), help="stage4_rag_ready root or a markdown file.")
    parser.add_argument("--output-dir", default=str(default_output))
    parser.add_argument("--raw-csv", default=None, help="SyntheticEvaluation CSV path. Defaults under output-dir.")
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--generate", action="store_true", help="Generate raw query/excerpt CSV with OpenAI first.")
    parser.add_argument("--openai-api-key", default=None)
    parser.add_argument("--model", default=os.getenv("OPENAI_EVAL_MODEL", "gpt-4o-mini"))
    parser.add_argument("--queries-per-segment", type=int, default=1)
    parser.add_argument("--source-window-chars", type=int, default=2500)
    parser.add_argument("--max-source-segments-per-document", type=int, default=5)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir).resolve()
    raw_csv = Path(args.raw_csv).resolve() if args.raw_csv else output_dir / "generated_queries_excerpts.csv"
    output_jsonl = output_dir / "eval_spans.jsonl"
    output_csv = output_dir / "eval_spans.csv"
    manifest = output_dir / "eval_spans_manifest.json"

    docs = discover_corpus_docs(input_path, max_documents=args.max_documents)
    if not docs:
        raise SystemExit(f"No markdown corpus documents found under {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(manifest, docs, raw_csv, output_jsonl, output_csv)

    if args.generate:
        run_native_openai_generation(
            docs=docs,
            raw_csv_path=raw_csv,
            openai_api_key=args.openai_api_key,
            model=args.model,
            queries_per_segment=args.queries_per_segment,
            source_window_chars=args.source_window_chars,
            max_source_segments_per_document=args.max_source_segments_per_document,
        )

    if not raw_csv.exists():
        raise SystemExit(
            f"Raw CSV not found: {raw_csv}. Run with --generate or pass --raw-csv from SyntheticEvaluation."
        )

    rows = build_span_eval_rows(_load_raw_csv(raw_csv), docs)
    write_jsonl(output_jsonl, rows)
    write_csv(output_csv, rows)
    write_manifest(manifest, docs, raw_csv, output_jsonl, output_csv)

    print(
        json.dumps(
            {
                "documents": len(docs),
                "span_samples": len(rows),
                "raw_csv": str(raw_csv),
                "output_jsonl": str(output_jsonl),
                "output_csv": str(output_csv),
                "manifest": str(manifest),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
