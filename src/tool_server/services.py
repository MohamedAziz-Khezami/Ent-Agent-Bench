# services.py — one named function per CRM tool. Each function calls the
# matching impl.py function directly (no string-keyed lookup anywhere) and
# has its own fully explicit, independent try/except — deliberately not
# factored into a shared helper, so any one tool's error handling can be
# changed without touching the other 16.
from __future__ import annotations

from src.core.errors import DomainError
from src.db.scenarios.crm_scenario import crm_tools as impl


def list_reps(conn) -> dict:
    try:
        result = impl.list_reps(conn)
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def find_contacts(conn, args) -> dict:
    try:
        result = impl.find_contacts(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def get_contact(conn, args) -> dict:
    try:
        result = impl.get_contact(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def find_leads(conn, args) -> dict:
    try:
        result = impl.find_leads(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def get_lead(conn, args) -> dict:
    try:
        result = impl.get_lead(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def get_deal(conn, args) -> dict:
    try:
        result = impl.get_deal(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def find_deals(conn, args) -> dict:
    try:
        result = impl.find_deals(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def get_activities(conn, args) -> dict:
    try:
        result = impl.get_activities(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def get_followups(conn, args) -> dict:
    try:
        result = impl.get_followups(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def create_contact(conn, args) -> dict:
    try:
        result = impl.create_contact(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def update_contact(conn, args) -> dict:
    try:
        result = impl.update_contact(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def create_lead(conn, args) -> dict:
    try:
        result = impl.create_lead(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def update_lead(conn, args) -> dict:
    try:
        result = impl.update_lead(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def create_deal(conn, args) -> dict:
    try:
        result = impl.create_deal(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def update_deal(conn, args) -> dict:
    try:
        result = impl.update_deal(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def log_activity(conn, args) -> dict:
    try:
        result = impl.log_activity(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def schedule_followup(conn, args) -> dict:
    try:
        result = impl.schedule_followup(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}


def update_followup(conn, args) -> dict:
    try:
        result = impl.update_followup(conn, **args.model_dump(exclude_none=True))
        return {"ok": True, "result": result}
    except DomainError as e:
        return {"ok": False, "error": {"code": e.code, "message": e.message, **e.extra}}
