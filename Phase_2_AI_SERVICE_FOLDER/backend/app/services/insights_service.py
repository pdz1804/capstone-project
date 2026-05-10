"""LLM-backed insights: summaries, MCQs, learning paths (SRS FR-016–FR-020)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.core.paths import BACKEND_ROOT
from app.services.processed_markdown_service import (
    gather_processed_markdown_context,
    sanitize_insights_document_id,
)

logger = logging.getLogger(__name__)


def _generator(cfg: Dict[str, Any]):
    from src.generation.generator import GenerationConfig, RAGGenerator

    gyaml = cfg.get("generation", {}) or {}
    gc = GenerationConfig(
        provider=str(gyaml.get("provider", "openai")),
        model_name=str(gyaml.get("model", "gpt-4o-mini")),
        api_key=gyaml.get("api_key"),
        base_url=gyaml.get("base_url"),
        temperature=float(gyaml.get("temperature", 0.2)),
        max_tokens=int(gyaml.get("max_tokens", 3000)),
        enable_citations=False,
        base_dir=str(BACKEND_ROOT),
    )
    return RAGGenerator(gc)


class InsightsService:
    def __init__(self, yaml_config: Dict[str, Any], user_id: str | None = None):
        self.cfg = yaml_config
        self._user_id = user_id

    def lecture_summary(
        self,
        focus_query: str = "",
        depth: str = "detailed",
        top_k: int = 12,
        document_id: str | None = None,
        tone: str = "neutral",
        target_length: str = "medium",
    ) -> Dict[str, Any]:
        """FR-016: summary from processed pipeline markdown (stage3/stage4), not vector search."""
        _ = top_k  # API compatibility; context is full markdown files (capped), not top-k chunks.
        q = focus_query.strip()
        raw_doc = (document_id or "").strip()
        doc = sanitize_insights_document_id(document_id)
        if raw_doc and doc is None:
            return {
                "summary": "",
                "error": "Invalid document_id: use the folder name under Processed files (no slashes or ..).",
            }
        ctx = gather_processed_markdown_context(self._user_id, doc, 120_000)
        if not ctx.strip():
            return {
                "summary": "",
                "error": (
                    "No processed markdown found. Run **Process** so stage 3 outputs `.md` under "
                    "`processing/stage3_document_processed/`. "
                    + (
                        f"If you scoped to one document, ensure folder name matches: {doc!r}."
                        if doc
                        else "Optionally select a document in the UI to scope to one folder."
                    )
                ),
            }
        g = _generator(self.cfg)
        length_hint = {
            "short": "Keep the summary concise (roughly 2–4 short sections).",
            "medium": "Aim for balanced coverage (several sections with bullets).",
            "long": "Be thorough with multiple sections and sub-bullets where helpful.",
        }.get((target_length or "medium").lower(), "Balanced length.")
        tone_hint = {
            "formal": "Use a formal academic tone.",
            "friendly": "Use a friendly, encouraging tone suitable for students.",
            "neutral": "Use a clear neutral instructional tone.",
        }.get((tone or "neutral").lower(), "Clear neutral instructional tone.")
        focus_line = (
            f"The learner asked to emphasize: {q}\n" if q else ""
        )
        prompt = (
            f"You are an educational assistant. Depth: {depth}. {tone_hint} {length_hint}\n"
            f"{focus_line}"
            "Produce a structured markdown summary with headings, bullet points, and cite file names from the content when useful.\n\n"
            f"CONTENT (processed document markdown from the pipeline, not search snippets):\n{ctx[:120000]}"
        )
        raw = g._call_llm(prompt)
        return {
            "summary": (raw or "").strip(),
            "depth": depth,
            "focus_query": q or None,
            "document_id": doc,
            "tone": tone,
            "target_length": target_length,
        }

    def _openai_direct(self, prompt: str) -> str:
        gyaml = self.cfg.get("generation", {}) or {}
        if (gyaml.get("provider") or "openai") != "openai":
            return ""
        try:
            from openai import OpenAI

            client = OpenAI()
            r = client.chat.completions.create(
                model=str(gyaml.get("model", "gpt-4o-mini")),
                messages=[{"role": "user", "content": prompt}],
                temperature=float(gyaml.get("temperature", 0.2)),
                max_tokens=min(int(gyaml.get("max_tokens", 3000)), 4096),
            )
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning("LLM call failed: %s", e)
            return ""

    def mcq_quiz(
        self,
        topic: str,
        num_questions: int = 5,
        difficulty: str = "intermediate",
        document_id: str | None = None,
        question_style: str = "exam",
        include_explanations: bool = True,
    ) -> Dict[str, Any]:
        """FR-019 style MCQs from processed markdown (same source as summaries)."""
        raw_doc = (document_id or "").strip()
        doc = sanitize_insights_document_id(document_id)
        if raw_doc and doc is None:
            return {"questions": [], "error": "Invalid document_id (folder name only)."}
        ctx = gather_processed_markdown_context(self._user_id, doc, 100_000)
        if not ctx.strip():
            return {"questions": [], "error": "No processed markdown. Run process first."}
        style_hint = {
            "exam": "Write questions in an exam style: clear stems, one best answer, plausible distractors.",
            "conceptual": "Emphasize definitions, relationships, and 'why' questions.",
            "mixed": "Mix recall, application, and short scenario-based questions.",
        }.get((question_style or "exam").lower(), "Exam-style clarity.")
        exp_line = (
            "Each object must include keys: question, options (array of 4 strings), correct_index (0-3), explanation (1-2 sentences)."
            if include_explanations
            else "Each object must include keys: question, options (array of 4 strings), correct_index (0-3). Do not include explanation."
        )
        prompt = (
            f"Create {num_questions} multiple-choice questions about: {topic}.\n"
            f"Difficulty: {difficulty}. {style_hint}\n"
            f"{exp_line}\n"
            "Use only the processed document markdown below. Return a JSON array.\n\n"
            f"CONTENT:\n{ctx[:100000]}"
        )
        text = self._openai_direct(prompt)
        try:
            import json

            # strip markdown fences if any
            t = text.strip()
            if t.startswith("```"):
                t = t.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            questions = json.loads(t)
            if isinstance(questions, dict) and "questions" in questions:
                questions = questions["questions"]
            return {
                "questions": questions,
                "topic": topic,
                "difficulty": difficulty,
                "document_id": doc,
                "question_style": question_style,
                "include_explanations": include_explanations,
            }
        except Exception:
            return {
                "questions": [],
                "raw": text,
                "topic": topic,
                "document_id": doc,
                "question_style": question_style,
            }

    def learning_roadmap(
        self,
        student_profile: str,
        goals: str,
        document_id: str | None = None,
    ) -> Dict[str, Any]:
        """FR-018 style roadmap from processed markdown."""
        raw_doc = (document_id or "").strip()
        doc = sanitize_insights_document_id(document_id)
        if raw_doc and doc is None:
            return {
                "roadmap": "",
                "error": "Invalid document_id (folder name only).",
                "document_id": None,
            }
        ctx = gather_processed_markdown_context(self._user_id, doc, 80_000)
        if not ctx.strip():
            return {
                "roadmap": "",
                "error": "No processed markdown. Run process first.",
                "document_id": doc,
            }
        prompt = (
            f"Student profile: {student_profile}\nGoals: {goals}\n\n"
            "Given the processed course markdown below, propose a concise learning roadmap: prerequisites, ordered topics, and suggested review areas.\n"
            "Use markdown.\n\n"
            f"CONTENT:\n{ctx[:80000]}"
        )
        return {"roadmap": self._openai_direct(prompt) or "", "document_id": doc}

    def analytics_placeholder(self) -> Dict[str, Any]:
        """FR-020: requires session store   schema only for now."""
        return {
            "message": "Performance analytics need persisted quiz sessions; endpoint reserved for future work.",
            "metrics": [],
        }
