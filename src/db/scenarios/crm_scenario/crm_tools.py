# crm_tools.py — CRM-specific tool implementations. All CRM domain logic
# lives here; nothing about HOW an agent calls these (Python/JS/JSON) does.
from __future__ import annotations

import sqlite3

from src.core.errors import DomainError, DuplicateKey, NotFound, MalformedFilter
from src.db.scenarios.crm_scenario.crm_db import SIM_TODAY


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _one(conn: sqlite3.Connection, table: str, rid: int) -> dict:
    r = conn.execute(f"SELECT * FROM {table} WHERE id=?", (rid,)).fetchone()
    if r is None:
        raise NotFound(f"{table[:-1]} with id {rid} does not exist")
    return dict(r)


def list_reps(conn) -> list[dict]:
    return _rows(conn.execute("SELECT * FROM reps"))


def find_contacts(conn, name=None, email=None, company=None, rep_id=None) -> list[dict]:
    clauses, args = [], []
    if name is not None:
        clauses.append("LOWER(name) LIKE LOWER(?)"); args.append(f"%{name}%")
    if email is not None:
        clauses.append("LOWER(email) = LOWER(?)"); args.append(email)
    if company is not None:
        clauses.append("LOWER(company) = LOWER(?)"); args.append(company)
    if rep_id is not None:
        clauses.append("rep_id = ?"); args.append(rep_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return _rows(conn.execute(f"SELECT * FROM contacts {where}", args))


def get_contact(conn, id) -> dict:  # noqa: A002
    return _one(conn, "contacts", id)


def find_leads(conn, contact_id=None, rep_id=None, status=None, min_score=None) -> list[dict]:
    clauses, args = [], []
    if contact_id is not None:
        clauses.append("contact_id = ?"); args.append(contact_id)
    if rep_id is not None:
        clauses.append("rep_id = ?"); args.append(rep_id)
    if status is not None:
        clauses.append("status = ?"); args.append(status)
    if min_score is not None:
        clauses.append("score >= ?"); args.append(min_score)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return _rows(conn.execute(f"SELECT * FROM leads {where}", args))


def get_lead(conn, id) -> dict:  # noqa: A002
    return _one(conn, "leads", id)


def get_deal(conn, id) -> dict:  # noqa: A002
    return _one(conn, "deals", id)


def find_deals(conn, lead_id=None, stage=None, rep_id=None, min_value=None) -> list[dict]:
    clauses, args = [], []
    if lead_id is not None:
        clauses.append("lead_id = ?"); args.append(lead_id)
    if stage is not None:
        clauses.append("stage = ?"); args.append(stage)
    if rep_id is not None:
        clauses.append("rep_id = ?"); args.append(rep_id)
    if min_value is not None:
        clauses.append("value >= ?"); args.append(min_value)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return _rows(conn.execute(f"SELECT * FROM deals {where}", args))


def get_activities(conn, deal_id=None, contact_id=None) -> list[dict]:
    if deal_id is None and contact_id is None:
        raise MalformedFilter("provide deal_id or contact_id")
    clauses, args = [], []
    if deal_id is not None:
        clauses.append("deal_id = ?"); args.append(deal_id)
    if contact_id is not None:
        clauses.append("contact_id = ?"); args.append(contact_id)
    return _rows(conn.execute(
        f"SELECT * FROM activities WHERE {' AND '.join(clauses)} ORDER BY ts ASC", args))


def get_followups(conn, deal_id=None, rep_id=None, status=None) -> list[dict]:
    clauses, args = [], []
    if deal_id is not None:
        clauses.append("deal_id = ?"); args.append(deal_id)
    if rep_id is not None:
        clauses.append("rep_id = ?"); args.append(rep_id)
    if status is not None:
        clauses.append("status = ?"); args.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return _rows(conn.execute(f"SELECT * FROM followups {where}", args))


def create_contact(conn, name, email, rep_id, company=None, phone=None) -> dict:
    existing = conn.execute(
        "SELECT id FROM contacts WHERE LOWER(email)=LOWER(?)", (email,)).fetchone()
    if existing:
        raise DuplicateKey(
            f"contact with email {email} already exists", existing_id=existing["id"])
    _one(conn, "reps", rep_id)
    cur = conn.execute(
        "INSERT INTO contacts (name, email, phone, company, rep_id, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (name, email, phone, company, rep_id, SIM_TODAY))
    conn.commit()
    return _one(conn, "contacts", cur.lastrowid)


def update_contact(conn, id, **fields) -> dict:  # noqa: A002
    _one(conn, "contacts", id)
    allowed = {k: v for k, v in fields.items()
               if k in ("name", "email", "company", "phone", "rep_id") and v is not None}
    if "rep_id" in allowed:
        _one(conn, "reps", allowed["rep_id"])
    if "email" in allowed:
        dup = conn.execute(
            "SELECT id FROM contacts WHERE LOWER(email)=LOWER(?) AND id<>?",
            (allowed["email"], id)).fetchone()
        if dup:
            raise DuplicateKey(
                f"contact with email {allowed['email']} already exists",
                existing_id=dup["id"])
    if allowed:
        sets = ", ".join(f"{k}=?" for k in allowed)
        conn.execute(f"UPDATE contacts SET {sets} WHERE id=?", (*allowed.values(), id))
        conn.commit()
    return _one(conn, "contacts", id)


def create_lead(conn, contact_id, source, score=None, rep_id=None) -> dict:
    contact = _one(conn, "contacts", contact_id)
    rep = rep_id if rep_id is not None else contact["rep_id"]
    _one(conn, "reps", rep)
    cur = conn.execute(
        "INSERT INTO leads (contact_id, source, score, status, rep_id, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (contact_id, source, score if score is not None else 50, "new", rep, SIM_TODAY))
    conn.commit()
    return _one(conn, "leads", cur.lastrowid)


def update_lead(conn, id, status=None, score=None, source=None) -> dict:  # noqa: A002
    _one(conn, "leads", id)
    if status is not None:
        conn.execute("UPDATE leads SET status=? WHERE id=?", (status, id))
    if score is not None:
        conn.execute("UPDATE leads SET score=? WHERE id=?", (score, id))
    if source is not None:
        conn.execute("UPDATE leads SET source=? WHERE id=?", (source, id))
    conn.commit()
    return _one(conn, "leads", id)


def create_deal(conn, lead_id, name, value, stage=None, close_date=None) -> dict:
    lead = _one(conn, "leads", lead_id)
    cur = conn.execute(
        "INSERT INTO deals (lead_id, name, stage, value, currency, close_date, rep_id, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (lead_id, name, stage or "prospecting", float(value), "USD",
         close_date, lead["rep_id"], SIM_TODAY))
    conn.commit()
    return _one(conn, "deals", cur.lastrowid)


def update_deal(conn, id, stage=None, value=None, close_date=None) -> dict:  # noqa: A002
    _one(conn, "deals", id)
    if stage is not None:
        conn.execute("UPDATE deals SET stage=? WHERE id=?", (stage, id))
    if value is not None:
        conn.execute("UPDATE deals SET value=? WHERE id=?", (float(value), id))
    if close_date is not None:
        conn.execute("UPDATE deals SET close_date=? WHERE id=?", (close_date, id))
    conn.commit()
    return _one(conn, "deals", id)


def log_activity(conn, type, subject, deal_id=None, contact_id=None) -> dict:  # noqa: A002
    if deal_id is None and contact_id is None:
        raise MalformedFilter("provide deal_id or contact_id")
    rep_id = None
    if deal_id is not None:
        deal = _one(conn, "deals", deal_id)
        rep_id = deal["rep_id"]
    if contact_id is not None:
        rep_id = _one(conn, "contacts", contact_id)["rep_id"]
    elif deal_id is not None:
        # world convention: every activity records which person it involved —
        # when only the deal is given, derive the contact from the deal's own
        # chain (deal -> lead -> contact), same rule the noise generator uses
        contact_id = _one(conn, "leads", deal["lead_id"])["contact_id"]
    cur = conn.execute(
        "INSERT INTO activities (deal_id, contact_id, type, subject, ts, rep_id) "
        "VALUES (?,?,?,?,?,?)",
        (deal_id, contact_id, type, subject, f"{SIM_TODAY}T12:00:00", rep_id))
    conn.commit()
    return _one(conn, "activities", cur.lastrowid)


def schedule_followup(conn, deal_id, due_date, note=None) -> dict:
    deal = _one(conn, "deals", deal_id)
    cur = conn.execute(
        "INSERT INTO followups (deal_id, due_date, note, status, rep_id) "
        "VALUES (?,?,?,?,?)",
        (deal_id, due_date, note, "open", deal["rep_id"]))
    conn.commit()
    return _one(conn, "followups", cur.lastrowid)


def update_followup(conn, id, status=None, due_date=None, note=None) -> dict:  # noqa: A002
    _one(conn, "followups", id)
    if status is not None:
        conn.execute("UPDATE followups SET status=? WHERE id=?", (status, id))
    if due_date is not None:
        conn.execute("UPDATE followups SET due_date=? WHERE id=?", (due_date, id))
    if note is not None:
        conn.execute("UPDATE followups SET note=? WHERE id=?", (note, id))
    conn.commit()
    return _one(conn, "followups", id)


