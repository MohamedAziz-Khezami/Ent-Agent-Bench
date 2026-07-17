# envelope.py — the one response shape every tool-server route returns,
# regardless of success, a caught DomainError, a FastAPI/Pydantic request
# validation failure, or an uncaught exception. HTTP status is always 200;
# success/failure is signaled purely by `success`, so clients never need to
# branch on HTTP status to detect an application-level failure.
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorInfo(BaseModel):
    code: str
    technical_message: str | None = None


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    error: ErrorInfo | None = None
    meta: dict[str, Any] | None = None

    @classmethod
    def ok(cls, data: Any, meta: dict[str, Any] | None = None) -> "APIResponse":
        return cls(success=True, data=data, meta=meta)

    @classmethod
    def fail(cls, code: str, technical_message: str | None = None,
              meta: dict[str, Any] | None = None) -> "APIResponse":
        return cls(success=False, error=ErrorInfo(code=code, technical_message=technical_message), meta=meta)
