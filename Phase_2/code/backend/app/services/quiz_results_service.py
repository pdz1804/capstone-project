from __future__ import annotations

from typing import Any, Dict, List

from app.repositories.quiz_results_repository_dynamo import DynamoQuizResultsRepository


class QuizResultsService:
    def __init__(self, repo: DynamoQuizResultsRepository) -> None:
        self.repo = repo

    @classmethod
    def from_env(cls) -> QuizResultsService:
        return cls(DynamoQuizResultsRepository.from_env())

    def list_for_user(self, user_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        return self.repo.list_attempts(user_id=user_id, limit=limit)

    def create_for_user(
        self,
        *,
        user_id: str,
        score: int,
        total: int,
        file_id: int | None = None,
        document_id: str | None = None,
        quiz_topic: str | None = None,
    ) -> Dict[str, Any]:
        return self.repo.create_attempt(
            user_id=user_id,
            score=score,
            total=total,
            file_id=file_id,
            document_id=document_id,
            quiz_topic=quiz_topic,
        )
