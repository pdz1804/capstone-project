"""LLM-backed insights: summaries, MCQs, learning paths (SRS FR-016–FR-020)."""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from app.core.paths import BACKEND_ROOT
from app.services.processed_markdown_service import (
    gather_processed_markdown_context,
    gather_processed_markdown_context_with_images,
    sanitize_insights_document_id,
)

logger = logging.getLogger(__name__)

_DEFAULT_GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image-preview"


def _build_gemini_image_config(types: Any) -> Any | None:
    """Match studio defaults: 16:9, 1K; tolerate older SDKs."""
    ImageConfig = getattr(types, "ImageConfig", None)
    if ImageConfig is None:
        return None
    candidates = [
        {"aspect_ratio": "16:9", "image_size": "1K"},
    ]
    for kwargs in candidates:
        try:
            return ImageConfig(**kwargs)
        except Exception:
            continue
    try:
        return ImageConfig(aspect_ratio="16:9")
    except Exception:
        try:
            return ImageConfig()
        except Exception:
            return None


def _call_gemini_infographic_image(prompt: str) -> Tuple[bytes | None, str | None, str, str | None]:
    """Return ``(image_bytes, mime_type, model_text, error)`` — streams may emit TEXT and IMAGE parts."""
    key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not key:
        return None, None, "", "GEMINI_API_KEY is not set"
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        return None, None, "", f"google-genai is not installed: {e}"

    model = (os.environ.get("GEMINI_IMAGE_MODEL") or _DEFAULT_GEMINI_IMAGE_MODEL).strip()
    client = genai.Client(api_key=key)

    config_kwargs: Dict[str, Any] = {"response_modalities": ["IMAGE", "TEXT"]}
    img_cfg = _build_gemini_image_config(types)
    if img_cfg is not None:
        config_kwargs["image_config"] = img_cfg
    try:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="MINIMAL")
    except Exception:
        pass

    try:
        config = types.GenerateContentConfig(**config_kwargs)
    except Exception:
        try:
            config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
        except Exception:
            return None, None, "", "Could not build GenerateContentConfig"

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        ),
    ]

    text_fragments: list[str] = []
    last_image: tuple[bytes, str] | None = None

    try:
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        ):
            ct = getattr(chunk, "text", None)
            if ct:
                text_fragments.append(str(ct))
            parts = getattr(chunk, "parts", None)
            if not parts:
                continue
            for part in parts:
                pt = getattr(part, "text", None)
                if pt:
                    text_fragments.append(str(pt))
                inline = getattr(part, "inline_data", None)
                if not inline:
                    continue
                raw = getattr(inline, "data", None)
                if not raw:
                    continue
                data_bytes: bytes
                if isinstance(raw, str):
                    data_bytes = base64.b64decode(raw)
                else:
                    data_bytes = raw
                mime = getattr(inline, "mime_type", None) or "image/png"
                last_image = (data_bytes, mime)
    except Exception as e:
        logger.warning("Gemini image stream failed: %s", e)
        return None, None, "".join(text_fragments).strip(), str(e)

    model_text = "".join(text_fragments).strip()
    if last_image:
        return last_image[0], last_image[1], model_text, None
    detail = f" Model output (text only): {model_text[:800]}" if model_text else ""
    return None, None, model_text, f"No image in model response.{detail}"


def _estimate_tokens(text: str) -> int:
    return max(1, int(len((text or "").strip()) / 4))


def _generation_model_id(cfg: Dict[str, Any]) -> str:
    gyaml = cfg.get("generation", {}) or {}
    return str(gyaml.get("model", "gpt-4o-mini"))


def _cleanup_summary_temp_images(image_paths: list[str]) -> None:
    for image_path in image_paths or []:
        p = Path(image_path)
        if not p.name.startswith("summary_frame_"):
            continue
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


def _generator(cfg: Dict[str, Any]):
    from src.generation.generator import GenerationConfig, RAGGenerator

    gyaml = cfg.get("generation", {}) or {}
    gc = GenerationConfig(
        provider=str(gyaml.get("provider", "openai")),
        model_name=str(gyaml.get("model", "gpt-4o-mini")),
        api_key=gyaml.get("api_key"),
        base_url=gyaml.get("base_url"),
        bedrock_region=(gyaml.get("bedrock_region") or None),
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
        max_summary_images = int(os.getenv("SUMMARY_MAX_IMAGES", "8") or "8")
        ctx, image_paths = gather_processed_markdown_context_with_images(
            self._user_id,
            doc,
            120_000,
            max_images=max(0, max_summary_images),
        )
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
            + (
                "Representative lecture frames are attached as images. Use them together with the transcript text to identify slide content, diagrams, and visual emphasis.\n\n"
                if image_paths
                else ""
            )
            + f"CONTENT (processed document markdown from the pipeline, not search snippets):\n{ctx[:120000]}"
        )
        try:
            raw, error = self._llm_text_or_error(prompt, image_paths=image_paths)
        finally:
            _cleanup_summary_temp_images(image_paths)
        if error:
            return {
                "summary": "",
                "error": error,
                "depth": depth,
                "focus_query": q or None,
                "document_id": doc,
                "tone": tone,
                "target_length": target_length,
            }
        return {
            "summary": (raw or "").strip(),
            "depth": depth,
            "focus_query": q or None,
            "document_id": doc,
            "tone": tone,
            "target_length": target_length,
            "usage": {
                "model_id": _generation_model_id(self.cfg),
                "token_in": _estimate_tokens(prompt),
                "token_out": _estimate_tokens(raw or ""),
                "images_in": len(image_paths),
            },
        }

    def lecture_visualization(
        self,
        document_id: str | None = None,
        topic: str = "",
        retrieved_context: str | None = None,
    ) -> Dict[str, Any]:
        """One-shot infographic from processed markdown and/or retrieved snippets (Gemini image)."""
        topic_q = (topic or "").strip()
        raw_doc = (document_id or "").strip()
        doc = sanitize_insights_document_id(document_id)
        if raw_doc and doc is None:
            return {
                "image_base64": "",
                "mime_type": "",
                "model_text": "",
                "error": "Invalid document_id: use the folder name under Processed files (no slashes or ..).",
            }

        if retrieved_context is not None:
            ctx = (retrieved_context or "").strip()
            if not ctx:
                return {
                    "image_base64": "",
                    "mime_type": "",
                    "model_text": "",
                    "error": "No retrieved content to visualize.",
                }
            source_note = (
                "Content source: retrieved excerpts from the student's indexed lecture materials only — "
                "do not invent facts beyond this text."
            )
        else:
            ctx = gather_processed_markdown_context(self._user_id, doc, 100_000)
            if not ctx.strip():
                return {
                    "image_base64": "",
                    "mime_type": "",
                    "model_text": "",
                    "error": (
                        "No processed markdown found. Run **Process** first. "
                        "From chat, ensure **Build Index** is done so retrieval can supply snippets when "
                        "no document_id is set."
                    ),
                }
            source_note = (
                "Content source: processed lecture markdown from the pipeline for this document scope — "
                "do not invent facts beyond this text."
            )

        focus = f"The learner asked to emphasize: {topic_q}\n\n" if topic_q else ""
        brand = (
            "Create ONE clear, educational infographic or study poster summarizing the CONTENT below. "
            "Style: modern, high contrast, readable labels, simple icons or shapes where helpful.\n"
            "Use this palette as the dominant accents (hex): "
            "primary sky #0ea5e9, deep sky #0284c7, accent #0369a1, "
            "panel backgrounds #f0f9ff and #e0f2fe, body text #0f172a and #334155, borders #bae6fd.\n"
            "Place a small, readable watermark in the bottom-right corner with the exact plain text: BK-MInD "
            "(no asterisks, no markdown, no ** bold syntax — letters only).\n"
            "Avoid illegible micro-text; no decorative clutter.\n\n"
            f"{source_note}\n\n"
            f"{focus}"
            "CONTENT:\n"
        )
        full_prompt = brand + ctx[:100_000]

        image_bytes, mime, model_text, err = _call_gemini_infographic_image(full_prompt)
        model_id = (os.environ.get("GEMINI_IMAGE_MODEL") or _DEFAULT_GEMINI_IMAGE_MODEL).strip()
        if err:
            return {
                "image_base64": "",
                "mime_type": "",
                "model_text": model_text or "",
                "error": err,
                "document_id": doc,
                "topic": topic_q or None,
            }
        if not image_bytes:
            return {
                "image_base64": "",
                "mime_type": "",
                "model_text": model_text or "",
                "error": "Empty image payload from model.",
                "document_id": doc,
                "topic": topic_q or None,
            }
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        return {
            "image_base64": b64,
            "mime_type": mime or "image/png",
            "model_text": model_text or "",
            "error": None,
            "document_id": doc,
            "topic": topic_q or None,
            "usage": {
                "model_id": model_id,
                "token_in": _estimate_tokens(full_prompt),
                "token_out": _estimate_tokens(model_text or "") + 1,
            },
        }

    def _llm_text_or_error(
        self,
        prompt: str,
        generator=None,
        image_paths: list[str] | None = None,
    ) -> Tuple[str, str | None]:
        try:
            gen = generator or _generator(self.cfg)
            return (gen._call_llm(prompt, image_paths=image_paths or []) or "").strip(), None
        except Exception as e:
            if image_paths:
                logger.warning("Multimodal LLM call failed, retrying summary without images: %s", e)
                try:
                    gen = generator or _generator(self.cfg)
                    return (gen._call_llm(prompt, image_paths=[]) or "").strip(), None
                except Exception as retry_error:
                    logger.warning("LLM text-only retry failed: %s", retry_error)
                    return "", str(retry_error)
            logger.warning("LLM call failed: %s", e)
            return "", str(e)

    def _llm_plain(self, prompt: str) -> str:
        text, _ = self._llm_text_or_error(prompt)
        return text

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
        text, error = self._llm_text_or_error(prompt)
        if error:
            return {
                "questions": [],
                "error": error,
                "topic": topic,
                "difficulty": difficulty,
                "document_id": doc,
                "question_style": question_style,
                "include_explanations": include_explanations,
            }
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
                "usage": {
                    "model_id": _generation_model_id(self.cfg),
                    "token_in": _estimate_tokens(prompt),
                    "token_out": _estimate_tokens(text or ""),
                },
            }
        except Exception:
            return {
                "questions": [],
                "raw": text,
                "topic": topic,
                "document_id": doc,
                "question_style": question_style,
                "usage": {
                    "model_id": _generation_model_id(self.cfg),
                    "token_in": _estimate_tokens(prompt),
                    "token_out": _estimate_tokens(text or ""),
                },
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
        roadmap = self._llm_plain(prompt) or ""
        return {
            "roadmap": roadmap,
            "document_id": doc,
            "usage": {
                "model_id": _generation_model_id(self.cfg),
                "token_in": _estimate_tokens(prompt),
                "token_out": _estimate_tokens(roadmap),
            },
        }

    def analytics_placeholder(self) -> Dict[str, Any]:
        """FR-020: requires session store — schema only for now."""
        return {
            "message": "Performance analytics need persisted quiz sessions; endpoint reserved for future work.",
            "metrics": [],
        }
