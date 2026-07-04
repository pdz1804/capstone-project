from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (BACKEND_ROOT, REPO_ROOT):
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)


def _ensure_optional_dependency_stubs() -> None:
    # Some route modules import optional runtime deps that may be absent in light dev envs.
    try:
        import email_validator  # type: ignore  # noqa: F401
    except Exception:
        mod = types.ModuleType("email_validator")

        class EmailNotValidError(ValueError):
            pass

        def validate_email(email: str, check_deliverability: bool = False):
            _ = check_deliverability
            normalized = str(email)
            local_part = normalized.split("@", 1)[0] if "@" in normalized else normalized
            domain = normalized.split("@", 1)[1] if "@" in normalized else "example.com"
            return types.SimpleNamespace(
                email=normalized,
                normalized=normalized,
                local_part=local_part,
                domain=domain,
            )

        mod.EmailNotValidError = EmailNotValidError
        mod.validate_email = validate_email
        mod.__dict__["__all__"] = ["EmailNotValidError", "validate_email"]
        sys.modules["email_validator"] = mod
        try:
            import importlib.metadata as _ilm

            _orig_version = _ilm.version

            def _patched_version(dist_name: str) -> str:
                if str(dist_name) == "email-validator":
                    return "2.0.0"
                return _orig_version(dist_name)

            _ilm.version = _patched_version  # type: ignore[assignment]
        except Exception:
            pass

    try:
        from botocore.exceptions import ClientError  # type: ignore  # noqa: F401
    except Exception:
        botocore_mod = types.ModuleType("botocore")
        exc_mod = types.ModuleType("botocore.exceptions")

        class ClientError(Exception):
            def __init__(self, error_response=None, operation_name: str = ""):
                super().__init__(f"ClientError: {operation_name}")
                self.response = error_response or {}
                self.operation_name = operation_name

        exc_mod.ClientError = ClientError
        botocore_mod.exceptions = exc_mod
        sys.modules["botocore"] = botocore_mod
        sys.modules["botocore.exceptions"] = exc_mod


_ensure_optional_dependency_stubs()


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run_check(name: str, fn) -> None:
    print(f"[CHECK] {name}")
    fn()
    print(f"[PASS]  {name}")


@dataclass
class _FakeUserRow:
    uid: str
    email: str
    role: str = "student"
    isActive: bool = True

    def model_dump(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "email": self.email,
            "role": self.role,
            "isActive": self.isActive,
        }


class _FakeUsageService:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def list_usage(self, **kwargs):
        self.calls.append(kwargs)
        return [{"usage_id": "u1"}, {"usage_id": "u2"}]


class _FakeUserService:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def list_users(self, **kwargs):
        self.calls.append(kwargs)
        return [
            _FakeUserRow(uid="user-1", email="u1@example.com"),
            _FakeUserRow(uid="user-2", email="u2@example.com"),
        ]


class _FakeKnowledgeService:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.sync_calls: List[List[str]] = []

    def sync_input_files_for_users(self, user_ids: List[str]):
        self.sync_calls.append(list(user_ids))
        return [{"user_id": uid, "synced": 1} for uid in user_ids]

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {"knowledge_id": "k1", "user_id": "user-1", "title": "Doc 1"},
            {"knowledge_id": "k2", "user_id": "user-2", "title": "Doc 2"},
        ]


class _FakeFeedbackService:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def list_all(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {"feedback_id": "f1", "user_id": "user-1", "vote": "like"},
            {"feedback_id": "f2", "user_id": "user-2", "vote": "general"},
        ]


def check_admin_all_record_listing() -> None:
    from app.admin import routes as admin_routes

    admin_stub = {"uid": "admin", "role": "admin"}

    usage = _FakeUsageService()
    inv = admin_routes.list_invocations(
        days=30,
        user_id=None,
        feature=None,
        model_id=None,
        limit=None,
        _admin=admin_stub,
        usage_svc=usage,
    )
    _assert(usage.calls and usage.calls[-1].get("limit") is None, "invocations did not pass limit=None")
    _assert(int(inv.get("count", 0)) == 2, "invocations count mismatch")

    users_svc = _FakeUserService()
    users = admin_routes.list_users_admin(
        skip=0,
        limit=None,
        query=None,
        role=None,
        is_active=None,
        include_usage=False,
        usage_days=30,
        _admin=admin_stub,
        user_service=users_svc,
        usage_svc=None,
    )
    _assert(users_svc.calls and users_svc.calls[-1].get("limit") is None, "users did not pass limit=None")
    _assert(int(users.get("count", 0)) == 2, "users count mismatch")

    knowledge_svc = _FakeKnowledgeService()
    knowledge = admin_routes.list_knowledge_admin(
        query=None,
        user_id=None,
        knowledge_type=None,
        is_active=None,
        limit=None,
        sync_with_storage=False,
        include_usage=False,
        usage_days=30,
        _admin=admin_stub,
        user_service=users_svc,
        knowledge_svc=knowledge_svc,
        usage_svc=None,
    )
    _assert(knowledge_svc.calls and knowledge_svc.calls[-1].get("limit") is None, "knowledge did not pass limit=None")
    _assert(int(knowledge.get("count", 0)) == 2, "knowledge count mismatch")

    sync = admin_routes.sync_knowledge_admin(
        _admin=admin_stub,
        user_service=users_svc,
        knowledge_svc=knowledge_svc,
    )
    _assert(users_svc.calls and users_svc.calls[-1].get("limit") is None, "knowledge sync did not call list_users(limit=None)")
    _assert(int(sync.get("users", 0)) == 2, "knowledge sync users mismatch")

    feedback_svc = _FakeFeedbackService()
    feedback = admin_routes.list_feedback_admin(
        limit=None,
        user_id=None,
        category=None,
        vote=None,
        is_active=None,
        query=None,
        include_usage=False,
        usage_days=30,
        _admin=admin_stub,
        feedback_svc=feedback_svc,
        usage_svc=None,
    )
    _assert(feedback_svc.calls and feedback_svc.calls[-1].get("limit") is None, "feedback did not pass limit=None")
    _assert(int(feedback.get("count", 0)) == 2, "feedback count mismatch")


def check_pptx_preview_viewer_mode() -> None:
    from app.api.routes import files_routes

    class _FakePresignClient:
        def __init__(self) -> None:
            self.calls: List[Dict[str, Any]] = []

        def generate_presigned_url(self, operation: str, Params: Dict[str, Any], ExpiresIn: int) -> str:
            self.calls.append({"operation": operation, "Params": dict(Params), "ExpiresIn": ExpiresIn})
            return "https://example.invalid/presigned"

    class _FakeS3Storage:
        def __init__(self) -> None:
            self._client = _FakePresignClient()

        def list_input_files(self):
            return [{"name": "slides.pptx", "path": "s3://demo-bucket/input/slides.pptx"}]

        def can_read_object(self, bucket: str, key: str) -> bool:
            return True

    storage = _FakeS3Storage()

    original_get_file_storage = files_routes.get_file_storage
    original_s3_class = files_routes.S3FileStorage
    try:
        files_routes.get_file_storage = lambda _user_id: storage
        files_routes.S3FileStorage = _FakeS3Storage

        office = files_routes.get_input_file_url(
            file_name="slides.pptx",
            expires_in=900,
            viewer="office",
            user_id="user-test",
        )
        _assert(str(office.get("viewer")) == "office", "office viewer response missing viewer=office")
        _assert(storage._client.calls, "office presign call missing")
        office_params = storage._client.calls[-1]["Params"]
        _assert("ResponseContentDisposition" not in office_params, "office mode should omit Content-Disposition override")
        _assert("ResponseContentType" not in office_params, "office mode should omit Content-Type override")

        standard = files_routes.get_input_file_url(
            file_name="slides.pptx",
            expires_in=900,
            viewer=None,
            user_id="user-test",
        )
        _assert(str(standard.get("mode")) == "presigned_s3", "standard presign mode mismatch")
        standard_params = storage._client.calls[-1]["Params"]
        _assert("ResponseContentDisposition" in standard_params, "standard mode should include Content-Disposition override")
    finally:
        files_routes.get_file_storage = original_get_file_storage
        files_routes.S3FileStorage = original_s3_class


def check_formula_render_path() -> None:
    from src.generation.generator import _normalize_math_delimiters

    sample = r"Inline \(a^2+b^2=c^2\) and block \[x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}\]"
    normalized = _normalize_math_delimiters(sample)
    _assert("$a^2+b^2=c^2$" in normalized, "inline math normalization failed")
    _assert("$$\nx = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}\n$$" in normalized, "block math normalization failed")

    root = Path(__file__).resolve().parents[2]
    lecture_view = (root / "frontend" / "src" / "views" / "LectureView.tsx").read_text(encoding="utf-8")
    search_view = (root / "frontend" / "src" / "views" / "SearchView.tsx").read_text(encoding="utf-8")
    main_tsx = (root / "frontend" / "src" / "main.tsx").read_text(encoding="utf-8")

    _assert("remarkMath" in lecture_view and "rehypeKatex" in lecture_view, "LectureView missing math plugins")
    _assert("remarkPlugins={LECTURE_REMARK_PLUGINS}" in lecture_view, "LectureView does not use math remark plugins")
    _assert("rehypePlugins={LECTURE_REHYPE_PLUGINS}" in lecture_view, "LectureView does not use katex rehype plugins")

    _assert("remarkMath" in search_view and "rehypeKatex" in search_view, "SearchView missing math plugins")
    _assert("remarkPlugins={SEARCH_REMARK_PLUGINS}" in search_view, "SearchView does not use math remark plugins")
    _assert("rehypePlugins={SEARCH_REHYPE_PLUGINS}" in search_view, "SearchView does not use katex rehype plugins")

    _assert("katex/dist/katex.min.css" in main_tsx, "KaTeX stylesheet is not loaded globally")


def check_reranker_disabled_guards() -> None:
    root = Path(__file__).resolve().parents[2]
    text_search = (root / "backend" / "app" / "services" / "text_search_service.py").read_text(encoding="utf-8")
    orchestrator = (root / "backend" / "app" / "services" / "search_orchestrator.py").read_text(encoding="utf-8")
    search_route = (root / "backend" / "app" / "api" / "routes" / "search_routes.py").read_text(encoding="utf-8")
    search_view = (root / "frontend" / "src" / "views" / "SearchView.tsx").read_text(encoding="utf-8")

    _assert("self._reranker_model = None" in text_search, "TextSearchService still enables reranker model")
    _assert("skip_reranker = True" in text_search, "TextSearchService does not force skip_reranker")
    _assert("skip_reranker = True" in orchestrator, "SearchOrchestrator does not force skip_reranker")
    _assert("skip_reranker=True" in search_route, "search route does not pin skip_reranker=True")
    _assert("Skip reranker" not in search_view, "Search UI still exposes reranker toggle")


def main() -> int:
    checks = [
        ("Admin listing returns full set path (no implicit limit)", check_admin_all_record_listing),
        ("Deployed PPTX preview uses office viewer-compatible URL mode", check_pptx_preview_viewer_mode),
        ("Formula render path in answer/lecture uses $$/$ + KaTeX plugins", check_formula_render_path),
        ("Reranker disabled across backend and UI", check_reranker_disabled_guards),
    ]

    failures: List[str] = []
    for name, fn in checks:
        try:
            _run_check(name, fn)
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"[FAIL]  {name}: {exc}")

    if failures:
        print("\nValidation summary: FAILED")
        for item in failures:
            print(f" - {item}")
        return 1

    print("\nValidation summary: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
