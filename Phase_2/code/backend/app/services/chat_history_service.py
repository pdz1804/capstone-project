from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.repositories.chat_history_repository_dynamo import DynamoChatHistoryRepository


class ChatHistoryService:
    def __init__(self, repo: DynamoChatHistoryRepository) -> None:
        self.repo = repo

    @classmethod
    def from_env(cls) -> ChatHistoryService:
        return cls(DynamoChatHistoryRepository.from_env())

    def ensure_session(
        self,
        *,
        user_id: str,
        session_id: str,
        title: str | None = None,
        pinned: bool = False,
    ) -> Dict[str, Any]:
        return self.repo.create_session(user_id=user_id, session_id=session_id, title=title, pinned=pinned)

    def get_session(self, *, user_id: str, session_id: str) -> Dict[str, Any] | None:
        return self.repo.get_session(user_id=user_id, session_id=session_id)

    def list_sessions(
        self,
        *,
        user_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> Tuple[List[Dict[str, Any]], str | None]:
        return self.repo.list_sessions(user_id=user_id, limit=limit, cursor=cursor)

    def update_session(
        self,
        *,
        user_id: str,
        session_id: str,
        title: str | None = None,
        pinned: bool | None = None,
    ) -> Dict[str, Any] | None:
        return self.repo.update_session(user_id=user_id, session_id=session_id, title=title, pinned=pinned)

    def put_message(
        self,
        *,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        traces: list[dict[str, Any]] | None = None,
        suggestions: list[str] | None = None,
        message_id: str | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        return self.repo.put_message(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            traces=traces,
            suggestions=suggestions,
            message_id=message_id,
            attachments=attachments,
        )

    def get_message(self, *, user_id: str, session_id: str, message_id: str) -> Dict[str, Any] | None:
        session = self.get_session(user_id=user_id, session_id=session_id)
        if not session:
            return None
        row = self.repo.get_message(session_id=session_id, message_id=message_id)
        if not row:
            return None
        row_uid = str(row.get("user_id") or "")
        if row_uid and row_uid != str(user_id):
            return None
        return row

    def list_messages(
        self,
        *,
        user_id: str,
        session_id: str,
        limit: int = 50,
        cursor: str | None = None,
        newest_first: bool = True,
    ) -> Tuple[List[Dict[str, Any]], str | None]:
        session = self.get_session(user_id=user_id, session_id=session_id)
        if not session:
            return [], None
        return self.repo.list_messages(
            session_id=session_id,
            limit=limit,
            cursor=cursor,
            newest_first=newest_first,
        )

    def list_recent_messages(
        self,
        *,
        user_id: str,
        session_id: str,
        limit: int = 8,
    ) -> List[Dict[str, Any]]:
        items, _ = self.list_messages(
            user_id=user_id,
            session_id=session_id,
            limit=limit,
            newest_first=True,
        )
        return list(reversed(items))

    def delete_session(self, *, user_id: str, session_id: str) -> bool:
        session = self.get_session(user_id=user_id, session_id=session_id)
        if not session:
            return False
        self.repo.delete_session(user_id=user_id, session_id=session_id)
        return True
