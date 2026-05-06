"""Evaluate chunking strategies against span-level retrieval ground truth.

The runner compares the current production chunk loader with an experimental
global semantic packing strategy inspired by Chroma's chunking report.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.chunking.chunker import ChunkingConfig, TextChunker
from src.retrieval.rag_retrievers import (
    BaseRetriever,
    SimpleBM25Retriever,
    SimpleDenseRetriever,
    SimpleHybridRetriever,
)
from app.core.paths import WorkspacePaths, load_yaml_config, merged_runtime_settings
from app.repositories import TextIndexRepository, build_qdrant_client, save_bm25_index, save_documents_snapshot
from app.services.indexing_service import _get_text_embedder
from app.services.text_search_service import TextSearchService

_SENTENCE_TRANSFORMER_CACHE: Dict[str, Any] = {}


@dataclass(frozen=True)
class CorpusDoc:
    doc_id: str
    path: Path
    text: str


@dataclass(frozen=True)
class SourceUnit:
    doc_id: str
    text: str
    start_char: int
    end_char: int
    heading: str


@dataclass(frozen=True)
class TextRegion:
    doc_id: str
    text: str
    char_map: List[Optional[int]]
    heading: str
    heading_stack: Tuple[str, ...]


@dataclass(frozen=True)
class TableBlock:
    doc_id: str
    lines: List[Tuple[int, int, str]]
    heading: str


class ProductionTextSearchAdapter:
    """Use the same text retrieval path as run_api.py without touching the live index."""

    def __init__(self, *, output_dir: Path, strategy_name: str, base_config: Dict[str, Any]):
        self.output_dir = output_dir
        self.strategy_name = strategy_name
        safe_strategy = re.sub(r"[^a-zA-Z0-9_]+", "_", strategy_name).strip("_") or "strategy"
        self.user_id = f"chunk_eval_{safe_strategy}_{uuid.uuid4().hex[:10]}"
        self.collection = f"chunk_eval_text_{safe_strategy}_{uuid.uuid4().hex[:10]}"
        self.index_root = output_dir / "production_like_indexes" / self.user_id
        self.paths = WorkspacePaths(
            user_id=self.user_id,
            input_dir=self.index_root / "input",
            output_dir=self.index_root / "output",
            processing_dir=self.index_root / "output" / "processing",
            rag_ready_dir=self.index_root / "output" / "processing" / "stage4_rag_ready",
            retrieval_dir=self.index_root / "output" / "retrieval",
            documents_json_path=self.index_root / "output" / "retrieval" / "documents.json",
            bm25_pickle_path=self.index_root / "output" / "retrieval" / "bm25_index.pkl",
            image_retrieval_root=self.index_root / "output" / "image_retrieval",
            image_meta_path=self.index_root / "output" / "image_retrieval" / "image_index_meta.json",
        )
        self.cfg = copy.deepcopy(base_config)
        q = self.cfg.setdefault("qdrant", {})
        q["text_collection"] = self.collection
        self.client = build_qdrant_client(self.cfg)
        self.service: Optional[TextSearchService] = None
        self.repo: Optional[TextIndexRepository] = None

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        self.paths.retrieval_dir.mkdir(parents=True, exist_ok=True)
        save_documents_snapshot(documents, self.paths.documents_json_path, user_id=self.user_id)
        save_bm25_index(documents, self.paths.bm25_pickle_path, user_id=self.user_id)

        q = self.cfg.get("qdrant", {}) or {}
        tr = self.cfg.get("text_retrieval", {}) or {}
        embed_model = tr.get("embedding_model", "all-MiniLM-L6-v2")
        vector_name = q.get("text_vector_name", "text")
        quantization = q.get("text_storage_quantization", "scalar")

        model = _get_text_embedder(embed_model)
        dim = model.get_sentence_embedding_dimension()
        texts = [str(doc.get("text") or "") for doc in documents]
        embeddings = model.encode(texts, show_progress_bar=False)

        repo = TextIndexRepository(
            self.client,
            collection_name=self.collection,
            vector_name=vector_name,
            vector_size=dim,
            storage_quantization=quantization,
            on_disk_vectors=True,
        )
        repo.ensure_collection(recreate=True)

        ids: List[str] = []
        payloads: List[Dict[str, Any]] = []
        for doc in documents:
            cid = str(doc.get("id") or "").strip()
            if not cid:
                raise ValueError("Production-like eval requires every chunk to have an id")
            metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
            payload: Dict[str, Any] = {
                "chunk_id": cid,
                "user_id": self.user_id,
                "source": doc.get("source", ""),
                "text_preview": doc.get("text", "") or "",
            }
            storage_uri = metadata.get("storage_uri")
            if storage_uri:
                payload["storage_uri"] = storage_uri
                payload["storage_backend"] = metadata.get("storage_backend", "s3")
            ids.append(cid)
            payloads.append(payload)
        repo.upsert_chunks(ids, embeddings, payloads, wait=True)
        self.repo = repo

        service = TextSearchService(self.cfg, user_id=self.user_id)
        service._paths = self.paths
        service._user_id = self.user_id
        self.service = service

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if self.service is None:
            raise RuntimeError("ProductionTextSearchAdapter must be indexed before search")
        return self.service.search(query, "hybrid", top_k, skip_reranker=True)

    def cleanup(self) -> None:
        try:
            self.client.delete_collection(self.collection)
        except Exception:
            pass


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def discover_corpus_docs(stage4_dir: Path, max_documents: Optional[int] = None) -> List[CorpusDoc]:
    docs: List[CorpusDoc] = []
    for doc_dir in sorted(p for p in stage4_dir.iterdir() if p.is_dir()):
        md_path = doc_dir / f"{doc_dir.name}.md"
        if not md_path.exists():
            candidates = sorted(doc_dir.glob("*.md"))
            if not candidates:
                continue
            md_path = candidates[0]
        text = md_path.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            continue
        docs.append(CorpusDoc(doc_id=doc_dir.name, path=md_path.resolve(), text=text))
        if max_documents is not None and len(docs) >= max_documents:
            break
    return docs


def _metadata_span(chunk: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    metadata = chunk.get("metadata") or {}
    start = metadata.get("start_char", metadata.get("char_start", chunk.get("start_char")))
    end = metadata.get("end_char", metadata.get("char_end", chunk.get("end_char")))
    try:
        return int(start), int(end)
    except (TypeError, ValueError):
        return None, None


def _metadata_spans(chunk: Dict[str, Any]) -> List[Tuple[int, int]]:
    metadata = chunk.get("metadata") or {}
    raw_spans = metadata.get("char_spans") or metadata.get("source_spans") or chunk.get("char_spans")
    spans: List[Tuple[int, int]] = []
    if isinstance(raw_spans, list):
        for raw in raw_spans:
            if isinstance(raw, dict):
                start = raw.get("start_char", raw.get("char_start", raw.get("start")))
                end = raw.get("end_char", raw.get("char_end", raw.get("end")))
            elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
                start, end = raw[0], raw[1]
            else:
                continue
            try:
                start_i = int(start)
                end_i = int(end)
            except (TypeError, ValueError):
                continue
            if end_i > start_i:
                spans.append((start_i, end_i))
    if spans:
        return _merge_intervals(spans)

    start, end = _metadata_span(chunk)
    if start is None or end is None or end <= start:
        return []
    return [(start, end)]


def _normalize_chunk(
    *,
    chunk_id: str,
    doc_id: str,
    text: str,
    source: str,
    start_char: Optional[int],
    end_char: Optional[int],
    strategy: str,
    chunk_type: str,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(extra_metadata or {})
    metadata.update(
        {
            "doc_id": doc_id,
            "source": source,
            "start_char": start_char,
            "end_char": end_char,
            "char_start": start_char,
            "char_end": end_char,
            "char_length": len(text),
            "chunking_strategy": strategy,
            "chunk_type": chunk_type,
        }
    )
    return {
        "id": chunk_id,
        "text": text,
        "source": source,
        "doc_id": doc_id,
        "metadata": metadata,
    }


def build_production_chunks(stage4_dir: Path, *, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
    regular_docs, prebuilt_chunks = BaseRetriever.load_documents_from_directory(stage4_dir)
    chunks: List[Dict[str, Any]] = []

    for idx, chunk in enumerate(prebuilt_chunks):
        metadata = dict(chunk.get("metadata") or {})
        doc_id = str(chunk.get("doc_id") or metadata.get("doc_id") or Path(chunk.get("source", "")).parent.name)
        start, end = _metadata_span(chunk)
        chunk_type = str(metadata.get("chunk_type") or metadata.get("content_type") or chunk.get("type") or "prebuilt")
        chunks.append(
            _normalize_chunk(
                chunk_id=str(chunk.get("id") or f"{doc_id}_prebuilt_{idx}"),
                doc_id=doc_id,
                text=str(chunk.get("text") or ""),
                source=str(chunk.get("source") or metadata.get("source") or ""),
                start_char=start,
                end_char=end,
                strategy="production_prebuilt",
                chunk_type=chunk_type,
                extra_metadata=metadata,
            )
        )

    if regular_docs:
        chunker = TextChunker(ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap))
        for doc in regular_docs:
            for chunk in chunker.chunk_document(str(doc.get("text") or ""), str(doc.get("id") or "document")):
                metadata = dict(chunk.get("metadata") or {})
                start, end = _metadata_span(chunk)
                chunks.append(
                    _normalize_chunk(
                        chunk_id=str(chunk.get("id") or metadata.get("chunk_name") or f"{doc.get('id')}_regular"),
                        doc_id=str(metadata.get("doc_id") or doc.get("id")),
                        text=str(chunk.get("text") or ""),
                        source=str(doc.get("source") or metadata.get("source") or ""),
                        start_char=start,
                        end_char=end,
                        strategy="production_prebuilt",
                        chunk_type="regular_text",
                        extra_metadata=metadata,
                    )
                )
    return [chunk for chunk in chunks if chunk["text"].strip()]


def build_markdown_recursive_chunks(
    docs: Sequence[CorpusDoc],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> List[Dict[str, Any]]:
    """Build a RecursiveCharacterTextSplitter baseline from the same markdown corpus."""
    chunker = TextChunker(ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap))
    chunks: List[Dict[str, Any]] = []
    for doc in docs:
        for idx, chunk_info in enumerate(chunker.split_text_with_offsets(doc.text)):
            text = str(chunk_info.get("text") or "")
            if not text.strip():
                continue
            start = chunk_info.get("start_char")
            end = chunk_info.get("end_char")
            chunks.append(
                _normalize_chunk(
                    chunk_id=f"{doc.doc_id}_recursive_markdown_{idx}",
                    doc_id=doc.doc_id,
                    text=text,
                    source=str(doc.path),
                    start_char=start,
                    end_char=end,
                    strategy="recursive_markdown",
                    chunk_type="markdown_text",
                    extra_metadata={
                        "char_spans": [{"start_char": start, "end_char": end}]
                        if start is not None and end is not None
                        else [],
                    },
                )
            )
    return chunks


def _line_spans(text: str) -> List[Tuple[int, int, str]]:
    spans: List[Tuple[int, int, str]] = []
    pos = 0
    for raw_line in text.splitlines(keepends=True):
        start = pos
        end = pos + len(raw_line)
        spans.append((start, end, raw_line.rstrip("\r\n")))
        pos = end
    return spans


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def _is_table_marker(line: str) -> bool:
    return line.strip() in {"[START_TABLE_CONTENT]", "[END_TABLE_CONTENT]"}


def _strip_table_markers_from_line(start: int, end: int, line: str) -> Tuple[int, int, str]:
    cleaned = line.replace("[START_TABLE_CONTENT]", "").replace("[END_TABLE_CONTENT]", "")
    stripped = cleaned.strip()
    if not stripped:
        return start, start, ""
    original_idx = line.find(stripped)
    if original_idx >= 0:
        return start + original_idx, start + original_idx + len(stripped), stripped
    cleaned_idx = len(cleaned) - len(cleaned.lstrip())
    return start + cleaned_idx, start + cleaned_idx + len(cleaned.strip()), stripped


def _is_heading(line: str) -> bool:
    return bool(re.match(r"^\s{0,3}#{1,6}\s+\S", line))


def _clean_heading(line: str) -> str:
    return re.sub(r"^\s{0,3}#{1,6}\s+", "", line).strip()


def _build_region(doc_id: str, fragments: Sequence[Tuple[int, int, str]], heading: str) -> Optional[TextRegion]:
    text_parts: List[str] = []
    char_map: List[Optional[int]] = []
    for idx, (start, end, line) in enumerate(fragments):
        if idx:
            text_parts.append("\n")
            char_map.append(None)
        text_parts.append(line)
        char_map.extend(range(start, min(end, start + len(line))))
    text = "".join(text_parts).strip()
    if not text:
        return None

    leading = len("".join(text_parts)) - len("".join(text_parts).lstrip())
    trailing = len("".join(text_parts).rstrip())
    full_text = "".join(text_parts)
    stripped_text = full_text[leading:trailing]
    stripped_map = char_map[leading:trailing]
    heading_stack = tuple(
        _clean_heading(line)
        for _, _, line in fragments
        if _is_heading(line) and _clean_heading(line)
    )
    if heading and (not heading_stack or heading_stack[-1] != heading):
        heading_stack = (*heading_stack, heading)
    return TextRegion(doc_id=doc_id, text=stripped_text, char_map=stripped_map, heading=heading, heading_stack=heading_stack)


def extract_text_regions_and_tables(doc: CorpusDoc) -> Tuple[List[TextRegion], List[TableBlock]]:
    lines = _line_spans(doc.text)
    regions: List[TextRegion] = []
    tables: List[TableBlock] = []
    heading = ""
    text_buffer: List[Tuple[int, int, str]] = []

    def flush_text_buffer() -> None:
        nonlocal text_buffer
        region = _build_region(doc.doc_id, text_buffer, heading)
        if region is not None:
            regions.append(region)
        text_buffer = []

    i = 0
    while i < len(lines):
        start, end, line = _strip_table_markers_from_line(*lines[i])
        if not line:
            if text_buffer:
                text_buffer.append((start, end, ""))
            i += 1
            continue

        if _is_heading(line):
            heading = _clean_heading(line)
            text_buffer.append((start, end, line))
            i += 1
            continue

        if _is_table_line(line):
            flush_text_buffer()
            table_lines: List[Tuple[int, int, str]] = []
            while i < len(lines):
                table_start, table_end, table_line = _strip_table_markers_from_line(*lines[i])
                if not table_line:
                    i += 1
                    continue
                if not _is_table_line(table_line):
                    break
                table_lines.append((table_start, table_end, table_line))
                i += 1
            if len(table_lines) >= 2:
                tables.append(TableBlock(doc.doc_id, table_lines, heading))
            else:
                text_buffer.extend(table_lines)
            continue

        text_buffer.append((start, end, line))
        i += 1

    flush_text_buffer()
    return regions, tables


def _sentence_units(
    *,
    doc_id: str,
    block_text: str,
    block_start: int,
    block_end: int,
    heading: str,
    max_unit_chars: int,
) -> List[SourceUnit]:
    stripped = block_text.strip()
    if not stripped:
        return []
    if len(stripped) <= max_unit_chars:
        local_start = block_text.find(stripped)
        return [
            SourceUnit(
                doc_id=doc_id,
                text=stripped,
                start_char=block_start + max(0, local_start),
                end_char=block_start + max(0, local_start) + len(stripped),
                heading=heading,
            )
        ]

    units: List[SourceUnit] = []
    pattern = re.compile(r".+?(?:[.!?](?=\s)|\n{1,}|$)", re.DOTALL)
    current_start: Optional[int] = None
    current_end: Optional[int] = None
    for match in pattern.finditer(block_text):
        text = match.group(0).strip()
        if not text:
            continue
        start = block_start + match.start() + (len(match.group(0)) - len(match.group(0).lstrip()))
        end = block_start + match.end() - (len(match.group(0)) - len(match.group(0).rstrip()))
        if current_start is None:
            current_start, current_end = start, end
            continue
        assert current_end is not None
        if end - current_start <= max_unit_chars:
            current_end = end
        else:
            source_text = block_text[current_start - block_start : current_end - block_start].strip()
            if source_text:
                units.append(SourceUnit(doc_id, source_text, current_start, current_end, heading))
            current_start, current_end = start, end
    if current_start is not None and current_end is not None:
        source_text = block_text[current_start - block_start : current_end - block_start].strip()
        if source_text:
            units.append(SourceUnit(doc_id, source_text, current_start, current_end, heading))
    return units


def extract_units_and_tables(
    doc: CorpusDoc,
    *,
    max_unit_chars: int,
) -> Tuple[List[SourceUnit], List[TableBlock]]:
    lines = _line_spans(doc.text)
    units: List[SourceUnit] = []
    tables: List[TableBlock] = []
    heading = ""
    text_buffer: List[Tuple[int, int, str]] = []

    def flush_text_buffer() -> None:
        nonlocal text_buffer
        if not text_buffer:
            return
        start = text_buffer[0][0]
        end = text_buffer[-1][1]
        block = doc.text[start:end]
        units.extend(
            _sentence_units(
                doc_id=doc.doc_id,
                block_text=block,
                block_start=start,
                block_end=end,
                heading=heading,
                max_unit_chars=max_unit_chars,
            )
        )
        text_buffer = []

    i = 0
    while i < len(lines):
        start, end, line = lines[i]
        start, end, line = _strip_table_markers_from_line(start, end, line)
        if not line:
            flush_text_buffer()
            i += 1
            continue
        if _is_table_marker(line):
            flush_text_buffer()
            i += 1
            continue

        if _is_heading(line):
            flush_text_buffer()
            heading = _clean_heading(line)
            text_buffer.append((start, end, line))
            i += 1
            continue

        if _is_table_line(line):
            flush_text_buffer()
            table_lines: List[Tuple[int, int, str]] = []
            while i < len(lines):
                table_start, table_end, table_line = _strip_table_markers_from_line(*lines[i])
                if not table_line:
                    i += 1
                    continue
                if not _is_table_line(table_line):
                    break
                table_lines.append((table_start, table_end, table_line))
                i += 1
            if len(table_lines) >= 2:
                tables.append(TableBlock(doc.doc_id, table_lines, heading))
            else:
                text_buffer.extend(table_lines)
            continue

        if not line.strip():
            flush_text_buffer()
            i += 1
            continue

        text_buffer.append((start, end, line))
        i += 1

    flush_text_buffer()
    return units, tables


def _table_chunks(
    table: TableBlock,
    *,
    doc_path: Path,
    strategy: str,
    max_table_chars: int,
    chunk_index_start: int,
) -> List[Dict[str, Any]]:
    lines = table.lines
    header = lines[:2] if len(lines) >= 2 else lines[:1]
    rows = lines[2:] if len(lines) >= 2 else lines[1:]
    if not rows:
        rows = lines
        header = []

    chunks: List[Dict[str, Any]] = []
    current_rows: List[Tuple[int, int, str]] = []

    def emit(group: List[Tuple[int, int, str]]) -> None:
        if not group:
            return
        chunk_lines = header + group
        body = "\n".join(line for _, _, line in chunk_lines)
        if table.heading:
            body = f"[Section: {table.heading}]\n\n{body}"
        retained_spans = [(start, end) for start, end, _ in chunk_lines if end > start]
        merged_spans = _merge_intervals(retained_spans)
        start_char = min(start for start, _ in merged_spans)
        end_char = group[-1][1]
        chunks.append(
            _normalize_chunk(
                chunk_id=f"{table.doc_id}_global_table_{chunk_index_start + len(chunks)}",
                doc_id=table.doc_id,
                text=body,
                source=str(doc_path),
                start_char=start_char,
                end_char=end_char,
                strategy=strategy,
                chunk_type="table_with_header",
                extra_metadata={
                    "heading": table.heading,
                    "table_header_retained": bool(header),
                    "table_row_count": len(group),
                    "char_spans": [
                        {"start_char": start, "end_char": end}
                        for start, end in merged_spans
                    ],
                },
            )
        )

    header_chars = sum(len(line) for _, _, line in header)
    for row in rows:
        next_chars = header_chars + sum(len(line) for _, _, line in current_rows) + len(row[2])
        if current_rows and next_chars > max_table_chars:
            emit(current_rows)
            current_rows = [row]
        else:
            current_rows.append(row)
    emit(current_rows)
    return chunks


def openai_token_count(string: str) -> int:
    """Token counter used by Chroma's chunking_evaluation package."""
    import tiktoken

    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(string, disallowed_special=()))


# Ported from brandonstarxel/chunking_evaluation:
# chunking_evaluation/chunking/recursive_token_chunker.py and
# chunking_evaluation/chunking/cluster_semantic_chunker.py.
# Local changes are limited to offset reconstruction and table handling.
def _split_text_with_regex(text: str, separator: str, keep_separator: bool) -> List[str]:
    if separator:
        if keep_separator:
            splits_raw = re.split(f"({separator})", text)
            splits = [splits_raw[i] + splits_raw[i + 1] for i in range(1, len(splits_raw), 2)]
            if len(splits_raw) % 2 == 0:
                splits += splits_raw[-1:]
            splits = [splits_raw[0]] + splits
        else:
            splits = re.split(separator, text)
    else:
        splits = list(text)
    return [s for s in splits if s != ""]


class ChromaTextSplitter:
    def __init__(
        self,
        *,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        length_function: Callable[[str], int] = len,
        keep_separator: bool = False,
        strip_whitespace: bool = True,
    ) -> None:
        if chunk_overlap > chunk_size:
            raise ValueError(
                f"Got a larger chunk overlap ({chunk_overlap}) than chunk size ({chunk_size}), should be smaller."
            )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._length_function = length_function
        self._keep_separator = keep_separator
        self._strip_whitespace = strip_whitespace

    def _join_docs(self, docs: List[str], separator: str) -> Optional[str]:
        text = separator.join(docs)
        if self._strip_whitespace:
            text = text.strip()
        return text or None

    def _merge_splits(self, splits: Iterable[str], separator: str) -> List[str]:
        separator_len = self._length_function(separator)
        docs: List[str] = []
        current_doc: List[str] = []
        total = 0
        for d in splits:
            length = self._length_function(d)
            if total + length + (separator_len if len(current_doc) > 0 else 0) > self._chunk_size:
                if len(current_doc) > 0:
                    doc = self._join_docs(current_doc, separator)
                    if doc is not None:
                        docs.append(doc)
                    while total > self._chunk_overlap or (
                        total + length + (separator_len if len(current_doc) > 0 else 0) > self._chunk_size
                        and total > 0
                    ):
                        total -= self._length_function(current_doc[0]) + (
                            separator_len if len(current_doc) > 1 else 0
                        )
                        current_doc = current_doc[1:]
            current_doc.append(d)
            total += length + (separator_len if len(current_doc) > 1 else 0)
        doc = self._join_docs(current_doc, separator)
        if doc is not None:
            docs.append(doc)
        return docs


class ChromaRecursiveTokenChunker(ChromaTextSplitter):
    def __init__(
        self,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
        keep_separator: bool = True,
        is_separator_regex: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap, keep_separator=keep_separator, **kwargs)
        self._separators = separators or ["\n\n", "\n", ".", "?", "!", " ", ""]
        self._is_separator_regex = is_separator_regex

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        final_chunks: List[str] = []
        separator = separators[-1]
        new_separators: List[str] = []
        for i, sep in enumerate(separators):
            sep_pattern = sep if self._is_separator_regex else re.escape(sep)
            if sep == "":
                separator = sep
                break
            if re.search(sep_pattern, text):
                separator = sep
                new_separators = separators[i + 1 :]
                break

        sep_pattern = separator if self._is_separator_regex else re.escape(separator)
        splits = _split_text_with_regex(text, sep_pattern, self._keep_separator)

        good_splits: List[str] = []
        merge_separator = "" if self._keep_separator else separator
        for split in splits:
            if self._length_function(split) < self._chunk_size:
                good_splits.append(split)
            else:
                if good_splits:
                    final_chunks.extend(self._merge_splits(good_splits, merge_separator))
                    good_splits = []
                if not new_separators:
                    final_chunks.append(split)
                else:
                    final_chunks.extend(self._split_text(split, new_separators))
        if good_splits:
            final_chunks.extend(self._merge_splits(good_splits, merge_separator))
        return final_chunks

    def split_text(self, text: str) -> List[str]:
        return self._split_text(text, self._separators)


def _embed_texts(
    texts: Sequence[str],
    *,
    backend: str,
    model_name: str,
) -> Tuple[np.ndarray, str, Optional[str]]:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32), backend, None
    if backend in {"sentence-transformers", "auto"}:
        try:
            from sentence_transformers import SentenceTransformer

            model = _SENTENCE_TRANSFORMER_CACHE.get(model_name)
            if model is None:
                try:
                    model = SentenceTransformer(model_name, local_files_only=True)
                except TypeError:
                    model = SentenceTransformer(model_name)
                _SENTENCE_TRANSFORMER_CACHE[model_name] = model
            embeddings = model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
            return np.asarray(embeddings, dtype=np.float32), "sentence-transformers", None
        except Exception as exc:
            if backend == "sentence-transformers":
                return _embed_texts_tfidf(texts, f"sentence-transformers failed: {exc}")
    return _embed_texts_tfidf(texts, None)


def _embed_texts_tfidf(texts: Sequence[str], warning: Optional[str]) -> Tuple[np.ndarray, str, Optional[str]]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(texts)
    normalized = normalize(matrix).toarray().astype(np.float32)
    return normalized, "tfidf", warning


def _chroma_similarity_matrix(
    sentences: Sequence[str],
    *,
    embedding_backend: str,
    embedding_model: str,
) -> Tuple[np.ndarray, str, Optional[str]]:
    if embedding_backend == "tfidf":
        embeddings, used, warning = _embed_texts(sentences, backend=embedding_backend, model_name=embedding_model)
        return np.dot(embeddings, embeddings.T), used, warning

    batch_size = 500
    embedding_matrix: Optional[np.ndarray] = None
    backend_used = embedding_backend
    warning: Optional[str] = None
    for i in range(0, len(sentences), batch_size):
        embeddings, used, batch_warning = _embed_texts(
            sentences[i : i + batch_size],
            backend=embedding_backend,
            model_name=embedding_model,
        )
        backend_used = used
        warning = warning or batch_warning
        embedding_matrix = embeddings if embedding_matrix is None else np.concatenate((embedding_matrix, embeddings), axis=0)
    assert embedding_matrix is not None
    return np.dot(embedding_matrix, embedding_matrix.T), backend_used, warning


def _chroma_calculate_reward(matrix: np.ndarray, start: int, end: int) -> float:
    return float(np.sum(matrix[start : end + 1, start : end + 1]))


def _chroma_optimal_segmentation(matrix: np.ndarray, max_cluster_size: int) -> List[Tuple[int, int]]:
    if matrix.shape[0] == 0:
        return []
    if matrix.shape[0] == 1:
        return [(0, 0)]

    off_diagonal = matrix[np.triu_indices(matrix.shape[0], k=1)]
    mean_value = float(np.mean(off_diagonal)) if off_diagonal.size else 0.0
    matrix = matrix - mean_value
    np.fill_diagonal(matrix, 0)

    n = matrix.shape[0]
    dp = np.zeros(n)
    segmentation = np.zeros(n, dtype=int)
    for i in range(n):
        for size in range(1, max_cluster_size + 1):
            if i - size + 1 >= 0:
                reward = _chroma_calculate_reward(matrix, i - size + 1, i)
                adjusted_reward = reward
                if i - size >= 0:
                    adjusted_reward += dp[i - size]
                if adjusted_reward > dp[i]:
                    dp[i] = adjusted_reward
                    segmentation[i] = i - size + 1

    clusters: List[Tuple[int, int]] = []
    i = n - 1
    while i >= 0:
        start = int(segmentation[i])
        clusters.append((start, i))
        i = start - 1
    clusters.reverse()
    return clusters


def _region_span_to_source_spans(region: TextRegion, start: int, end: int) -> List[Tuple[int, int]]:
    source_positions = [pos for pos in region.char_map[start:end] if pos is not None]
    if not source_positions:
        return []
    intervals = [(pos, pos + 1) for pos in source_positions]
    return _merge_intervals(intervals)


def _is_heading_only_text(text: str) -> bool:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return False
    if any(line.startswith("[Section:") for line in lines):
        return True
    for line in lines:
        if not _is_heading(line):
            return False
        content = _clean_heading(line)
        if len(content) > 120 or re.search(r"[.!?:;|]", content):
            return False
    return True


def _split_region_with_chroma_offsets(
    region: TextRegion,
    *,
    min_chunk_tokens: int,
) -> List[Tuple[str, List[Tuple[int, int]]]]:
    splitter = ChromaRecursiveTokenChunker(
        chunk_size=min_chunk_tokens,
        chunk_overlap=0,
        length_function=openai_token_count,
        separators=["\n\n", "\n", ".", "?", "!", " ", ""],
    )
    parts = splitter.split_text(region.text)
    mapped: List[Tuple[str, List[Tuple[int, int]]]] = []
    cursor = 0
    for part in parts:
        if not part:
            continue
        start = region.text.find(part, cursor)
        if start < 0:
            start = region.text.find(part)
        if start < 0:
            continue
        end = start + len(part)
        spans = _region_span_to_source_spans(region, start, end)
        if spans:
            mapped.append((part, spans))
            cursor = end
    return mapped


def _merge_heading_only_clusters(
    clusters: Sequence[Tuple[int, int]],
    sentences: Sequence[str],
) -> List[Tuple[int, int]]:
    merged: List[Tuple[int, int]] = []
    pending_start: Optional[int] = None
    for start, end in clusters:
        text = " ".join(sentences[start : end + 1])
        if _is_heading_only_text(text):
            pending_start = start if pending_start is None else pending_start
            continue

        if pending_start is not None:
            start = pending_start
            pending_start = None
        merged.append((start, end))

    if pending_start is not None:
        if merged:
            prev_start, _ = merged[-1]
            merged[-1] = (prev_start, clusters[-1][1])
        else:
            merged.append((pending_start, clusters[-1][1]))
    return merged


def _chroma_cluster_region(
    region: TextRegion,
    *,
    max_chunk_tokens: int,
    min_chunk_tokens: int,
    embedding_backend: str,
    embedding_model: str,
) -> Tuple[List[Tuple[str, List[Tuple[int, int]]]], str, Optional[str]]:
    min_chunks = _split_region_with_chroma_offsets(region, min_chunk_tokens=min_chunk_tokens)
    sentences = [text for text, _ in min_chunks]
    if not sentences:
        return [], embedding_backend, None
    if len(sentences) == 1:
        return [(sentences[0], min_chunks[0][1])], embedding_backend, None

    matrix, backend_used, warning = _chroma_similarity_matrix(
        sentences,
        embedding_backend=embedding_backend,
        embedding_model=embedding_model,
    )
    max_cluster = max(1, max_chunk_tokens // min_chunk_tokens)
    clusters = _chroma_optimal_segmentation(matrix, max_cluster)
    clusters = _merge_heading_only_clusters(clusters, sentences)

    chunks: List[Tuple[str, List[Tuple[int, int]]]] = []
    for start, end in clusters:
        text = " ".join(sentences[start : end + 1])
        spans: List[Tuple[int, int]] = []
        for _, part_spans in min_chunks[start : end + 1]:
            spans.extend(part_spans)
        chunks.append((text, _merge_intervals(spans)))
    return chunks, backend_used, warning


def _unit_text_for_embedding(unit: SourceUnit) -> str:
    if unit.heading and not unit.text.lstrip().startswith("#"):
        return f"{unit.heading}\n{unit.text}"
    return unit.text


def _chunk_text_for_group(group: Sequence[SourceUnit]) -> str:
    parts: List[str] = []
    emitted_heading = ""
    for unit in group:
        text = unit.text.strip()
        if not text:
            continue
        if text.lstrip().startswith("#"):
            parts.append(text)
            emitted_heading = unit.heading
            continue
        if unit.heading and unit.heading != emitted_heading:
            parts.append(f"[Section: {unit.heading}]")
            emitted_heading = unit.heading
        parts.append(text)
    return "\n\n".join(parts)


def embed_units(
    units: Sequence[SourceUnit],
    *,
    backend: str,
    model_name: str,
) -> Tuple[np.ndarray, str, Optional[str]]:
    texts = [_unit_text_for_embedding(unit) for unit in units]
    if not texts:
        return np.zeros((0, 0), dtype=np.float32), backend, None

    if backend in {"sentence-transformers", "auto"}:
        try:
            from sentence_transformers import SentenceTransformer

            try:
                model = SentenceTransformer(model_name, local_files_only=True)
            except TypeError:
                model = SentenceTransformer(model_name)
            embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return np.asarray(embeddings, dtype=np.float32), "sentence-transformers", None
        except Exception as exc:
            if backend == "sentence-transformers":
                return _embed_units_tfidf(texts, f"sentence-transformers failed: {exc}")

    return _embed_units_tfidf(texts, None)


def _embed_units_tfidf(texts: Sequence[str], warning: Optional[str]) -> Tuple[np.ndarray, str, Optional[str]]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize

    matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(texts)
    normalized = normalize(matrix).toarray().astype(np.float32)
    return normalized, "tfidf", warning


def _group_score(prefix: np.ndarray, start: int, end: int) -> float:
    total = prefix[end, end] - prefix[start, end] - prefix[end, start] + prefix[start, start]
    size = max(1, end - start)
    return float(total / math.sqrt(size))


def pack_units_global(
    units: Sequence[SourceUnit],
    embeddings: np.ndarray,
    *,
    max_chunk_chars: int,
) -> List[List[SourceUnit]]:
    if not units:
        return []
    if len(units) == 1:
        return [[units[0]]]

    sim = np.matmul(embeddings, embeddings.T)
    sim = np.nan_to_num(sim, nan=0.0, posinf=0.0, neginf=0.0)
    sim = np.maximum(sim, 0.0)
    prefix = np.zeros((len(units) + 1, len(units) + 1), dtype=np.float64)
    prefix[1:, 1:] = sim.cumsum(axis=0).cumsum(axis=1)

    dp = [-float("inf")] * (len(units) + 1)
    back = [-1] * (len(units) + 1)
    dp[0] = 0.0
    for end in range(1, len(units) + 1):
        total_chars = 0
        for start in range(end - 1, -1, -1):
            total_chars += len(units[start].text)
            if total_chars > max_chunk_chars and start < end - 1:
                break
            score = dp[start] + _group_score(prefix, start, end)
            if score > dp[end]:
                dp[end] = score
                back[end] = start

    groups: List[List[SourceUnit]] = []
    end = len(units)
    while end > 0:
        start = back[end]
        if start < 0:
            start = end - 1
        groups.append(list(units[start:end]))
        end = start
    groups.reverse()
    return groups


def build_global_text_pack_chunks(
    docs: Sequence[CorpusDoc],
    *,
    max_chunk_chars: int,
    max_unit_chars: int,
    max_table_chars: int,
    chroma_max_chunk_tokens: int,
    chroma_min_chunk_tokens: int,
    embedding_backend: str,
    embedding_model: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    strategy = "chroma_cluster_semantic"
    chunks: List[Dict[str, Any]] = []
    all_regions: List[TextRegion] = []
    tables_by_doc: Dict[str, List[TableBlock]] = {}
    doc_path_by_id = {doc.doc_id: doc.path for doc in docs}

    for doc in docs:
        regions, tables = extract_text_regions_and_tables(doc)
        all_regions.extend(regions)
        tables_by_doc[doc.doc_id] = tables

    embedding_backend_used = embedding_backend
    embedding_warning: Optional[str] = None
    for doc in docs:
        doc_regions = [region for region in all_regions if region.doc_id == doc.doc_id]
        text_chunk_idx = 0
        for region_idx, region in enumerate(doc_regions):
            region_chunks, used, warning = _chroma_cluster_region(
                region,
                max_chunk_tokens=chroma_max_chunk_tokens,
                min_chunk_tokens=chroma_min_chunk_tokens,
                embedding_backend=embedding_backend,
                embedding_model=embedding_model,
            )
            embedding_backend_used = used
            embedding_warning = embedding_warning or warning
            for chunk_text, merged_spans in region_chunks:
                if not chunk_text.strip() or not merged_spans:
                    continue
                chunks.append(
                    _normalize_chunk(
                        chunk_id=f"{doc.doc_id}_chroma_cluster_text_{text_chunk_idx}",
                        doc_id=doc.doc_id,
                        text=chunk_text,
                        source=str(doc.path),
                        start_char=min(start for start, _ in merged_spans),
                        end_char=max(end for _, end in merged_spans),
                        strategy=strategy,
                        chunk_type="chroma_cluster_text",
                        extra_metadata={
                            "region_index": region_idx,
                            "heading": region.heading,
                            "heading_stack": list(region.heading_stack),
                            "max_chunk_tokens": chroma_max_chunk_tokens,
                            "min_chunk_tokens": chroma_min_chunk_tokens,
                            "char_spans": [
                                {"start_char": start, "end_char": end}
                                for start, end in merged_spans
                            ],
                        },
                    )
                )
                text_chunk_idx += 1

    table_chunk_index = 0
    for doc_id, tables in tables_by_doc.items():
        for table in tables:
            table_chunks = _table_chunks(
                table,
                doc_path=doc_path_by_id[doc_id],
                strategy=strategy,
                max_table_chars=max_table_chars,
                chunk_index_start=table_chunk_index,
            )
            table_chunk_index += len(table_chunks)
            chunks.extend(table_chunks)

    stats = {
        "text_regions": len(all_regions),
        "table_blocks": sum(len(tables) for tables in tables_by_doc.values()),
        "chroma_max_chunk_tokens": chroma_max_chunk_tokens,
        "chroma_min_chunk_tokens": chroma_min_chunk_tokens,
        "embedding_backend": embedding_backend_used,
        "embedding_model": embedding_model if embedding_backend_used == "sentence-transformers" else None,
        "embedding_warning": embedding_warning,
    }
    return [chunk for chunk in chunks if chunk["text"].strip()], stats


def _merge_intervals(intervals: Iterable[Tuple[int, int]]) -> List[Tuple[int, int]]:
    sorted_intervals = sorted((start, end) for start, end in intervals if start is not None and end is not None and end > start)
    merged: List[Tuple[int, int]] = []
    for start, end in sorted_intervals:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _interval_length(intervals: Sequence[Tuple[int, int]]) -> int:
    return sum(end - start for start, end in intervals)


def _overlap_length(a: Sequence[Tuple[int, int]], b: Sequence[Tuple[int, int]]) -> int:
    i = j = 0
    overlap = 0
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if end > start:
            overlap += end - start
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return overlap


def evaluate_strategy(
    *,
    strategy_name: str,
    chunks: Sequence[Dict[str, Any]],
    eval_rows: Sequence[Dict[str, Any]],
    k_values: Sequence[int],
    retriever_type: str,
    output_dir: Path,
    production_config: Dict[str, Any],
) -> Dict[str, Any]:
    retriever_name = (retriever_type or "hybrid").strip().lower()
    if retriever_name == "bm25":
        retriever = SimpleBM25Retriever()
    elif retriever_name == "dense":
        retriever = SimpleDenseRetriever()
    elif retriever_name == "hybrid":
        retriever = SimpleHybridRetriever()
    elif retriever_name == "production-hybrid":
        retriever = ProductionTextSearchAdapter(
            output_dir=output_dir,
            strategy_name=strategy_name,
            base_config=production_config,
        )
    else:
        raise ValueError(f"Unsupported retriever type: {retriever_type}")
    retriever.index_documents(list(chunks))

    metric_acc = {
        k: {
            "samples": 0,
            "hits": 0,
            "recall_sum": 0.0,
            "precision_sum": 0.0,
            "iou_sum": 0.0,
            "retrieved_chars_sum": 0,
        }
        for k in k_values
    }
    details: List[Dict[str, Any]] = []

    try:
        for row in eval_rows:
            query = str(row["query"])
            relevant_doc_id = str(row["doc_id"])
            relevant_start = int(row["start_char"])
            relevant_end = int(row["end_char"])
            relevant_len = max(1, relevant_end - relevant_start)
            results = retriever.search(query, top_k=max(k_values))

            sample_detail: Dict[str, Any] = {
                "sample_id": row.get("sample_id"),
                "query": query,
                "doc_id": relevant_doc_id,
                "start_char": relevant_start,
                "end_char": relevant_end,
                "top_results": [],
                "metrics": {},
            }
            for result in results:
                metadata = result.get("metadata") or {}
                char_spans = _metadata_spans(result)
                sample_detail["top_results"].append(
                    {
                        "rank": result.get("rank"),
                        "id": result.get("id"),
                        "score": result.get("score"),
                        "doc_id": metadata.get("doc_id", result.get("doc_id")),
                        "chunk_type": metadata.get("chunk_type"),
                        "start_char": metadata.get("start_char"),
                        "end_char": metadata.get("end_char"),
                        "char_spans": [
                            {"start_char": start, "end_char": end}
                            for start, end in char_spans
                        ],
                        "text_preview": (result.get("text") or "")[:220],
                    }
                )

            for k in k_values:
                top_results = results[:k]
                intervals_by_doc: Dict[str, List[Tuple[int, int]]] = {}
                for result in top_results:
                    metadata = result.get("metadata") or {}
                    doc_id = str(metadata.get("doc_id") or result.get("doc_id") or "")
                    spans = _metadata_spans(result)
                    if not spans:
                        continue
                    intervals_by_doc.setdefault(doc_id, []).extend(spans)

                retrieved_len = 0
                for intervals in intervals_by_doc.values():
                    retrieved_len += _interval_length(_merge_intervals(intervals))
                relevant_intervals = [(relevant_start, relevant_end)]
                same_doc_intervals = _merge_intervals(intervals_by_doc.get(relevant_doc_id, []))
                overlap = _overlap_length(same_doc_intervals, relevant_intervals)
                union = retrieved_len + relevant_len - overlap

                recall = overlap / relevant_len
                precision = overlap / retrieved_len if retrieved_len else 0.0
                iou = overlap / union if union else 0.0
                hit = overlap > 0

                acc = metric_acc[k]
                acc["samples"] += 1
                acc["hits"] += int(hit)
                acc["recall_sum"] += recall
                acc["precision_sum"] += precision
                acc["iou_sum"] += iou
                acc["retrieved_chars_sum"] += retrieved_len
                sample_detail["metrics"][f"@{k}"] = {
                    "hit": hit,
                    "span_recall": recall,
                    "span_precision": precision,
                    "span_iou": iou,
                    "retrieved_chars": retrieved_len,
                    "overlap_chars": overlap,
                }
            details.append(sample_detail)
    finally:
        if isinstance(retriever, ProductionTextSearchAdapter):
            retriever.cleanup()

    metrics: Dict[str, Any] = {}
    for k, acc in metric_acc.items():
        samples = max(1, acc["samples"])
        metrics[f"@{k}"] = {
            "samples": acc["samples"],
            "hit_rate": acc["hits"] / samples,
            "hits": acc["hits"],
            "mean_span_recall": acc["recall_sum"] / samples,
            "mean_span_precision": acc["precision_sum"] / samples,
            "mean_span_iou": acc["iou_sum"] / samples,
            "mean_retrieved_chars": acc["retrieved_chars_sum"] / samples,
        }

    return {
        "strategy": strategy_name,
        "metrics": metrics,
        "details": details,
    }


def summarize_chunks(chunks: Sequence[Dict[str, Any]], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    type_counts: Dict[str, int] = {}
    lengths: List[int] = []
    exact_offsets = 0
    for chunk in chunks:
        metadata = chunk.get("metadata") or {}
        chunk_type = str(metadata.get("chunk_type") or "unknown")
        type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
        lengths.append(len(str(chunk.get("text") or "")))
        start, end = _metadata_span(chunk)
        if start is not None and end is not None:
            exact_offsets += 1
    stats = {
        "chunks": len(chunks),
        "chunk_type_counts": type_counts,
        "avg_chunk_chars": sum(lengths) / len(lengths) if lengths else 0,
        "min_chunk_chars": min(lengths) if lengths else 0,
        "max_chunk_chars": max(lengths) if lengths else 0,
        "chunks_with_offsets": exact_offsets,
    }
    if extra:
        stats.update(extra)
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare production chunking with global semantic packing.")
    parser.add_argument("--stage4-dir", required=True)
    parser.add_argument("--eval-jsonl", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-documents", type=int, default=None)
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument(
        "--chunk-source",
        choices=["markdown", "prebuilt"],
        default="markdown",
        help=(
            "markdown compares strategies from the same canonical stage4 markdown source. "
            "prebuilt compares current parser-built production chunks against markdown-built global chunks."
        ),
    )
    parser.add_argument("--global-max-chars", type=int, default=1000)
    parser.add_argument("--global-unit-max-chars", type=int, default=420)
    parser.add_argument("--global-table-max-chars", type=int, default=1000)
    parser.add_argument("--chroma-max-chunk-tokens", type=int, default=400)
    parser.add_argument("--chroma-min-chunk-tokens", type=int, default=50)
    parser.add_argument("--embedding-backend", choices=["auto", "sentence-transformers", "tfidf"], default="auto")
    parser.add_argument("--embedding-model", default="all-MiniLM-L6-v2")
    parser.add_argument(
        "--retriever",
        choices=["bm25", "dense", "hybrid", "production-hybrid"],
        default="production-hybrid",
        help=(
            "production-hybrid indexes each strategy into temporary Qdrant/BM25 "
            "state and retrieves through TextSearchService, matching run_api.py text retrieval."
        ),
    )
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 3, 5])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    stage4_dir = Path(args.stage4_dir).resolve()
    eval_jsonl = Path(args.eval_jsonl).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    docs = discover_corpus_docs(stage4_dir, max_documents=args.max_documents)
    eval_rows = _read_jsonl(eval_jsonl)
    if not docs:
        raise SystemExit(f"No markdown docs found under {stage4_dir}")
    if not eval_rows:
        raise SystemExit(f"No eval rows found in {eval_jsonl}")

    if args.chunk_source == "markdown":
        baseline_name = "recursive_markdown"
        baseline_chunks = build_markdown_recursive_chunks(
            docs,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
    else:
        baseline_name = "production_prebuilt"
        baseline_chunks = build_production_chunks(
            stage4_dir,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

    global_chunks, global_extra = build_global_text_pack_chunks(
        docs,
        max_chunk_chars=args.global_max_chars,
        max_unit_chars=args.global_unit_max_chars,
        max_table_chars=args.global_table_max_chars,
        chroma_max_chunk_tokens=args.chroma_max_chunk_tokens,
        chroma_min_chunk_tokens=args.chroma_min_chunk_tokens,
        embedding_backend=args.embedding_backend,
        embedding_model=args.embedding_model,
    )

    strategies = {
        baseline_name: {
            "chunks": baseline_chunks,
            "chunk_stats": summarize_chunks(baseline_chunks),
        },
        "chroma_cluster_semantic": {
            "chunks": global_chunks,
            "chunk_stats": summarize_chunks(global_chunks, global_extra),
        },
    }

    production_config = merged_runtime_settings(load_yaml_config())
    results: Dict[str, Any] = {}
    for name, payload in strategies.items():
        results[name] = evaluate_strategy(
            strategy_name=name,
            chunks=payload["chunks"],
            eval_rows=eval_rows,
            k_values=args.top_k,
            retriever_type=args.retriever,
            output_dir=output_dir,
            production_config=production_config,
        )

    report = {
        "inputs": {
            "stage4_dir": str(stage4_dir),
            "eval_jsonl": str(eval_jsonl),
            "documents": [{"doc_id": doc.doc_id, "path": str(doc.path), "chars": len(doc.text)} for doc in docs],
            "eval_samples": len(eval_rows),
            "chunk_source": args.chunk_source,
            "retriever": args.retriever,
            "retriever_note": (
                "production-hybrid uses TextSearchService.search_hybrid with temporary Qdrant "
                "collection plus temporary persisted BM25/doc snapshots."
                if args.retriever == "production-hybrid"
                else "local in-memory retriever"
            ),
            "metrics": "character-span overlap proxy for token-level recall/precision/IoU",
        },
        "settings": {
            "production_chunk_size": args.chunk_size,
            "production_chunk_overlap": args.chunk_overlap,
            "global_max_chars": args.global_max_chars,
            "global_unit_max_chars": args.global_unit_max_chars,
            "global_table_max_chars": args.global_table_max_chars,
            "chroma_max_chunk_tokens": args.chroma_max_chunk_tokens,
            "chroma_min_chunk_tokens": args.chroma_min_chunk_tokens,
            "embedding_backend_requested": args.embedding_backend,
            "embedding_model": args.embedding_model,
            "top_k": args.top_k,
        },
        "strategies": {
            name: {
                "chunk_stats": payload["chunk_stats"],
                "metrics": results[name]["metrics"],
            }
            for name, payload in strategies.items()
        },
        "details": {name: results[name]["details"] for name in strategies},
    }

    report_path = output_dir / "strategy_eval_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nWrote report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
