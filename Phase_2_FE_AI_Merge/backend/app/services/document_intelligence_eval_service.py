"""Document Intelligence Evaluation with database integration."""

from __future__ import annotations

import json
import logging
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.core.paths import BACKEND_ROOT, merged_runtime_settings, sanitize_storage_user_id, workspace_paths_for_user
from app.services.processed_documents_service import build_processed_documents_snapshot
from app.services.processed_markdown_service import gather_processed_markdown_context
from app.services.search_orchestrator import SearchOrchestrator

logger = logging.getLogger(__name__)

_MAX_CONTEXT_CHARS_PER_DOC = 80_000
_MAX_SUMMARY_CONTEXT_CHARS = 45_000

_JSON_BLOCK_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL | re.IGNORECASE)

_CORRECTNESS_LABELS = {"correct", "partially_correct", "incorrect"}
_FAITHFULNESS_LABELS = {"faithful", "partially_faithful", "hallucinated"}
_ANSWER_SUPPORT_LABELS = {"fully_supported", "partially_supported", "not_supported"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_or_empty(raw: str) -> Dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {"items": parsed}
    except json.JSONDecodeError:
        pass
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
        return parsed if isinstance(parsed, dict) else {"items": parsed}
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clip(text: Any, limit: int) -> str:
    value = str(text or "").strip()
    return value


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _stdev(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    m = _mean(values)
    return float(math.sqrt(sum((x - m) ** 2 for x in values) / len(values)))


def _generation_config(cfg: Dict[str, Any], provider: str | None = None, model: str | None = None):
    """Build RAGGenerator configuration matching RetrievalEvalService pattern."""
    from src.generation.generator import GenerationConfig, RAGGenerator

    gyaml = cfg.get("generation", {}) or {}
    provider_val = str(gyaml.get("provider", "openai")) if provider is None else provider
    model_val = str(gyaml.get("model", "gpt-4o-mini")) if model is None else model

    gc = GenerationConfig(
        provider=provider_val,
        model_name=model_val,
        api_key=gyaml.get("api_key"),
        base_url=gyaml.get("base_url"),
        bedrock_region=(gyaml.get("bedrock_region") or None),
        temperature=0.0,
        max_tokens=int(gyaml.get("max_tokens", 3000)),
        enable_citations=False,
        base_dir=str(BACKEND_ROOT),
    )
    return RAGGenerator(gc)


class DocumentIntelligenceEvalService:
    """Service for document intelligence evaluation with database integration."""

    def __init__(self, yaml_config: Dict[str, Any] | None = None, user_id: str | None = None):
        if user_id is None:
            raise ValueError("user_id is required for DocumentIntelligenceEvalService")

        self.cfg = merged_runtime_settings(yaml_config)
        self.user_id = sanitize_storage_user_id(user_id)
        self.paths = workspace_paths_for_user(self.user_id)
        self.root = self.paths.output_dir / "evaluation" / "document_intelligence_eval"

    def _run_path(self, run_id: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", str(run_id or "").strip())
        if not safe:
            raise ValueError("run_id is required")
        return self.root / safe / "report.json"

    def load_run(self, run_id: str) -> Dict[str, Any]:
        path = self._run_path(run_id)
        if not path.exists():
            raise FileNotFoundError(run_id)
        return _read_json(path)

    def save_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        path = self._run_path(str(run.get("run_id") or ""))
        run["artifact_path"] = str(path)
        _write_json(path, run)
        return run

    def new_run_id(self) -> str:
        return f"doc_intel_eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def _active_documents(self, max_documents: int | None = None) -> List[Dict[str, Any]]:
        """Get processed documents for evaluation."""
        snapshot = build_processed_documents_snapshot(self.user_id, include_preview=False)
        docs: List[Dict[str, Any]] = []
        for doc in snapshot.get("documents") or []:
            doc_id = str(doc.get("id") or "").strip()
            if not doc_id or doc_id.startswith("__"):
                continue
            # Get stage1_normalized markdown (processed markdown)
            ctx = gather_processed_markdown_context(self.user_id, doc_id, _MAX_CONTEXT_CHARS_PER_DOC)
            if not ctx.strip():
                continue
            docs.append(
                {
                    "doc_id": doc_id,
                    "display_name": str(doc.get("display_name") or doc_id),
                    "total_files": int(doc.get("total_files") or 0),
                    "context": ctx,
                }
            )
            if max_documents and len(docs) >= max_documents:
                break
        return docs

    def _flatten_sections_from_markdown(self, markdown_text: str, doc_id: str) -> List[Dict[str, Any]]:
        """Flatten sections from stage1_normalized markdown."""
        sections: List[Dict[str, Any]] = []
        lines = markdown_text.split('\n')
        heading_re = re.compile(r'^(#{1,6})\s+(.+)$')

        current_section = None
        current_content = []
        breadcrumbs: List[str] = []
        section_index = 0

        for line in lines:
            match = heading_re.match(line)
            if match:
                # Save previous section
                if current_section and current_content:
                    current_section["source_text"] = '\n'.join(current_content).strip()
                    sections.append(current_section)
                    section_index += 1

                # Start new section
                level = len(match.group(1))
                heading_text = match.group(2).strip()

                # Update breadcrumbs
                if level == 1:
                    breadcrumbs = [heading_text]
                else:
                    while len(breadcrumbs) >= level:
                        breadcrumbs.pop()
                    breadcrumbs.append(heading_text)

                current_section = {
                    "doc_id": doc_id,
                    "section_id": f"{doc_id}:section:{section_index:04d}",
                    "section_index": section_index,
                    "heading_text": heading_text,
                    "heading_level": level,
                    "heading_breadcrumb": list(breadcrumbs),
                }
                current_content = []
            elif current_section is not None:
                current_content.append(line)

        # Save last section
        if current_section and current_content:
            current_section["source_text"] = '\n'.join(current_content).strip()
            sections.append(current_section)

        # If no sections found, create a default one
        if not sections:
            sections.append({
                "doc_id": doc_id,
                "section_id": f"{doc_id}:section:0000",
                "section_index": 0,
                "heading_text": "Document",
                "heading_level": 1,
                "heading_breadcrumb": ["Document"],
                "source_text": markdown_text.strip(),
            })

        return sections

    def _generate_qa_pairs(
        self,
        generator: Any,
        section: Dict[str, Any],
        question_count: int,
    ) -> List[Dict[str, str]]:
        """Generate QA pairs for a section using LLM."""
        prompt = f"""
Generate {question_count} question-answer pairs for this document section.

Return JSON only:
{{
  "items": [
    {{"question": "...", "reference_answer": "..."}}
  ]
}}

Requirements:
- Questions should be specific and answerable from the section content.
- Answers should be concise and accurate based on content.
- Generate exactly {question_count} pairs.

Section heading: {section.get('heading_text', '')}
Section breadcrumb: {' > '.join(section.get('heading_breadcrumb', []))}

Section content:
{_clip(section.get('source_text', ''), 6000)}
""".strip()

        raw = ""
        try:
            raw = generator._call_llm(prompt)
            payload = _json_or_empty(raw)
            items = payload.get("items") if isinstance(payload, dict) else []
            if not isinstance(items, list):
                items = []
            return items[:question_count]
        except Exception as exc:
            logger.warning("QA pair generation failed for %s: %s", section.get('section_id'), exc)
            return []

    def _judge_qa(
        self,
        generator: Any,
        *,
        question: str,
        reference_answer: str,
        retrieved_context: Sequence[Dict[str, Any]],
        generated_answer: str,
    ) -> Dict[str, str]:
        """Judge the QA response."""
        context_text = "\n\n".join(
            f"[{idx + 1}] id={ctx.get('id', '')}\n{ctx.get('text') or ctx.get('full_text') or ''}"
            for idx, ctx in enumerate(retrieved_context[:10])
        )

        prompt = f"""
Judge this end-to-end QA response.

Return JSON only:
{{
  "correctness": "correct | partially_correct | incorrect",
  "faithfulness": "faithful | partially_faithful | hallucinated",
  "answer_support": "fully_supported | partially_supported | not_supported",
  "rationale": "short"
}}

Definitions:
- correctness: whether the answer matches the reference answer.
- faithfulness: whether the answer avoids unsupported claims.
- answer_support: whether retrieved evidence supports the answer.

Question: {question}
Reference answer: {reference_answer}
Generated answer: {generated_answer}

Retrieved context:
{context_text}
""".strip()

        raw = ""
        try:
            raw = generator._call_llm(prompt)
            payload = _json_or_empty(raw)
            return {
                "correctness": str(payload.get("correctness") or "incorrect").strip(),
                "faithfulness": str(payload.get("faithfulness") or "hallucinated").strip(),
                "answer_support": str(payload.get("answer_support") or "not_supported").strip(),
                "rationale": str(payload.get("rationale") or "").strip(),
            }
        except Exception as exc:
            logger.warning("QA judge failed: %s", exc)
            return {
                "correctness": "incorrect",
                "faithfulness": "hallucinated",
                "answer_support": "not_supported",
                "rationale": f"Error: {exc}",
            }

    def _generate_answer(
        self,
        generator: Any,
        question: str,
        retrieved_context: Sequence[Dict[str, Any]],
    ) -> str:
        """Generate answer using retrieved context."""
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
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        return generator._call_llm(combined_prompt, image_paths=None)

    def _run_retrieval(
        self,
        question: str,
        top_k: int,
        retriever_type: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Run retrieval using SearchOrchestrator - searches ALL active documents in DB."""
        out = SearchOrchestrator(self.cfg, user_id=self.user_id).run(
            query=question,
            top_k=top_k,
            retriever_type=retriever_type,
            include_images=False,
            images_for_generation=0,
            mode="retrieval_only",
            search_scope="text",
            generation_model=None,
            skip_reranker=True,
        )

        retrieved: List[Dict[str, Any]] = []
        for item in out.get("text_results") or []:
            retrieved.append({
                "id": item.get("id"),
                "source": item.get("source"),
                "score": item.get("score"),
                "rank": item.get("rank"),
                "retrieval_type": retriever_type,
                "text": item.get("text") or item.get("full_text") or "",
                "full_text": item.get("text") or item.get("full_text") or "",
                "metadata": item.get("metadata") or {},
            })

        telemetry = out.get("telemetry") or {}
        return retrieved, telemetry

    def create_run(
        self,
        *,
        run_id: str | None = None,
        questions_per_section: int = 10,
        max_documents: int | None = None,
        max_sections_per_document: int | None = None,
        top_k: int = 10,
        retriever_type: str = "hybrid",
        provider: str = "openai",
        model: str | None = None,
    ) -> Dict[str, Any]:
        """Create and run a document intelligence evaluation."""

        run_id = run_id or self.new_run_id()
        generator = _generation_config(self.cfg, provider, model)

        # Get active documents (for question generation only)
        docs = self._active_documents(max_documents=max_documents)

        if not docs:
            raise ValueError("No active documents found for evaluation")

        # Flatten sections from each document's markdown
        doc_sections: Dict[str, List[Dict[str, Any]]] = {}
        for doc in docs:
            sections = self._flatten_sections_from_markdown(doc.get("context", ""), doc["doc_id"])
            if max_sections_per_document is not None:
                sections = sections[:max_sections_per_document]
            doc_sections[doc["doc_id"]] = sections

        # Print summary
        total_sections = sum(len(sections) for sections in doc_sections.values())
        total_questions = total_sections * questions_per_section
        logger.info(
            f"Starting evaluation: {len(docs)} documents, "
            f"{total_sections} total sections, "
            f"up to {total_questions} questions"
        )

        # Run evaluation
        all_results: List[Dict[str, Any]] = []

        for doc_idx, doc in enumerate(docs, 1):
            doc_id = doc["doc_id"]
            sections = doc_sections.get(doc_id, [])
            logger.info(
                f"Processing document {doc_idx}/{len(docs)}: {doc['display_name']} "
                f"({doc_id}) - {len(sections)} sections"
            )

            for section_idx, section in enumerate(sections, 1):
                section_text = section.get("source_text", "")

                # Skip sections with too little content (< 100 chars)
                if len(section_text) < 100:
                    logger.info(
                        f"  Section {section_idx}/{len(sections)}: {section.get('heading_text', 'Untitled')} - "
                        f"SKIPPED (only {len(section_text)} chars, minimum 100 required)"
)
                    continue

                logger.info(
                    f"  Section {section_idx}/{len(sections)}: {section.get('heading_text', 'Untitled')}"
                )

                # Generate QA pairs
                pairs = self._generate_qa_pairs(generator, section, questions_per_section)

                for q_idx, pair in enumerate(pairs[:questions_per_section], 1):
                    question = pair.get("question", "").strip()
                    reference_answer = pair.get("reference_answer", "").strip()

                    if not question:
                        continue

                    logger.info(
                        f"    Question {q_idx}/{questions_per_section}: "
                        f"{question[:60]}{'...' if len(question) > 60 else ''}"
                    )

                    # Run retrieval (searches across ALL active documents in DB, not just this doc)
                    retrieved, telemetry = self._run_retrieval(question, top_k, retriever_type)
                    logger.info(f"      Retrieved {len(retrieved)} chunks")

                    # Generate answer
                    generated_answer = self._generate_answer(generator, question, retrieved)
                    logger.info(f"      Generated answer: {len(generated_answer)} chars")

                    # Judge QA
                    judge_result = self._judge_qa(
                        generator,
                        question=question,
                        reference_answer=reference_answer,
                        retrieved_context=retrieved,
                        generated_answer=generated_answer,
                    )

                    logger.info(f"      Judge: {judge_result.get('correctness', 'unknown')}")

                    all_results.append({
                        "doc_id": doc_id,
                        "section_id": section["section_id"],
                        "question_index": q_idx,
                        "question": question,
                        "reference_answer": reference_answer,
                        "source_section_text": section.get("source_text", ""),
                        "generated_answer": generated_answer,
                        "judge_result": judge_result,
                        "retrieved_context": retrieved,
                        "telemetry": telemetry,
                    })

        logger.info(f"Completed evaluation: {len(all_results)} questions processed")

        # Compute summary metrics
        distributions = self._compute_distributions(all_results)

        run = {
            "run_id": run_id,
            "user_id": self.user_id,
            "status": "completed",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "config": {
                "questions_per_section": questions_per_section,
                "max_documents": max_documents,
                "max_sections_per_document": max_sections_per_document,
                "top_k": top_k,
                "retriever_type": retriever_type,
                "provider": provider,
                "model": model if model else self.cfg.get("generation", {}).get("model"),
            },
            "active_files": [{"doc_id": d["doc_id"], "display_name": d["display_name"], "total_files": d["total_files"]} for d in docs],
            "results": all_results,
            "summary": {
                "distributions": distributions,
                "total_questions": len(all_results),
                "total_documents": len(docs),
                "total_sections": sum(len(s) for s in doc_sections.values()),
            },
        }

        return self.save_run(run)

    def _compute_distributions(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
        """Compute distributions for correctness, faithfulness and answer support."""
        distributions: Dict[str, Dict[str, int]] = {
            "correctness": {},
            "faithfulness": {},
            "answer_support": {},
        }

        for result in results:
            judge_result = result.get("judge_result", {})

            # Correctness distribution
            correctness = judge_result.get("correctness", "incorrect")
            distributions["correctness"][correctness] = distributions["correctness"].get(correctness, 0) + 1

            # Faithfulness distribution
            faithfulness = judge_result.get("faithfulness", "hallucinated")
            distributions["faithfulness"][faithfulness] = distributions["faithfulness"].get(faithfulness, 0) + 1

            # Answer support distribution
            answer_support = judge_result.get("answer_support", "not_supported")
            distributions["answer_support"][answer_support] = distributions["answer_support"].get(answer_support, 0) + 1

        return distributions
