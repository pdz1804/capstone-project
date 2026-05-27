#!/usr/bin/env python3
"""
Run Excel End-to-End RAG Pipeline (Parse → Chunk → Retrieve → LLM → Answer)

This script tests the FULL pipeline:
  1. Reads parsed Excel JSON (or parses raw .xlsx)
  2. Chunks with table-aware ExcelTableChunker
  3. Builds a retrieval index (BM25 / Dense / Hybrid)
  4. Queries the index with a user question
  5. Feeds retrieved chunks to LLM (OpenAI / Bedrock)
  6. Prints the generated answer with citations

Usage:
    # Quick test with a single file and default question
    python run_excel_e2e.py --json output/excel/courseware.json

    # Custom query
    python run_excel_e2e.py --json output/excel/courseware.json \
        --query "Giải tích 1 do ai dạy?"

    # Use a specific LLM provider
    python run_excel_e2e.py --json output/excel/courseware.json \
        --provider openai --model gpt-4.1-mini

    # Use the test_parsing LLM providers (openai/bedrock from .env)
    python run_excel_e2e.py --json output/excel/courseware.json \
        --use-local-llm --query "What courses are available?"

    # Batch: test all Excel JSONs
    python run_excel_e2e.py --json-dir output/excel/ \
        --query "Summarize the content of this spreadsheet"

    # Parse raw Excel first, then full pipeline
    python run_excel_e2e.py --raw raw/excel/courseware.xlsx \
        --query "Liệt kê các môn tự chọn"
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import textwrap
from pathlib import Path
from datetime import datetime

# ── Setup paths ──
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "src"))

# Load .env from backend/ root
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from chunking.excel_chunker import ExcelTableChunker, ExcelChunkingConfig, chunk_excel_json
from chunking.excel_preprocessor import ExcelPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("run_excel_e2e")

OUTPUT_DIR = BACKEND_DIR / "output" / "excel"
RAG_READY_DIR = BACKEND_DIR / "rag_ready"

DEFAULT_QUERIES = [
    "Summarize the content of this spreadsheet.",
    "What are the main categories or sections in this document?",
    "List any courses, items, or key data entries mentioned.",
]

def load_json(json_path: Path) -> list:
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────
# Step 1 & 2: Parse + Chunk
# ──────────────────────────────────────────────────────────────────

def step_parse_and_chunk(json_path: Path, chunk_size: int, chunk_overlap: int,
                          max_table_chunk: int) -> list:
    """Load JSON and chunk it."""
    sheets = load_json(json_path)
    doc_id = json_path.stem

    log.info(f"Loaded {len(sheets)} sheets from {json_path.name}")

    chunks = chunk_excel_json(
        sheets,
        doc_id=doc_id,
        source=str(json_path),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_table_chunk_size=max_table_chunk,
    )

    table_chunks = sum(1 for c in chunks if c.get("metadata", {}).get("is_table"))
    text_chunks = len(chunks) - table_chunks

    print(f"  📊 Produced {len(chunks)} chunks ({table_chunks} table, {text_chunks} text)")
    return chunks


# ──────────────────────────────────────────────────────────────────
# Step 3: Build simple in-memory retriever
# ──────────────────────────────────────────────────────────────────

def build_bm25_retriever(chunks: list):
    """Build a simple BM25 retriever from chunks."""
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        log.warning("rank_bm25 not installed. Using naive keyword search.")
        return None

    corpus = [c["text"] for c in chunks]
    tokenized = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized)
    return bm25


def retrieve_bm25(bm25, chunks: list, query: str, top_k: int = 5) -> list:
    """Retrieve top-k chunks using BM25."""
    if bm25 is None:
        # Fallback: naive keyword matching
        query_terms = set(query.lower().split())
        scored = []
        for chunk in chunks:
            text_lower = chunk["text"].lower()
            score = sum(1 for t in query_terms if t in text_lower)
            scored.append((score, chunk))
        scored.sort(key=lambda x: -x[0])
        return [
            {**c, "score": s, "retrieval_type": "keyword"}
            for s, c in scored[:top_k]
        ]

    from rank_bm25 import BM25Okapi
    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    scored_chunks = list(zip(scores, chunks))
    scored_chunks.sort(key=lambda x: -x[0])

    results = []
    for score, chunk in scored_chunks[:top_k]:
        results.append({**chunk, "score": float(score), "retrieval_type": "bm25"})
    return results


# ──────────────────────────────────────────────────────────────────
# Step 4 & 5: LLM Generation
# ──────────────────────────────────────────────────────────────────

def generate_with_src_generator(query: str, retrieved_docs: list,
                                 provider: str = "openai",
                                 model: str = "gpt-4o-mini") -> dict:
    """Use src/generation/generator.py RAGGenerator."""
    from generation.generator import RAGGenerator, GenerationConfig

    config = GenerationConfig(
        provider=provider,
        model_name=model,
        api_key=os.getenv("OPENAI_API_KEY"),
        enable_citations=True,
        temperature=0.0,
    )
    generator = RAGGenerator(config)
    return generator.generate(query, retrieved_docs)


# ──────────────────────────────────────────────────────────────────
# Pipeline runner
# ──────────────────────────────────────────────────────────────────

def run_e2e(json_path: Path, query: str, chunk_size: int, chunk_overlap: int,
            max_table_chunk: int, top_k: int, provider: str, model: str,
            use_local_llm: bool, verbose: bool):
    """Run the full end-to-end pipeline on one file."""

    print(f"E2E PIPELINE: {json_path.name}")

    # ── Step 1-2: Chunk ──
    print("STEP 1-2: PARSE + CHUNK")
    chunks = step_parse_and_chunk(json_path, chunk_size, chunk_overlap, max_table_chunk)

    if not chunks:
        log.error("No chunks produced   aborting.")
        return

    # ── Step 3: Retrieve ──
    print("STEP 3: RETRIEVE")
    print(f"  Query: {query}")
    bm25 = build_bm25_retriever(chunks)
    retrieved = retrieve_bm25(bm25, chunks, query, top_k=top_k)
    print(f"  Retrieved {len(retrieved)} chunks")

    for i, doc in enumerate(retrieved):
        meta = doc.get("metadata", {})
        score = doc.get("score", 0)
        sheet = meta.get("sheet_name", "?")
        is_table = meta.get("is_table", False)
        preview = doc["text"].replace("\n", " ")
        print(f"    [{i+1}] score={score:.3f} sheet='{sheet}' {'TABLE' if is_table else 'TEXT'}")
        if verbose:
            print(f"Preview: {preview}")

    # ── Step 4: What is fed to LLM ──
    print("STEP 4: CONTEXT FED TO LLM")
    for i, doc in enumerate(retrieved):
        meta = doc.get("metadata", {})
        sheet = meta.get("sheet_name", "")
        is_table = meta.get("is_table", False)
        print(f"\n  ── Chunk [{i+1}] Sheet: {sheet} ({'TABLE' if is_table else 'TEXT'}) ──")
        text_preview = doc["text"]
        for line in text_preview.split("\n"):
            print(f"  │ {line}")

    # ── Step 5: Generate ──
    print("STEP 5: LLM GENERATION")

    if use_local_llm:
        print(f"  Using local LLM provider: {os.getenv('PREFER_PROVIDER', 'openai')}")
        answer = asyncio.run(generate_with_local_llm(query, retrieved))
        print(f"\n  📝 ANSWER:\n")
        print(textwrap.indent(str(answer), "    "))
        result = {"answer": answer, "provider": "local"}
    else:
        print(f"  Using src/ generator: {provider}/{model}")
        result = generate_with_src_generator(query, retrieved, provider, model)
        answer = result.get("answer", "")
        print(f"\n  📝 ANSWER:\n")
        print(textwrap.indent(answer, "    "))

        if result.get("files"):
            print(f"\n  📁 Files cited:")
            for num, fname in result["files"].items():
                print(f"    [{num}] {fname}")

        if result.get("contents"):
            print(f"\n  📄 Content citations:")
            for cid, info in list(result["contents"].items())[:5]:
                if isinstance(info, dict):
                    print(f"    {cid}: {info.get('text', '')[:80]}...")

    return result


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run full Excel E2E RAG pipeline (Chunk → Retrieve → LLM → Answer)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        Examples:
          # Quick test
          python run_excel_e2e.py --json output/excel/courseware.json

          # Custom query
          python run_excel_e2e.py --json output/excel/courseware.json \\
              --query "Giải tích 1 do ai dạy?"

          # Use local test_parsing LLM
          python run_excel_e2e.py --json output/excel/courseware.json \\
              --use-local-llm --query "List all courses"

          # Parse raw Excel first
          python run_excel_e2e.py --raw raw/excel/courseware.xlsx \\
              --query "Summarize this spreadsheet"
        """)
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", type=str, help="Path to parsed Excel JSON")
    group.add_argument("--json-dir", type=str, help="Directory of parsed Excel JSONs")
    group.add_argument("--raw", type=str, help="Path to raw .xlsx file")

    parser.add_argument("--query", type=str, default=None, help="Question to ask (default: auto)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to retrieve (default: 10)")

    # Chunking
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--max-table-chunk", type=int, default=2000)

    # LLM
    parser.add_argument("--provider", type=str, default="openai", help="LLM provider (openai/azure/ollama)")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="LLM model name")
    parser.add_argument("--use-local-llm", action="store_true",
                        help="Use test_parsing LLM providers (reads .env)")

    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    query = args.query or DEFAULT_QUERIES[0]

    print("EXCEL END-TO-END RAG PIPELINE")
    print(f"  Query   : {query}")
    print(f"  LLM     : {'local (.env)' if args.use_local_llm else f'{args.provider}/{args.model}'}")
    print(f"  Chunking: size={args.chunk_size} overlap={args.chunk_overlap} table_max={args.max_table_chunk}")

    if args.raw:
        # Parse first
        sys.path.insert(0, str(BACKEND_DIR / "src" / "processor"))
        from xlsx_reader_v2 import process_workbook

        raw_path = Path(args.raw)
        json_path = OUTPUT_DIR / f"{raw_path.stem}.json"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        print("PARSING RAW EXCEL")
        result = process_workbook(raw_path)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        log.info(f"Parsed → {json_path}")

        run_e2e(json_path, query, args.chunk_size, args.chunk_overlap,
                args.max_table_chunk, args.top_k, args.provider, args.model,
                args.use_local_llm, args.verbose)

    elif args.json:
        json_path = Path(args.json)
        if not json_path.exists():
            log.error(f"Not found: {json_path}")
            sys.exit(1)
        run_e2e(json_path, query, args.chunk_size, args.chunk_overlap,
                args.max_table_chunk, args.top_k, args.provider, args.model,
                args.use_local_llm, args.verbose)

    elif args.json_dir:
        json_dir = Path(args.json_dir)
        json_files = sorted(json_dir.glob("*.json"))
        if not json_files:
            log.error(f"No JSON files in {json_dir}")
            sys.exit(1)

        for jf in json_files[:3]:  # Limit to 3 files to avoid excessive API calls
            try:
                run_e2e(jf, query, args.chunk_size, args.chunk_overlap,
                        args.max_table_chunk, args.top_k, args.provider, args.model,
                        args.use_local_llm, args.verbose)
            except Exception as e:
                log.error(f"Failed on {jf.name}: {e}")

    print("PIPELINE COMPLETE")


if __name__ == "__main__":
    main()
