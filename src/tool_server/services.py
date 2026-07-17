# services.py — one named function per CRM tool.
from __future__ import annotations

from src.core.errors import DomainError
from src.db.scenarios.crm_scenario import crm_tools as impl
from src.tool_server.envelope import APIResponse


def list_reps(conn) -> APIResponse:
    try:
        result = impl.list_reps(conn)
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def find_contacts(conn, args) -> APIResponse:
    try:
        result = impl.find_contacts(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def get_contact(conn, args) -> APIResponse:
    try:
        result = impl.get_contact(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def find_leads(conn, args) -> APIResponse:
    try:
        result = impl.find_leads(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def get_lead(conn, args) -> APIResponse:
    try:
        result = impl.get_lead(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def get_deal(conn, args) -> APIResponse:
    try:
        result = impl.get_deal(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def find_deals(conn, args) -> APIResponse:
    try:
        result = impl.find_deals(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def get_activities(conn, args) -> APIResponse:
    try:
        result = impl.get_activities(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def get_followups(conn, args) -> APIResponse:
    try:
        result = impl.get_followups(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def create_contact(conn, args) -> APIResponse:
    try:
        result = impl.create_contact(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def update_contact(conn, args) -> APIResponse:
    try:
        result = impl.update_contact(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def create_lead(conn, args) -> APIResponse:
    try:
        result = impl.create_lead(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def update_lead(conn, args) -> APIResponse:
    try:
        result = impl.update_lead(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def create_deal(conn, args) -> APIResponse:
    try:
        result = impl.create_deal(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def update_deal(conn, args) -> APIResponse:
    try:
        result = impl.update_deal(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def log_activity(conn, args) -> APIResponse:
    try:
        result = impl.log_activity(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def schedule_followup(conn, args) -> APIResponse:
    try:
        result = impl.schedule_followup(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)


def update_followup(conn, args) -> APIResponse:
    try:
        result = impl.update_followup(conn, **args.model_dump(exclude_none=True))
        return APIResponse.ok(result)
    except DomainError as e:
        return APIResponse.fail(code=e.code, technical_message=e.message, meta=e.extra or None)
