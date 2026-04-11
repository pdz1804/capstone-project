from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

from app.repositories.feedback_repository_dynamo import DynamoFeedbackRepository

logger = logging.getLogger(__name__)


ALLOWED_CATEGORIES: List[str] = [
    "Content Quality",
    "Feature & Scope",
    "Model Intelligence",
    "Safety & Security",
    "Uncategorized",
    "User Experience",
]

DEFAULT_CLASSIFIER_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


class FeedbackService:
    _executor = ThreadPoolExecutor(max_workers=2)

    def __init__(self, repo: DynamoFeedbackRepository) -> None:
        self.repo = repo

    @classmethod
    def from_env(cls) -> "FeedbackService":
        return cls(DynamoFeedbackRepository.from_env())

    def list_for_user(
        self,
        *,
        user_id: str,
        limit: int = 30,
        cursor: str | None = None,
        category: str | None = None,
        session_id: str | None = None,
    ) -> Tuple[List[Dict[str, Any]], str | None]:
        return self.repo.list_feedback(
            user_id=user_id,
            limit=limit,
            cursor=cursor,
            category=category,
            session_id=session_id,
        )

    def get_for_user(self, *, user_id: str, feedback_id: str) -> Dict[str, Any] | None:
        return self.repo.get_feedback(user_id=user_id, feedback_id=feedback_id)

    def create_for_user(
        self,
        *,
        user_id: str,
        vote: str,
        query: str,
        response: str,
        session_id: str | None = None,
        message_id: str | None = None,
        reason_code: str | None = None,
        reason_text: str | None = None,
        scope: str | None = None,
        feedback_text: str | None = None,
    ) -> Dict[str, Any]:
        return self.repo.create_feedback(
            user_id=user_id,
            vote=vote,
            query=query,
            response=response,
            session_id=session_id,
            message_id=message_id,
            reason_code=reason_code,
            reason_text=reason_text,
            scope=scope,
            feedback_text=feedback_text,
        )

    def schedule_analysis(self, *, user_id: str, feedback_id: str) -> None:
        def _run() -> None:
            self._analyze_and_update(user_id=user_id, feedback_id=feedback_id)

        FeedbackService._executor.submit(_run)

    def _analyze_and_update(self, *, user_id: str, feedback_id: str) -> None:
        item = self.repo.get_feedback(user_id=user_id, feedback_id=feedback_id)
        if not item:
            return

        model_id = (os.getenv("FEEDBACK_CLASSIFIER_MODEL") or DEFAULT_CLASSIFIER_MODEL).strip() or DEFAULT_CLASSIFIER_MODEL
        try:
            category, sub_category, suggested_action, summary = self._classify_with_bedrock(item=item, model_id=model_id)
            self.repo.update_analysis(
                user_id=user_id,
                feedback_id=feedback_id,
                category=category,
                sub_category=sub_category,
                suggested_action=suggested_action,
                analysis_summary=summary,
                classifier_model=model_id,
                classification_status="completed",
                classification_error=None,
            )
        except Exception as e:
            logger.warning("Feedback classification failed for %s/%s: %s", user_id, feedback_id, e)
            self.repo.update_analysis(
                user_id=user_id,
                feedback_id=feedback_id,
                category="Uncategorized",
                sub_category="Classification failed",
                suggested_action="Review this feedback manually and triage in next sprint planning.",
                analysis_summary="Automatic classification failed.",
                classifier_model=model_id,
                classification_status="failed",
                classification_error=str(e)[:500],
            )

    def _classify_with_bedrock(self, *, item: Dict[str, Any], model_id: str) -> Tuple[str, str, str, str]:
        import boto3

        region = (os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION") or "us-east-1").strip()
        rt = boto3.client("bedrock-runtime", region_name=region)

        taxonomy = "\n".join(f"- {c}" for c in ALLOWED_CATEGORIES)
        prompt = f"""
You are a strict feedback triage classifier for an educational RAG application.
Classify ONE feedback item into exactly one category and suggest an actionable developer fix.

Allowed categories:
{taxonomy}

Feedback payload:
- vote: {item.get('vote')}
- scope: {item.get('scope')}
- feedback_text: {item.get('feedback_text')}
- reason_code: {item.get('reason_code')}
- reason_text: {item.get('reason_text')}
- user_query: {item.get('query')}
- ai_response: {item.get('response')}

Output JSON only with keys:
{{
  "category": "...",
  "sub_category": "...",
  "suggested_action": "...",
  "analysis_summary": "..."
}}

Rules:
- category must be one of allowed categories.
- suggested_action must be concrete and directly implementable.
- Keep sub_category under 60 chars.
- Keep analysis_summary under 220 chars.
""".strip()

        resp = rt.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 500, "temperature": 0.0},
        )

        out_text = ""
        msg = (resp.get("output") or {}).get("message") or {}
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("text"):
                out_text += str(block["text"])

        parsed = self._parse_json(out_text)
        category = str(parsed.get("category") or "Uncategorized").strip()
        if category not in ALLOWED_CATEGORIES:
            category = "Uncategorized"
        sub_category = str(parsed.get("sub_category") or "General").strip()[:60] or "General"
        suggested_action = str(parsed.get("suggested_action") or "Review feedback and prioritize a fix.").strip()[:1200]
        summary = str(parsed.get("analysis_summary") or "").strip()[:220]
        if not summary:
            summary = f"{category} / {sub_category}"
        return category, sub_category, suggested_action, summary

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        raw = (text or "").strip()
        if not raw:
            return {}
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            pass

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
