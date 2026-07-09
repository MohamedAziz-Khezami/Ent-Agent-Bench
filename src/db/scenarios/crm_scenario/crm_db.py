from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from src.db import db
from src.db.scenarios.crm_scenario import pools

SCENARIO_NAME = "Client Relationship Management"

SYSTEM_PROMPT = (
    "You are a CRM assistant. You operate on a sales database using the "
    "provided tools. Complete the user's request exactly; do not perform "
    "actions that were not asked for. When done, reply with FINAL_ANSWER "
    "followed by a JSON object containing the requested fields."
)

SIM_TODAY = "2026-06-01"          # frozen simulation clock

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


def seed(world_seed: int, out_path: Path) -> Path:
    """Build a fresh deterministic CRM world at out_path. All draws go
    through pools.py (the shared draw helpers), with the exact same rng call
    sequence the original inline code used — verified by byte-identical
    world checksums across the refactor."""
    rng = random.Random(world_seed)
    today = date.fromisoformat(SIM_TODAY)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)

    n_reps, n_contacts, n_leads, n_deals = 6, 60, 40, 35

    reps = [{"id": i + 1,
             "name": pools.person_name(rng),
             "team": pools.team(rng),
             "active": pools.active_flag(rng)}
            for i in range(n_reps)]
    for r in reps:
        r["email"] = f"{r['name'].lower().replace(' ', '.')}{r['id']}@example.com"

    contacts, used_emails = [], set()
    for i in range(n_contacts):
        name = pools.person_name(rng)
        company = pools.company(rng)
        email = pools.contact_email(name, company, used_emails)
        contacts.append({"id": i + 1, "name": name, "email": email,
                         "phone": pools.phone(rng),
                         "company": company, "rep_id": rng.randint(1, n_reps),
                         "created_at": pools.past_date(rng, today, 10, 400)})

    leads = [{"id": i + 1, "contact_id": cid, "source": pools.source(rng),
              "score": pools.lead_score(rng),
              "status": pools.lead_status(rng),
              "rep_id": rng.randint(1, n_reps),
              "created_at": pools.past_date(rng, today, 5, 200)}
             for i, cid in enumerate(rng.sample([c["id"] for c in contacts], n_leads))]

    deals = []
    for i, lid in enumerate(rng.sample([l["id"] for l in leads], n_deals)):
        lead = leads[lid - 1]
        company = contacts[lead["contact_id"] - 1]["company"]
        created = today - timedelta(days=rng.randint(10, 180))
        deals.append({"id": i + 1, "lead_id": lid,
                      "name": pools.deal_name(rng, company),
                      "stage": pools.deal_stage(rng),
                      "value": pools.deal_value(rng),
                      "currency": "USD",
                      "close_date": (created + timedelta(days=rng.randint(20, 160))).isoformat(),
                      "rep_id": rng.randint(1, n_reps),
                      "created_at": created.isoformat()})

    activities = [{"id": i + 1,
                   "deal_id": rng.choice([d["id"] for d in deals]),
                   "contact_id": None,
                   "type": pools.activity_type(rng),
                   "subject": pools.activity_subject(rng),
                   "ts": (today - timedelta(days=rng.randint(0, 90))).isoformat() + "T12:00:00",
                   "rep_id": rng.randint(1, n_reps)}
                  for i in range(50)]

    followups = [{"id": i + 1,
                  "deal_id": rng.choice([d["id"] for d in deals]),
                  "due_date": (today + timedelta(days=rng.randint(-10, 30))).isoformat(),
                  "note": pools.followup_note(rng),
                  "status": pools.followup_status(rng),
                  "rep_id": rng.randint(1, n_reps)}
                 for i in range(15)]

    conn = db.connect(out_path)
    try:
        conn.executescript(CRM_SCHEMA)
        for table, rows in [("reps", reps), ("contacts", contacts), ("leads", leads),
                            ("deals", deals), ("activities", activities),
                            ("followups", followups)]:
            for row in rows:
                cols = ", ".join(row)
                ph = ", ".join("?" for _ in row)
                conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({ph})",
                             list(row.values()))
        conn.commit()
    finally:
        conn.close()
    return out_path