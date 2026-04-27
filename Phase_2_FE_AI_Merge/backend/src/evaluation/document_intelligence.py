"""Document Intelligence Evaluation framework.

The framework writes one phase report:

* e2e_qa_eval_report.json

It intentionally removes standalone chunk/retrieval metrics. Retrieval quality
is observed only through end-to-end QA judgment.
"""

from __future__ import annotations

import abc
import asyncio
import base64
import json
import mimetypes
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.core.paths import load_yaml_config, merged_runtime_settings
from src.generation.providers.bedrock_provider import BedrockProvider
from src.generation.providers.openai_provider import OpenAIProvider

_JSON_BLOCK_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)
_TABLE_RE = re.compile(r"\[START_TABLE_CONTENT\](.*?)\[END_TABLE_CONTENT\]", re.DOTALL)
_IMAGE_RE = re.compile(r"\[START_IMAGE_PATH\]\s*(.*?)\s*\[END_IMAGE_PATH\]", re.DOTALL)

_CORRECTNESS_LABELS = {"correct", "partially_correct", "incorrect"}
_FAITHFULNESS_LABELS = {"faithful", "partially_faithful", "hallucinated"}
_ANSWER_SUPPORT_LABELS = {"fully_supported", "partially_supported", "not_supported"}


def _build_llm_provider(provider: str, model: Optional[str]):
    provider_name = (provider or "openai").strip().lower()
    if provider_name == "openai":
        return OpenAIProvider(
            api_key=os.getenv("OPENAI_API_KEY"),
            default_model=model or os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
        )
    if provider_name in {"bedrock", "aws_bedrock"}:
        return BedrockProvider(
            access_key=os.getenv("AWS_LLM_ACCESS_KEY_ID"),
            secret_key=os.getenv("AWS_LLM_SECRET_ACCESS_KEY"),
            region=os.getenv("AWS_LLM_REGION") or os.getenv("AWS_REGION") or "us-west-2",
            default_model=model or os.getenv("AWS_LLM_MODEL") or os.getenv("BEDROCK_MODEL_ID") or "mistral.mistral-small-2402-v1:0",
        )
    raise ValueError(f"Unsupported provider: {provider}")


@dataclass(frozen=True)
class DocumentIntelligenceEvalConfig:
    input_path: str
    parsed_root: str
    output_dir: str
    phase: str = "all"
    questions_per_section: int = 10
    max_documents: Optional[int] = None
    max_sections_per_document: Optional[int] = None
    top_k: int = 10
    retriever_type: str = "hybrid"
    provider: str = "openai"
    model: Optional[str] = None
    user_id: Optional[str] = None


@dataclass(frozen=True)
class SectionSample:
    doc_id: str
    section_id: str
    section_index: int
    heading_text: str
    heading_level: int
    heading_breadcrumb: List[str]
    source_text: str


@dataclass(frozen=True)
class DocumentEvalSample:
    doc_id: str
    doc_type: str
    parsed_tree_path: str
    rag_ready_dir: str
    source_document_path: Optional[str]
    source_markdown_path: Optional[str]
    sections: List[SectionSample]


@dataclass(frozen=True)
class TableElementSample:
    doc_id: str
    section_id: str
    table_id: str
    parsed_table: str
    original_table_input: str
    input_mode: str
    original_table_image_path: Optional[str] = None
    original_table_image_input: Optional[Dict[str, Any]] = None
    source_page_match_score: Optional[float] = None


@dataclass(frozen=True)
class ImageElementSample:
    doc_id: str
    section_id: str
    image_id: str
    extracted_image_path: str
    parsed_image_metadata: Dict[str, Any]
    extracted_image_input: Optional[Dict[str, Any]]
    original_image_input: Optional[Dict[str, Any]]
    original_image_input_mode: str
    original_image_path: Optional[str]
    image_load_status: str
    source_page_match_score: Optional[float] = None


@dataclass(frozen=True)
class SourceReference:
    source_path: Optional[str]
    pdf_path: Optional[Path]
    page_paths: List[Path]
    status: str


@dataclass(frozen=True)
class QAEvalItem:
    doc_id: str
    section_id: str
    question_index: int
    question: str
    reference_answer: str
    source_section_text: str
    target_section_key: str = ""
    target_chunk_ids: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class QAEvalResult:
    item: QAEvalItem
    retrieved_context: List[Dict[str, Any]]
    generated_answer: str
    judge_result: Dict[str, str]
    retrieval_trace: Dict[str, Any]
    failure_category: str = ""


@dataclass(frozen=True)
class DocumentQAEvalResult:
    doc_id: str
    results: List[QAEvalResult]
    distributions: Dict[str, Dict[str, int]]
    retrieval_trace_summary: Dict[str, int]
    failed_questions_by_section: Dict[str, List[Dict[str, Any]]]


@dataclass
class LocalCorpusChunk:
    doc_id: str
    chunk_id: str
    text: str
    source: str
    metadata: Dict[str, Any]
    chunk_index: int
    raw_section_key: str = ""
    mapped_section_id: str = ""
    mapped_section_key: str = ""


@dataclass(frozen=True)
class LocalCorpusIndex:
    doc_ids: List[str]
    doc_dirs: List[str]
    chunks: List[LocalCorpusChunk]


class BaseDocumentIntelligenceJudge(abc.ABC):
    @abc.abstractmethod
    async def generate_qa_pairs(self, section: SectionSample, question_count: int) -> List[Dict[str, str]]:
        raise NotImplementedError

    @abc.abstractmethod
    async def judge_qa(
        self,
        *,
        question: str,
        reference_answer: str,
        retrieved_context: Sequence[Dict[str, Any]],
        generated_answer: str,
    ) -> Dict[str, str]:
        raise NotImplementedError


class LLMDocumentIntelligenceJudge(BaseDocumentIntelligenceJudge):
    """LLM-backed judge for E2E QA."""

    def __init__(self, provider: str = "openai", model: Optional[str] = None):
        self.provider_name = (provider or "openai").strip().lower()
        self.model = (model or "").strip() or None
        self._provider = _build_llm_provider(self.provider_name, self.model)

    async def _complete_text(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 1800) -> str:
        return str(
            await self._provider.create(
                instructions=system_prompt,
                input=user_prompt,
                model=self.model,
                temperature=0.0,
                max_tokens=max_tokens,
            )
            or ""
        )

    async def _complete_multimodal(
        self,
        system_prompt: str,
        user_text: str,
        images: Sequence[Dict[str, Any]],
        *,
        max_tokens: int = 1800,
    ) -> str:
        content: List[Dict[str, Any]] = [{"type": "input_text", "text": user_text}]
        for image in images:
            data_url = image.get("data_url")
            if data_url:
                content.append({"type": "input_image", "image_url": {"url": data_url}})
        messages = [{"role": "user", "content": content}]
        return str(
            await self._provider.create(
                instructions=system_prompt,
                input=messages,
                model=self.model,
                temperature=0.0,
                max_tokens=max_tokens,
            )
            or ""
        )

    async def generate_qa_pairs(self, section: SectionSample, question_count: int) -> List[Dict[str, str]]:
        system_prompt = (
            "You generate factual QA pairs for document evaluation. Use only the source section. "
            "Return JSON only."
        )
        user_prompt = f"""
Generate exactly {question_count} factual questions and reference answers from this source section.

Rules:
- Use only facts explicitly present in the source section.
- Avoid opinion/open-ended questions.
- Each reference answer must be answerable from the source section.
- Return JSON only:
{{"items": [{{"question": "...", "reference_answer": "..."}}]}}

Section heading: {section.heading_text}
Section breadcrumb: {" > ".join(section.heading_breadcrumb)}
Source section:
{section.source_text}
""".strip()
        payload = _json_or_empty(await self._complete_text(system_prompt, user_prompt, max_tokens=2400))
        items = payload.get("items") if isinstance(payload, dict) else []
        out: List[Dict[str, str]] = []
        for item in items or []:
            q = str(item.get("question", "")).strip()
            a = str(item.get("reference_answer", "")).strip()
            if q and a:
                out.append({"question": q, "reference_answer": a})
        return out[:question_count]

    async def judge_qa(
        self,
        *,
        question: str,
        reference_answer: str,
        retrieved_context: Sequence[Dict[str, Any]],
        generated_answer: str,
    ) -> Dict[str, str]:
        system_prompt = (
            "You are an end-to-end QA evaluator. Judge one question at a time. "
            "Only output correctness, faithfulness, answer_support, and judge_rationale. Return JSON only."
        )
        context_text = "\n\n".join(
            f"[{idx + 1}] id={ctx.get('id', '')}\n{ctx.get('text') or ctx.get('full_text') or ''}"
            for idx, ctx in enumerate(retrieved_context)
        )
        user_prompt = f"""
Judge this single QA result.

Question:
{question}

Reference answer:
{reference_answer}

Retrieved context:
{context_text}

Generated answer:
{generated_answer}

Return only:
{{
  "correctness": "correct | partially_correct | incorrect",
  "faithfulness": "faithful | partially_faithful | hallucinated",
  "answer_support": "fully_supported | partially_supported | not_supported",
  "judge_rationale": "short explanation"
}}
""".strip()
        return _normalize_qa_result(_json_or_empty(await self._complete_text(system_prompt, user_prompt, max_tokens=1600)))


class BaseQAExecutor(abc.ABC):
    @abc.abstractmethod
    async def run(self, question: str) -> Tuple[List[Dict[str, Any]], str]:
        raise NotImplementedError


class SearchOrchestratorQAExecutor(BaseQAExecutor):
    """Runs the app's retrieval + generation path for E2E QA."""

    def __init__(
        self,
        yaml_config: Dict[str, Any],
        *,
        top_k: int,
        retriever_type: str,
        user_id: Optional[str] = None,
    ):
        self.yaml_config = yaml_config
        self.top_k = top_k
        self.retriever_type = retriever_type
        self.user_id = user_id

    async def run(self, question: str) -> Tuple[List[Dict[str, Any]], str]:
        from app.services.search_orchestrator import SearchOrchestrator

        out = SearchOrchestrator(self.yaml_config, user_id=self.user_id).run(
            question,
            top_k=self.top_k,
            retriever_type=self.retriever_type,
            include_images=False,
            mode="retrieval_generation",
            search_scope="text",
        )
        retrieved = list(out.get("text_results") or [])
        return retrieved, str(out.get("answer") or "")


class LocalCorpusQAExecutor(BaseQAExecutor):
    """Runs isolated local-corpus retrieval + generation for E2E QA."""

    def __init__(
        self,
        corpus: LocalCorpusIndex,
        *,
        top_k: int,
        provider: str,
        model: Optional[str],
    ):
        from src.retrieval.rag_retrievers import SimpleBM25Retriever

        self.corpus = corpus
        self.top_k = top_k
        self.provider_name = (provider or "openai").strip().lower()
        self.model = (model or "").strip() or None
        self._provider = _build_llm_provider(self.provider_name, self.model)
        self._retriever = SimpleBM25Retriever()
        self._doc_map: Dict[str, Dict[str, Any]] = {}

        documents: List[Dict[str, Any]] = []
        for chunk in corpus.chunks:
            metadata = dict(chunk.metadata)
            metadata["doc_id"] = chunk.doc_id
            metadata["section_key"] = chunk.mapped_section_key or chunk.raw_section_key
            metadata["mapped_section_id"] = chunk.mapped_section_id
            metadata["mapped_section_key"] = chunk.mapped_section_key
            metadata["chunk_index"] = chunk.chunk_index
            doc = {
                "id": chunk.chunk_id,
                "text": chunk.text,
                "source": chunk.source,
                "metadata": metadata,
            }
            documents.append(doc)
            self._doc_map[chunk.chunk_id] = doc
        self._retriever.index_documents(documents)

    async def _complete_text(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 1200) -> str:
        return str(
            await self._provider.create(
                instructions=system_prompt,
                input=user_prompt,
                model=self.model,
                temperature=0.0,
                max_tokens=max_tokens,
            )
            or ""
        )

    async def _generate_answer(self, question: str, retrieved_context: Sequence[Dict[str, Any]]) -> str:
        if not retrieved_context:
            return ""
        system_prompt = (
            "You answer questions using only the retrieved context. "
            "If the context is insufficient, say exactly: Insufficient information in retrieved context."
        )
        context_text = "\n\n".join(
            f"[{idx + 1}] id={ctx.get('id', '')}\n{ctx.get('full_text') or ctx.get('text') or ''}"
            for idx, ctx in enumerate(retrieved_context)
        )
        user_prompt = f"""
Answer this question using only the retrieved context.

Question:
{question}

Retrieved context:
{context_text}

Rules:
- Do not use outside knowledge.
- Keep the answer concise.
- If the answer is not in the retrieved context, say exactly: Insufficient information in retrieved context.
""".strip()
        return (await self._complete_text(system_prompt, user_prompt)).strip()

    async def run(self, question: str) -> Tuple[List[Dict[str, Any]], str]:
        raw = self._retriever.search(question, self.top_k)
        retrieved: List[Dict[str, Any]] = []
        for item in raw:
            base = self._doc_map.get(str(item.get("id") or ""))
            full_text = str((base or {}).get("text") or item.get("text") or "")
            metadata = dict((base or {}).get("metadata") or item.get("metadata") or {})
            retrieved.append(
                {
                    "id": item.get("id"),
                    "source": item.get("source") or (base or {}).get("source"),
                    "score": item.get("score"),
                    "rank": item.get("rank"),
                    "retrieval_type": "local_bm25",
                    "text": full_text,
                    "full_text": full_text,
                    "metadata": metadata,
                }
            )
        generated_answer = await self._generate_answer(question, retrieved)
        return retrieved, generated_answer


class DocumentIntelligenceRunner:
    def __init__(
        self,
        config: DocumentIntelligenceEvalConfig,
        judge: BaseDocumentIntelligenceJudge,
        qa_executor: Optional[BaseQAExecutor] = None,
    ):
        self.config = config
        self.judge = judge
        self.qa_executor = qa_executor

    async def run(self) -> Dict[str, Any]:
        samples = discover_document_samples(self.config)
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        phase = self.config.phase
        if phase not in {"all", "e2e_qa"}:
            raise ValueError(f"Unsupported document intelligence eval phase: {phase}")
        written: Dict[str, Any] = {}
        if phase in {"all", "e2e_qa"}:
            written["e2e_qa"] = await self.run_e2e_qa(samples, out_dir)
        return written

    async def run_e2e_qa(self, samples: Sequence[DocumentEvalSample], out_dir: Path) -> Dict[str, Any]:
        corpus = build_local_corpus_index(self.config, samples)
        executor = self.qa_executor
        if executor is None:
            executor = LocalCorpusQAExecutor(
                corpus,
                top_k=self.config.top_k,
                provider=self.config.provider,
                model=self.config.model,
            )

        documents: List[DocumentQAEvalResult] = []
        for sample in samples:
            sections = sample.sections
            if self.config.max_sections_per_document is not None:
                sections = sections[: self.config.max_sections_per_document]
            qa_results: List[QAEvalResult] = []
            for section in sections:
                pairs = await self.judge.generate_qa_pairs(section, self.config.questions_per_section)
                for idx, pair in enumerate(pairs[: self.config.questions_per_section]):
                    target_section_key = _section_key_from_section(section)
                    target_chunk_ids = tuple(
                        chunk.chunk_id
                        for chunk in corpus.chunks
                        if chunk.doc_id == sample.doc_id and chunk.mapped_section_id == section.section_id
                    )
                    item = QAEvalItem(
                        doc_id=sample.doc_id,
                        section_id=section.section_id,
                        question_index=idx,
                        question=pair["question"],
                        reference_answer=pair["reference_answer"],
                        source_section_text=section.source_text,
                        target_section_key=target_section_key,
                        target_chunk_ids=target_chunk_ids,
                    )
                    retrieved_context, generated_answer = await executor.run(item.question)
                    retrieval_trace = _build_retrieval_trace(item, retrieved_context)
                    judge_result = await self.judge.judge_qa(
                        question=item.question,
                        reference_answer=item.reference_answer,
                        retrieved_context=retrieved_context,
                        generated_answer=generated_answer,
                    )
                    qa_results.append(
                        QAEvalResult(
                            item=item,
                            retrieved_context=_trim_context_for_report(retrieved_context),
                            generated_answer=generated_answer,
                            judge_result=judge_result,
                            retrieval_trace=retrieval_trace,
                            failure_category=_failure_category(retrieval_trace, judge_result),
                        )
                    )
            documents.append(
                DocumentQAEvalResult(
                    doc_id=sample.doc_id,
                    results=qa_results,
                    distributions=_qa_distributions(qa_results),
                    retrieval_trace_summary=_retrieval_trace_summary(qa_results),
                    failed_questions_by_section=_failed_questions_by_section(qa_results),
                )
            )
        report = {
            "phase": "e2e_qa_eval",
            "corpus": {
                "doc_ids": corpus.doc_ids,
                "doc_dirs": corpus.doc_dirs,
                "chunk_count": len(corpus.chunks),
            },
            "documents": [asdict(result) for result in documents],
            "summary": {
                "distributions": _merge_qa_distributions([d.distributions for d in documents]),
                "retrieval_trace_summary": _merge_retrieval_trace_summaries(
                    [d.retrieval_trace_summary for d in documents]
                ),
            },
        }
        _write_json(out_dir / "e2e_qa_eval_report.json", report)
        return report


def run_document_intelligence_eval(
    config: DocumentIntelligenceEvalConfig,
    judge: Optional[BaseDocumentIntelligenceJudge] = None,
    qa_executor: Optional[BaseQAExecutor] = None,
) -> Dict[str, Any]:
    runner = DocumentIntelligenceRunner(
        config,
        judge or LLMDocumentIntelligenceJudge(config.provider, config.model),
        qa_executor=qa_executor,
    )
    return asyncio.run(runner.run())


def discover_document_samples(config: DocumentIntelligenceEvalConfig) -> List[DocumentEvalSample]:
    input_path = Path(config.input_path).resolve()
    parsed_root = Path(config.parsed_root).resolve()
    doc_dirs = discover_corpus_doc_dirs(input_path)
    if config.max_documents is not None:
        doc_dirs = doc_dirs[: config.max_documents]
    samples = []
    for doc_dir in doc_dirs:
        sample = _build_sample_for_doc_dir(doc_dir, parsed_root)
        if sample is not None:
            samples.append(sample)
    return samples


def discover_corpus_doc_dirs(input_path: Path) -> List[Path]:
    if input_path.is_dir() and any(input_path.glob("*_manifest.json")):
        return [input_path]
    return sorted({path.parent for path in input_path.rglob("*_manifest.json")})


def build_local_corpus_index(
    config: DocumentIntelligenceEvalConfig,
    samples: Sequence[DocumentEvalSample],
) -> LocalCorpusIndex:
    input_path = Path(config.input_path).resolve()
    parsed_root = Path(config.parsed_root).resolve()
    corpus_doc_dirs = discover_corpus_doc_dirs(input_path)
    sample_by_doc_id = {sample.doc_id: sample for sample in samples}
    chunks: List[LocalCorpusChunk] = []
    doc_ids: List[str] = []
    doc_dirs: List[str] = []

    for doc_dir in corpus_doc_dirs:
        sample = _build_sample_for_doc_dir(doc_dir, parsed_root)
        canonical_doc_id = sample.doc_id if sample is not None else doc_dir.name
        doc_ids.append(canonical_doc_id)
        doc_dirs.append(str(doc_dir))
        for chunk in _load_chunks_for_doc_dir(doc_dir, canonical_doc_id):
            chunks.append(chunk)

    _map_corpus_chunks_to_sections(chunks, sample_by_doc_id)
    return LocalCorpusIndex(doc_ids=sorted(doc_ids), doc_dirs=sorted(doc_dirs), chunks=chunks)


def _build_sample_for_doc_dir(doc_dir: Path, parsed_root: Path) -> Optional[DocumentEvalSample]:
    manifest_path = _first_existing(
        doc_dir,
        ["docx_manifest.json", "pdf_manifest.json", "excel_manifest.json", "pptx_manifest.json"],
    )
    if manifest_path is None:
        return None
    manifest = _load_json(manifest_path)
    doc_id = str(manifest.get("doc_id") or doc_dir.name)
    if manifest_path.name.startswith("docx"):
        doc_type = "docx"
    elif manifest_path.name.startswith("pdf"):
        doc_type = "pdf"
    elif manifest_path.name.startswith("excel"):
        doc_type = "excel"
    else:
        doc_type = "pptx"
    parsed_path = _resolve_parsed_tree(doc_id, doc_type, parsed_root)
    if parsed_path is None:
        return None
    tree = _load_json(parsed_path)
    sections = flatten_sections(tree, doc_id)
    md_path = doc_dir / f"{doc_id}.md"
    return DocumentEvalSample(
        doc_id=doc_id,
        doc_type=doc_type,
        parsed_tree_path=str(parsed_path),
        rag_ready_dir=str(doc_dir),
        source_document_path=_resolve_source_document_path(manifest, doc_id, parsed_root),
        source_markdown_path=str(md_path) if md_path.exists() else None,
        sections=sections,
    )


def _resolve_parsed_tree(doc_id: str, doc_type: str, parsed_root: Path) -> Optional[Path]:
    candidates = [
        parsed_root / f"{doc_id}.json",
        parsed_root / f"{doc_type}_parsed" / f"{doc_id}.json",
    ]
    if doc_type == "docx":
        candidates.append(parsed_root / "docx_parsed" / f"{doc_id}.json")
    if doc_type == "pdf":
        candidates.append(parsed_root / "pdf_parsed" / f"{doc_id}.json")
    if doc_type == "excel":
        candidates.append(parsed_root / "excel_parsed" / f"{doc_id}.json")
    if doc_type == "pptx":
        candidates.append(parsed_root / "pptx_parsed" / f"{doc_id}.json")
    for path in candidates:
        if path.exists():
            return path
    return None


def _resolve_source_document_path(manifest: Dict[str, Any], doc_id: str, parsed_root: Path) -> Optional[str]:
    source = str(manifest.get("source") or "").strip()
    if source and Path(source).exists():
        return source
    originals = parsed_root / "original_files"
    for ext in (".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".ppt"):
        candidate = originals / f"{doc_id}{ext}"
        if candidate.exists():
            return str(candidate)
    return source or None


def flatten_sections(tree: Any, doc_id: str) -> List[SectionSample]:
    sections: List[SectionSample] = []

    def _walk(nodes: Sequence[Dict[str, Any]], breadcrumb: Sequence[str]) -> None:
        for node in nodes:
            heading = _node_heading(node)
            level = _coerce_int(node.get("heading_level"), 0)
            content = str(node.get("content", "") or "")
            children = list(node.get("children") or [])
            current = list(breadcrumb) + ([heading] if heading else [])
            if content.strip():
                idx = len(sections)
                sections.append(
                    SectionSample(
                        doc_id=doc_id,
                        section_id=f"{doc_id}:section:{idx:04d}",
                        section_index=idx,
                        heading_text=heading,
                        heading_level=level,
                        heading_breadcrumb=current,
                        source_text=content,
                    )
                )
            if children:
                _walk(children, current)

    if isinstance(tree, list):
        _walk(tree, [])
    return sections


def _node_heading(node: Dict[str, Any]) -> str:
    for key in ("heading_text", "sheet_name", "section", "title", "name"):
        value = str(node.get(key, "") or "").strip()
        if value:
            return value
    return ""


def _section_key_from_heading(heading_text: Any, heading_breadcrumb: Any) -> str:
    heading = str(heading_text or "").strip()
    breadcrumb = [
        str(item).strip()
        for item in (heading_breadcrumb or [])
        if str(item).strip()
    ]
    if heading and (not breadcrumb or breadcrumb[-1] != heading):
        breadcrumb.append(heading)
    return " > ".join(breadcrumb).strip()


def _section_key_from_section(section: SectionSample) -> str:
    key = _section_key_from_heading(section.heading_text, section.heading_breadcrumb)
    return key or f"{section.doc_id}:{section.section_id}"


def _section_key_from_chunk_metadata(metadata: Dict[str, Any]) -> str:
    heading_key = _section_key_from_heading(metadata.get("heading_text"), metadata.get("heading_breadcrumb"))
    if heading_key:
        return heading_key
    sheet_name = str(metadata.get("sheet_name", "") or "").strip()
    section = str(metadata.get("section", "") or "").strip()
    if sheet_name and section:
        return f"{sheet_name} > {section}"
    return sheet_name or section


def _load_chunks_for_doc_dir(doc_dir: Path, doc_id: str) -> List[LocalCorpusChunk]:
    chunk_path = _first_existing(
        doc_dir,
        ["docx_chunks.json", "pdf_chunks.json", "excel_chunks.json", "pptx_chunks.json"],
    )
    if chunk_path is None:
        return []
    payload = _load_json(chunk_path)
    items = payload if isinstance(payload, list) else payload.get("chunks") or []
    out: List[LocalCorpusChunk] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "") or "").strip()
        if not text:
            continue
        metadata = dict(item.get("metadata") or {})
        chunk_id = str(item.get("id") or item.get("chunk_id") or f"{doc_id}:chunk:{idx:06d}").strip()
        chunk_index = _coerce_int(item.get("chunk_index", metadata.get("chunk_index", idx)), idx)
        out.append(
            LocalCorpusChunk(
                doc_id=doc_id,
                chunk_id=chunk_id,
                text=text,
                source=str(item.get("source", "") or ""),
                metadata=metadata,
                chunk_index=chunk_index,
                raw_section_key=_section_key_from_chunk_metadata(metadata),
            )
        )
    return out


def _map_corpus_chunks_to_sections(
    chunks: Sequence[LocalCorpusChunk],
    sample_by_doc_id: Dict[str, DocumentEvalSample],
) -> None:
    grouped: Dict[str, List[LocalCorpusChunk]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.doc_id, []).append(chunk)

    for doc_id, doc_chunks in grouped.items():
        sample = sample_by_doc_id.get(doc_id)
        if sample is None or not sample.sections:
            continue
        section_by_key: Dict[str, List[SectionSample]] = {}
        for section in sample.sections:
            section_by_key.setdefault(_section_key_from_section(section), []).append(section)

        for chunk in doc_chunks:
            matched_section: Optional[SectionSample] = None
            if chunk.raw_section_key:
                candidates = section_by_key.get(chunk.raw_section_key) or []
                if len(candidates) == 1:
                    matched_section = candidates[0]
                elif len(candidates) > 1:
                    matched_section = _best_section_by_overlap(chunk.text, candidates)
            if matched_section is None:
                matched_section = _best_section_by_overlap(chunk.text, sample.sections)
            if matched_section is not None:
                chunk.mapped_section_id = matched_section.section_id
                chunk.mapped_section_key = _section_key_from_section(matched_section)


def _best_section_by_overlap(text: str, sections: Sequence[SectionSample]) -> Optional[SectionSample]:
    query_tokens = _content_tokens(text)
    if not query_tokens:
        return None
    best_section: Optional[SectionSample] = None
    best_score = 0.0
    for section in sections:
        section_tokens = _content_tokens(section.source_text)
        if not section_tokens:
            continue
        score = len(query_tokens & section_tokens) / max(len(query_tokens), 1)
        if score > best_score:
            best_score = score
            best_section = section
    return best_section if best_score > 0 else None


def extract_table_samples(
    sample: DocumentEvalSample,
    *,
    reference_cache_dir: Optional[Path] = None,
) -> List[TableElementSample]:
    out: List[TableElementSample] = []
    source_reference = _load_source_reference(sample, reference_cache_dir)
    for section in sample.sections:
        for idx, match in enumerate(_TABLE_RE.finditer(section.source_text)):
            table = match.group(1).strip()
            page_path, page_score = _best_page_for_text(table, source_reference)
            page_input, page_status = load_image_as_llm_input(page_path)
            if page_input:
                original_input = (
                    "Original source reference is attached as an image. "
                    "Input mode: page_image. This is the full source page selected for this table, not an exact crop. "
                    f"Page match score: {page_score if page_score is not None else 'unknown'}."
                )
                input_mode = "page_image"
            else:
                original_input = section.source_text
                input_mode = "source_text_fallback"
            out.append(
                TableElementSample(
                    doc_id=sample.doc_id,
                    section_id=section.section_id,
                    table_id=f"{section.section_id}:table:{idx:03d}",
                    parsed_table=table,
                    original_table_input=original_input,
                    input_mode=input_mode,
                    original_table_image_path=str(page_path) if page_path else None,
                    original_table_image_input=page_input,
                    source_page_match_score=page_score,
                )
            )
    return out


def extract_image_samples(
    sample: DocumentEvalSample,
    *,
    reference_cache_dir: Optional[Path] = None,
) -> List[ImageElementSample]:
    out: List[ImageElementSample] = []
    rag_dir = Path(sample.rag_ready_dir)
    source_reference = _load_source_reference(sample, reference_cache_dir)
    for section in sample.sections:
        for idx, match in enumerate(_IMAGE_RE.finditer(section.source_text)):
            marker_value = match.group(1).strip()
            raw_path = marker_value.split("|", 1)[0].strip()
            extracted_path = _resolve_extracted_image_path(raw_path, rag_dir)
            extracted_input, extracted_status = load_image_as_llm_input(extracted_path)
            original_path, match_score = _best_page_for_image(extracted_path, source_reference)
            if original_path is None:
                original_path, text_score = _best_page_for_text(section.source_text, source_reference)
                match_score = match_score if match_score is not None else text_score
            original_input, original_status = load_image_as_llm_input(original_path)
            original_mode = "page_image" if original_input else "unavailable"
            load_status = extracted_status if extracted_input else f"failed_extracted:{extracted_status}"
            if extracted_input and original_input:
                load_status = "extracted_loaded_original_page_loaded"
            elif extracted_input and not original_input:
                load_status = "extracted_loaded_original_unavailable"
            elif original_input:
                load_status = f"failed_extracted:{extracted_status}_original_page_loaded"
            out.append(
                ImageElementSample(
                    doc_id=sample.doc_id,
                    section_id=section.section_id,
                    image_id=f"{section.section_id}:image:{idx:03d}",
                    extracted_image_path=str(extracted_path) if extracted_path else raw_path,
                    parsed_image_metadata={
                        "marker": marker_value,
                        "raw_path": raw_path,
                        "section_heading": section.heading_text,
                        "section_breadcrumb": section.heading_breadcrumb,
                    },
                    extracted_image_input=extracted_input,
                    original_image_input=original_input,
                    original_image_input_mode=original_mode,
                    original_image_path=str(original_path) if original_path else None,
                    image_load_status=load_status,
                    source_page_match_score=match_score,
                )
            )
    return out


def _load_source_reference(sample: DocumentEvalSample, reference_cache_dir: Optional[Path]) -> SourceReference:
    source_path = Path(sample.source_document_path) if sample.source_document_path else None
    if reference_cache_dir is None:
        return SourceReference(str(source_path) if source_path else None, None, [], "render_not_requested")
    if source_path is None or not source_path.exists():
        return SourceReference(str(source_path) if source_path else None, None, [], "source_missing")
    return render_source_document_pages(source_path, reference_cache_dir)


def render_source_document_pages(source_path: Path, output_dir: Path, *, dpi: int = 144) -> SourceReference:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path, convert_status = _source_to_pdf(source_path, output_dir)
    if pdf_path is None or not pdf_path.exists():
        return SourceReference(str(source_path), None, [], convert_status)

    page_dir = output_dir / "pages"
    page_dir.mkdir(parents=True, exist_ok=True)
    existing_pages = sorted(page_dir.glob("page_*.png"))
    if existing_pages:
        return SourceReference(str(source_path), pdf_path, existing_pages, "loaded_cached_pages")

    try:
        import fitz  # type: ignore

        doc = fitz.open(str(pdf_path))
        matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        page_paths: List[Path] = []
        for idx, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            page_path = page_dir / f"page_{idx + 1:04d}.png"
            pix.save(str(page_path))
            page_paths.append(page_path)
        doc.close()
        return SourceReference(str(source_path), pdf_path, page_paths, "rendered_pages")
    except Exception as exc:  # pragma: no cover - depends on local render stack
        return SourceReference(str(source_path), pdf_path, [], f"page_render_failed:{exc}")


def _source_to_pdf(source_path: Path, output_dir: Path) -> Tuple[Optional[Path], str]:
    if source_path.suffix.lower() == ".pdf":
        return source_path, "source_is_pdf"

    cached_pdf = output_dir / f"{source_path.stem}.pdf"
    if cached_pdf.exists():
        return cached_pdf, "loaded_cached_pdf"

    office = shutil.which("libreoffice") or shutil.which("soffice")
    if not office:
        return None, "libreoffice_missing"

    lo_home = output_dir / "libreoffice_home"
    lo_runtime = output_dir / "libreoffice_runtime"
    lo_profile = output_dir / "libreoffice_profile"
    lo_home.mkdir(parents=True, exist_ok=True)
    lo_runtime.mkdir(parents=True, exist_ok=True)
    lo_profile.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(lo_home)
    env["XDG_RUNTIME_DIR"] = str(lo_runtime)

    try:
        completed = subprocess.run(
            [
                office,
                "--headless",
                f"-env:UserInstallation={lo_profile.resolve().as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(source_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
    except Exception as exc:  # pragma: no cover - subprocess failure is environment-specific
        return None, f"libreoffice_failed:{exc}"

    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        return None, f"libreoffice_failed:{err[:300]}"

    if cached_pdf.exists():
        return cached_pdf, "converted_to_pdf"
    candidates = sorted(output_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    return (candidates[0], "converted_to_pdf") if candidates else (None, "converted_pdf_missing")


def _best_page_for_text(text: str, source_reference: SourceReference) -> Tuple[Optional[Path], Optional[float]]:
    if not source_reference.page_paths:
        return None, None
    if source_reference.pdf_path is None or not source_reference.pdf_path.exists():
        return source_reference.page_paths[0], None

    query_tokens = _content_tokens(text)
    if not query_tokens:
        return source_reference.page_paths[0], 0.0

    try:
        import fitz  # type: ignore

        doc = fitz.open(str(source_reference.pdf_path))
        best_idx = 0
        best_score = -1.0
        for idx, page in enumerate(doc):
            page_tokens = _content_tokens(page.get_text("text"))
            if not page_tokens:
                score = 0.0
            else:
                score = len(query_tokens & page_tokens) / max(len(query_tokens), 1)
            if score > best_score:
                best_idx = idx
                best_score = score
        doc.close()
        if best_idx < len(source_reference.page_paths):
            return source_reference.page_paths[best_idx], round(best_score, 4)
    except Exception:
        pass
    return source_reference.page_paths[0], 0.0


def _best_page_for_image(
    extracted_image_path: Optional[Path],
    source_reference: SourceReference,
) -> Tuple[Optional[Path], Optional[float]]:
    if not source_reference.page_paths:
        return None, None
    if extracted_image_path is None or not extracted_image_path.exists():
        return source_reference.page_paths[0], None

    try:
        import cv2  # type: ignore

        template = cv2.imread(str(extracted_image_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            return source_reference.page_paths[0], None
        best_path: Optional[Path] = None
        best_score = -1.0
        for page_path in source_reference.page_paths:
            page = cv2.imread(str(page_path), cv2.IMREAD_GRAYSCALE)
            if page is None:
                continue
            score = _template_match_score(page, template)
            if score > best_score:
                best_path = page_path
                best_score = score
        if best_path is not None:
            return best_path, round(float(best_score), 4)
    except Exception:
        pass
    return source_reference.page_paths[0], 0.0


def _template_match_score(page: Any, template: Any) -> float:
    import cv2  # type: ignore

    page_h, page_w = page.shape[:2]
    tpl_h, tpl_w = template.shape[:2]
    if page_h < 16 or page_w < 16 or tpl_h < 8 or tpl_w < 8:
        return 0.0

    best = -1.0
    for scale in (1.0, 0.85, 0.7, 0.55, 0.4, 0.3, 0.2, 0.15, 0.1):
        new_w = int(tpl_w * scale)
        new_h = int(tpl_h * scale)
        if new_w < 8 or new_h < 8 or new_w > page_w or new_h > page_h:
            continue
        resized = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)
        result = cv2.matchTemplate(page, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        best = max(best, float(max_val))
    return best if best >= 0 else 0.0


def _content_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-zÀ-ỹ0-9_]{3,}", text.lower())
    stop = {
        "start_table_content",
        "end_table_content",
        "start_image_path",
        "end_image_path",
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
    }
    return {token for token in tokens if token not in stop}


def load_image_as_llm_input(path: Optional[Path]) -> Tuple[Optional[Dict[str, Any]], str]:
    if path is None:
        return None, "path_missing"
    if not path.exists():
        return None, "file_not_found"
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"mime_type": mime, "data_url": f"data:{mime};base64,{data}"}, "loaded"


def _resolve_extracted_image_path(raw_path: str, rag_dir: Path) -> Optional[Path]:
    path = Path(raw_path)
    if path.exists():
        return path
    candidate = rag_dir / "images" / path.name
    if candidate.exists():
        return candidate
    return path


def _trim_context_for_report(context: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for item in context:
        text = str(item.get("full_text") or item.get("text") or "")
        out.append(
            {
                "id": item.get("id"),
                "source": item.get("source"),
                "score": item.get("score"),
                "retrieval_type": item.get("retrieval_type"),
                "text": text,
                "metadata": item.get("metadata") or {},
            }
        )
    return out


def _build_retrieval_trace(item: QAEvalItem, retrieved_context: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    retrieved_doc_ids: List[str] = []
    retrieved_section_keys: List[str] = []
    retrieved_chunk_ids: List[str] = []
    for ctx in retrieved_context:
        metadata = ctx.get("metadata") or {}
        retrieved_doc_ids.append(str(metadata.get("doc_id") or ""))
        retrieved_section_keys.append(
            str(metadata.get("mapped_section_key") or metadata.get("section_key") or "")
        )
        retrieved_chunk_ids.append(str(ctx.get("id") or ""))

    target_chunk_ids = list(item.target_chunk_ids)
    trace = {
        "target_doc_id": item.doc_id,
        "target_section_key": item.target_section_key,
        "target_chunk_ids": target_chunk_ids,
        "retrieved_doc_ids": retrieved_doc_ids,
        "retrieved_section_keys": retrieved_section_keys,
        "retrieved_chunk_ids": retrieved_chunk_ids,
        "doc_hit_in_top_k": item.doc_id in set(retrieved_doc_ids),
        "section_hit_in_top_k": bool(item.target_section_key) and item.target_section_key in set(retrieved_section_keys),
        "chunk_hit_in_top_k": bool(set(target_chunk_ids) & set(retrieved_chunk_ids)),
        "retrieval_failure_reason": "",
    }
    if not target_chunk_ids:
        trace["retrieval_failure_reason"] = "target_chunk_mapping_missing"
    elif not retrieved_context:
        trace["retrieval_failure_reason"] = "no_results"
    elif not trace["doc_hit_in_top_k"]:
        trace["retrieval_failure_reason"] = "wrong_document"
    elif not trace["section_hit_in_top_k"]:
        trace["retrieval_failure_reason"] = "wrong_section"
    elif not trace["chunk_hit_in_top_k"]:
        trace["retrieval_failure_reason"] = "wrong_chunk"
    return trace


def _qa_distributions(results: Sequence[QAEvalResult]) -> Dict[str, Dict[str, int]]:
    dist = {
        "correctness": {label: 0 for label in sorted(_CORRECTNESS_LABELS)},
        "faithfulness": {label: 0 for label in sorted(_FAITHFULNESS_LABELS)},
        "answer_support": {label: 0 for label in sorted(_ANSWER_SUPPORT_LABELS)},
    }
    for result in results:
        jr = result.judge_result
        for key in dist:
            label = jr.get(key)
            if label in dist[key]:
                dist[key][label] += 1
    return dist


def _merge_qa_distributions(distributions: Sequence[Dict[str, Dict[str, int]]]) -> Dict[str, Dict[str, int]]:
    merged = {
        "correctness": {label: 0 for label in sorted(_CORRECTNESS_LABELS)},
        "faithfulness": {label: 0 for label in sorted(_FAITHFULNESS_LABELS)},
        "answer_support": {label: 0 for label in sorted(_ANSWER_SUPPORT_LABELS)},
    }
    for dist in distributions:
        for key in merged:
            for label, count in (dist.get(key) or {}).items():
                if label in merged[key]:
                    merged[key][label] += int(count)
    return merged


def _retrieval_trace_summary(results: Sequence[QAEvalResult]) -> Dict[str, int]:
    summary = {
        "question_count": len(results),
        "doc_hit_in_top_k": 0,
        "section_hit_in_top_k": 0,
        "chunk_hit_in_top_k": 0,
    }
    for result in results:
        trace = result.retrieval_trace
        for key in ("doc_hit_in_top_k", "section_hit_in_top_k", "chunk_hit_in_top_k"):
            if trace.get(key):
                summary[key] += 1
    return summary


def _merge_retrieval_trace_summaries(summaries: Sequence[Dict[str, int]]) -> Dict[str, int]:
    merged = {
        "question_count": 0,
        "doc_hit_in_top_k": 0,
        "section_hit_in_top_k": 0,
        "chunk_hit_in_top_k": 0,
    }
    for summary in summaries:
        for key in merged:
            merged[key] += int(summary.get(key, 0))
    return merged


def _failure_category(retrieval_trace: Dict[str, Any], judge_result: Dict[str, str]) -> str:
    reason = str(retrieval_trace.get("retrieval_failure_reason") or "").strip()
    if reason == "target_chunk_mapping_missing":
        return "target_chunk_mapping_missing"
    if reason == "no_results":
        return "no_results"
    if reason == "wrong_document":
        return "wrong_file_retrieval"
    if reason == "wrong_section":
        return "wrong_section_retrieval"
    if reason == "wrong_chunk":
        return "wrong_chunk_retrieval"
    if (
        judge_result.get("correctness") != "correct"
        or judge_result.get("faithfulness") != "faithful"
        or judge_result.get("answer_support") != "fully_supported"
    ):
        return "downstream_qa_failure"
    return "passed"


def _failed_questions_by_section(results: Sequence[QAEvalResult]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for result in results:
        if result.failure_category != "passed":
            out.setdefault(result.item.section_id, []).append(
                {
                    "question": result.item.question,
                    "reference_answer": result.item.reference_answer,
                    "generated_answer": result.generated_answer,
                    "judge_result": result.judge_result,
                    "retrieval_trace": result.retrieval_trace,
                    "retrieved_context": result.retrieved_context,
                    "failure_category": result.failure_category,
                }
            )
    return out


def _element_distribution(documents: Sequence[ElementEvalResult]) -> Dict[str, Any]:
    return {
        "table_count": sum(len(doc.tables) for doc in documents),
        "image_count": sum(len(doc.images) for doc in documents),
        "image_load_status_counts": _count_labels(
            img.sample.image_load_status for doc in documents for img in doc.images
        ),
    }


def _serialize_element_result(result: ElementEvalResult) -> Dict[str, Any]:
    """Serialize element results without embedding base64 image payloads."""
    tables = []
    for table_result in result.tables:
        sample = table_result.sample
        tables.append(
            {
                "sample": {
                    "doc_id": sample.doc_id,
                    "section_id": sample.section_id,
                    "table_id": sample.table_id,
                    "parsed_table": sample.parsed_table,
                    "original_table_input": sample.original_table_input,
                    "input_mode": sample.input_mode,
                    "original_table_image_path": sample.original_table_image_path,
                    "original_table_loaded_as_image_input": sample.original_table_image_input is not None,
                    "source_page_match_score": sample.source_page_match_score,
                },
                "judge_result": table_result.judge_result,
            }
        )
    images = []
    for image_result in result.images:
        sample = image_result.sample
        images.append(
            {
                "sample": {
                    "doc_id": sample.doc_id,
                    "section_id": sample.section_id,
                    "image_id": sample.image_id,
                    "extracted_image_path": sample.extracted_image_path,
                    "parsed_image_metadata": sample.parsed_image_metadata,
                    "original_image_input_mode": sample.original_image_input_mode,
                    "original_image_path": sample.original_image_path,
                    "image_load_status": sample.image_load_status,
                    "extracted_image_loaded_as_image_input": sample.extracted_image_input is not None,
                    "original_image_loaded_as_image_input": sample.original_image_input is not None,
                    "source_page_match_score": sample.source_page_match_score,
                },
                "judge_result": image_result.judge_result,
            }
        )
    return {
        "doc_id": result.doc_id,
        "tables": tables,
        "images": images,
    }


def _normalize_table_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "missing_rows": _str_list(payload.get("missing_rows")),
        "wrong_values_of_cells": _str_list(payload.get("wrong_values_of_cells")),
        "wrong_headers": _str_list(payload.get("wrong_headers")),
        "structure_errors": _str_list(payload.get("structure_errors")),
        "judge_rationale": str(payload.get("judge_rationale", "")).strip(),
    }


def _normalize_image_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "crop_quality": _str_list(payload.get("crop_quality")),
        "issues": _str_list(payload.get("issues")),
        "judge_rationale": str(payload.get("judge_rationale", "")).strip(),
    }


def _normalize_qa_result(payload: Dict[str, Any]) -> Dict[str, str]:
    # Exactly the requested score fields plus rationale. No extra metrics.
    return {
        "correctness": _label(payload.get("correctness"), _CORRECTNESS_LABELS, "incorrect"),
        "faithfulness": _label(payload.get("faithfulness"), _FAITHFULNESS_LABELS, "hallucinated"),
        "answer_support": _label(payload.get("answer_support"), _ANSWER_SUPPORT_LABELS, "not_supported"),
        "judge_rationale": str(payload.get("judge_rationale", "")).strip(),
    }


def _json_or_empty(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _first_existing(folder: Path, names: Sequence[str]) -> Optional[Path]:
    for name in names:
        path = folder / name
        if path.exists():
            return path
    return None


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _int_between(value: Any, lo: int, hi: int) -> int:
    return max(lo, min(hi, _coerce_int(value, lo)))


def _str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _label(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip()
    return text if text in allowed else default


def _count_labels(values: Iterable[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out
