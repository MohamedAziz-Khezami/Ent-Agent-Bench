# pools.py — the single source for every random draw the CRM world uses.
# Both the background-noise seeder (crm_db) and the task kernel injector
# (world_builder) draw from THESE functions, so injected kernel rows are
# statistically indistinguishable from noise (no odd-one-out name pools, no
# conspicuously round values — the anti-fingerprint layer of the
# constructive generator).
#
# Behavior contract: each helper makes EXACTLY the same rng calls, in the
# same order, as the inline crm_db.seed() code it was extracted from —
# verified by byte-identical world checksums across the refactor.
from __future__ import annotations

import random
from datetime import date, timedelta

FIRST = ["Alice", "Bob", "Carol", "Dana", "Elif", "Femi", "Grace", "Hugo",
         "Iris", "Jonas", "Kira", "Liam", "Mona", "Noor", "Omar", "Priya",
         "Quinn", "Rosa", "Sam", "Tara"]
LAST = ["Tan", "Lee", "Mo", "Ruiz", "Cole", "Nakamura", "Okafor", "Silva",
        "Haddad", "Novak", "Iversen", "Khan", "Moreau", "Diaz", "Weber", "Larsen"]
COMPANIES = ["Acme", "Globex", "Initech", "Umbrella", "Stark", "Wayne",
             "Hooli", "Vandelay", "Wonka", "Cyberdyne", "Soylent", "Tyrell"]
TEAMS = ["East", "West", "North", "South"]
SOURCES = ["webform", "referral", "event", "cold_call", "inbound_email"]
STAGES = ["prospecting", "qualification", "proposal", "negotiation", "closing", "won", "lost"]
SUBJECTS = ["intro", "pricing", "demo", "follow-up", "contract", "renewal",
            "kickoff", "negotiation", "check-in", "objections"]
DEAL_SUFFIXES = ["expansion", "renewal", "pilot", "rollout", "upgrade"]

DEAL_VALUE_LOW, DEAL_VALUE_HIGH, DEAL_VALUE_STEP = 5_000, 120_000, 500


def person_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def company(rng: random.Random) -> str:
    return rng.choice(COMPANIES)


def team(rng: random.Random) -> str:
    return rng.choice(TEAMS)


def active_flag(rng: random.Random) -> int:
    return 1 if rng.random() > 0.1 else 0


def phone(rng: random.Random) -> str:
    return f"+1-555-{rng.randint(1000, 9999)}"


def source(rng: random.Random) -> str:
    return rng.choice(SOURCES)


def lead_score(rng: random.Random) -> int:
    return rng.randint(5, 99)


def lead_status(rng: random.Random) -> str:
    return rng.choices(["new", "qualified", "unqualified", "converted"],
                        weights=[30, 40, 15, 15])[0]


def deal_stage(rng: random.Random) -> str:
    return rng.choices(STAGES, weights=[10, 15, 18, 18, 20, 12, 7])[0]


def deal_name(rng: random.Random, company_name: str) -> str:
    return f"{company_name} {rng.choice(DEAL_SUFFIXES)}"


def deal_value(rng: random.Random) -> float:
    return float(rng.randrange(DEAL_VALUE_LOW, DEAL_VALUE_HIGH, DEAL_VALUE_STEP))


def deal_value_between(rng: random.Random, low: float, high: float) -> float:
    """Kernel variant: a value inside [low, high] drawn on the SAME 500-step
    grid the background uses, so constructed values (e.g. 'safely above the
    threshold') don't stand out as oddly precise."""
    lo = max(DEAL_VALUE_LOW, int(low + DEAL_VALUE_STEP - 1) // DEAL_VALUE_STEP * DEAL_VALUE_STEP)
    hi = min(DEAL_VALUE_HIGH, int(high) // DEAL_VALUE_STEP * DEAL_VALUE_STEP)
    if lo > hi:
        raise ValueError(f"empty deal value range [{low}, {high}]")
    return float(rng.randrange(lo, hi + DEAL_VALUE_STEP, DEAL_VALUE_STEP))


def activity_type(rng: random.Random) -> str:
    return rng.choice(["call", "email", "meeting", "note"])


def activity_subject(rng: random.Random) -> str:
    return rng.choice(SUBJECTS)


def followup_note(rng: random.Random) -> str | None:
    return rng.choice(["check in", "send docs", None])


def followup_status(rng: random.Random) -> str:
    return rng.choice(["open", "open", "done"])


def past_date(rng: random.Random, today: date, lo_days: int, hi_days: int) -> str:
    return (today - timedelta(days=rng.randint(lo_days, hi_days))).isoformat()


def contact_email(name: str, company_name: str, used: set[str]) -> str:
    """Deterministic (no rng): derived from name+company, deduped with a counter."""
    email, n = f"{name.lower().replace(' ', '.')}@{company_name.lower()}.example", 2
    while email in used:
        email = f"{name.lower().replace(' ', '.')}{n}@{company_name.lower()}.example"
        n += 1
    used.add(email)
    return email
