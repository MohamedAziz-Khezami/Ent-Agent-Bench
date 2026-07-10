from __future__ import annotations

from datetime import date, timedelta

from config import SIM_TODAY  # re-exported: existing `from ...crm_db import SIM_TODAY` call sites are unchanged

SCENARIO_NAME = "Client Relationship Management"

SYSTEM_PROMPT = (
    "You are a CRM assistant. You operate on a sales database using the "
    "provided tools. Complete the user's request exactly; do not perform "
    "actions that were not asked for. When done, reply with FINAL_ANSWER "
    "followed by a JSON object containing the requested fields."
)

CRM_SCHEMA = """
CREATE TABLE reps (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    team TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    company TEXT,
    rep_id INTEGER NOT NULL REFERENCES reps(id),
    created_at TEXT NOT NULL
);
CREATE TABLE leads (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    source TEXT NOT NULL,
    score INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('new','qualified','unqualified','converted')),
    rep_id INTEGER NOT NULL REFERENCES reps(id),
    created_at TEXT NOT NULL
);
CREATE TABLE deals (
    id INTEGER PRIMARY KEY,
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    name TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN
        ('prospecting','qualification','proposal','negotiation','closing','won','lost')),
    value REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    close_date TEXT,
    rep_id INTEGER NOT NULL REFERENCES reps(id),
    created_at TEXT NOT NULL
);
CREATE TABLE activities (
    id INTEGER PRIMARY KEY,
    deal_id INTEGER REFERENCES deals(id),
    contact_id INTEGER REFERENCES contacts(id),
    type TEXT NOT NULL CHECK (type IN ('call','email','meeting','note')),
    subject TEXT NOT NULL,
    ts TEXT NOT NULL,
    rep_id INTEGER NOT NULL REFERENCES reps(id),
    CHECK (deal_id IS NOT NULL OR contact_id IS NOT NULL)
);
CREATE TABLE followups (
    id INTEGER PRIMARY KEY,
    deal_id INTEGER NOT NULL REFERENCES deals(id),
    due_date TEXT NOT NULL,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','done')),
    rep_id INTEGER NOT NULL REFERENCES reps(id)
);
"""

TABLES = ["reps", "contacts", "leads", "deals", "activities", "followups"]


def sim_date(offset_days: int) -> str:
    return (date.fromisoformat(SIM_TODAY) + timedelta(days=offset_days)).isoformat()
