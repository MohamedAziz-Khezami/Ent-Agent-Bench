# errors.py — scenario-agnostic domain error vocabulary. Any scenario's tool
# implementations (e.g. impl.py) raise these; each tool_server/services.py
# function catches them explicitly and converts to the same canonical
# {"code", "message", ...} shape, regardless of which surface (Python/JS/TS/
# JSON-MCP) ultimately made the call.
from __future__ import annotations


class DomainError(Exception):
    code = "domain_error"

    def __init__(self, message: str, **extra):
        super().__init__(message)
        self.message = message
        self.extra = extra


class DuplicateKey(DomainError):
    code = "duplicate_key"


class NotFound(DomainError):
    code = "not_found"


class MalformedFilter(DomainError):
    code = "malformed_filter"
