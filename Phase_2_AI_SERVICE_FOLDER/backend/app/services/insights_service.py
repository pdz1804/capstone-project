"""LLM-backed insights: summaries, MCQs, learning paths (SRS FR-016–FR-020)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.core.paths import BACKEND_ROOT, DOCUMENTS_JSON_PATH
from app.services.text_search_service import TextSearchService, _load_doc_map

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


def _context_from_query(cfg: Dict[str, Any], query: str, top_k: int) -> str:
    ts = TextSearchService(cfg)
    hits = ts.search(query, "hybrid", top_k)
    dm = _load_doc_map(DOCUMENTS_JSON_PATH)
    parts: List[str] = []
    for h in hits:
        cid = str(h.get("id", ""))
        text = (dm.get(cid) or {}).get("text") or h.get("text", "")
        src = h.get("source", "")
        parts.append(f"---\nSource: {src}\n{text[:6000]}")
    return "\n".join(parts) if parts else ""


class InsightsService:
    def __init__(self, yaml_config: Dict[str, Any]):
        self.cfg = yaml_config

    def lecture_summary(
        self,
        focus_query: str = "",
        depth: str = "detailed",
        top_k: int = 12,
    ) -> Dict[str, Any]:
        """FR-016: multi-level summary from retrieved lecture chunks."""
        q = focus_query.strip() or "key concepts learning objectives definitions formulas"
        ctx = _context_from_query(self.cfg, q, top_k)
        if not ctx:
            return {"summary": "", "error": "No indexed content. Run process + index first."}
        g = _generator(self.cfg)
        prompt = (
            f"You are an educational assistant. Depth: {depth}.\n"
            "Produce a structured markdown summary with headings, bullet points, and timestamps/sources when present.\n\n"
            f"CONTENT:\n{ctx[:120000]}"
        )
        raw = g._call_llm(prompt)
        return {"summary": (raw or "").strip(), "depth": depth, "focus_query": q}

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

    def mcq_quiz(self, topic: str, num_questions: int = 5, difficulty: str = "intermediate") -> Dict[str, Any]:
        """FR-019 style adaptive MCQs from corpus."""
        ctx = _context_from_query(self.cfg, topic, top_k=15)
        if not ctx:
            return {"questions": [], "error": "No indexed content."}
        prompt = (
            f"Create {num_questions} multiple-choice questions about: {topic}.\n"
            f"Difficulty: {difficulty}. Use only the content below.\n"
            "Return JSON array of objects with keys: question, options (array of 4 strings), correct_index (0-3), explanation.\n\n"
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
            return {"questions": questions, "topic": topic, "difficulty": difficulty}
        except Exception:
            return {"questions": [], "raw": text, "topic": topic}

    def learning_roadmap(self, student_profile: str, goals: str) -> Dict[str, Any]:
        """FR-018 style roadmap."""
        ctx = _context_from_query(self.cfg, goals, top_k=12)
        prompt = (
            f"Student profile: {student_profile}\nGoals: {goals}\n\n"
            "Given the course content excerpts below, propose a concise learning roadmap: prerequisites, ordered topics, and suggested review areas.\n"
            "Use markdown.\n\n"
            f"CONTENT:\n{ctx[:80000]}"
        )
        return {"roadmap": self._openai_direct(prompt) or ""}

    def analytics_placeholder(self) -> Dict[str, Any]:
        """FR-020: requires session store — schema only for now."""
        return {
            "message": "Performance analytics need persisted quiz sessions; endpoint reserved for future work.",
            "metrics": [],
        }
