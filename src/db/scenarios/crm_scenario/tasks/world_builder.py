# world_builder.py — constructive world generation: decide the task first
# (template params), then build a world that makes it valid BY DESIGN.
# Background noise and the injected task kernel draw from the same pools.py
# distributions, kernel rows get id slots interleaved uniformly into each
# table's 1..N range, and background rows can never contaminate the kernel's
# answer set (see conflict-prevention layers below). No rejection-retry over
# whole worlds anywhere.
#
# Conflict prevention:
#   1. reference partitioning — background rows only reference background
#      parents (kernel entities like a task's rep can't accidentally own
#      background deals), so query answer-sets are closed by construction.
#   2. identity exclusion — kernel names/companies are removed from the
#      background draw pools, so the query's entity description can't match
#      a background row; `guards:` predicates additionally trigger a bounded
#      per-row redraw for anything exclusion can't express.
#   3. the audit (audit.py) re-checks every invariant on the finished world.
#
# Determinism: three named RNG sub-streams per task
# (f"{seed}:params" / ":world" / ":inject") so editing how one phase draws
# can never shift another phase's output.
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from config import BACKGROUND_COUNTS as _BG_COUNTS
from config import GUARD_REDRAW_LIMIT as _GUARD_REDRAW_LIMIT
from src.db import db
from src.db.scenarios.crm_scenario import pools
from src.db.scenarios.crm_scenario.crm_db import CRM_SCHEMA, SIM_TODAY, TABLES
from src.db.scenarios.crm_scenario.tasks import template_interpreter as ti


def _complete_forbidden(expected_added: dict, expected_changed: dict) -> dict:
    """Every table is forbidden from 'removed'; 'added'/'changed' are
    forbidden unless this task's own expectations say otherwise — the frozen
    JSON is a complete, self-contained contract. (Moved from the old
    search-based generator, unchanged semantics.)"""
    result: dict[str, set] = {}
    for table in TABLES:
        kinds = result.setdefault(table, set())
        kinds.add("removed")
        if table not in expected_added:
            kinds.add("added")
        if table not in expected_changed:
            kinds.add("changed")
    return {t: sorted(kinds) for t, kinds in result.items()}


def _kernel_identities(kernel: list[dict]) -> dict[str, set]:
    """Names/companies the kernel uses — excluded from background draws so
    the query's entity description can only ever match kernel rows."""
    names, companies = set(), set()
    for row in kernel:
        if row["table"] in ("contacts", "reps") and "name" in row["cols"]:
            names.add(row["cols"]["name"])
        if "company" in row["cols"]:
            companies.add(row["cols"]["company"])
    return {"names": names, "companies": companies}


def _draw_excluding(draw_fn, rng, excluded: set, limit: int = 50):
    for _ in range(limit):
        v = draw_fn(rng)
        if v not in excluded:
            return v
    raise RuntimeError(f"could not draw a value outside {len(excluded)} exclusions")


def _violates_guard(table: str, cols: dict, guards: list[dict]) -> bool:
    for g in guards:
        if g["table"] != table:
            continue
        where = g["where"]
        if all(k in cols and cols[k] == v for k, v in where.items()):
            return True
    return False


def _background(rng: random.Random, exclusions: dict, guards: list[dict]) -> dict[str, list[dict]]:
    """Same shapes/counts/distributions as the classic crm_db.seed() noise,
    but: rows hold OBJECT references to their parents (ids assigned later,
    after interleaving), kernel identities are excluded, and guard-violating
    rows get a bounded redraw."""
    today = date.fromisoformat(SIM_TODAY)

    def guarded(table: str, make) -> dict:
        for _ in range(_GUARD_REDRAW_LIMIT):
            cols = make()
            if not _violates_guard(table, cols, guards):
                return cols
        raise RuntimeError(f"guard redraw limit hit for {table}")

    reps = [{"table": "reps", "cols": guarded("reps", lambda: {
        "name": _draw_excluding(pools.person_name, rng, exclusions["names"]),
        "team": pools.team(rng),
        "active": pools.active_flag(rng)}), "fk": {}}
        for _ in range(_BG_COUNTS["reps"])]

    used_emails: set[str] = set()
    contacts = []
    for _ in range(_BG_COUNTS["contacts"]):
        def make_contact():
            name = _draw_excluding(pools.person_name, rng, exclusions["names"])
            company = _draw_excluding(pools.company, rng, exclusions["companies"])
            return {"name": name, "company": company,
                    "phone": pools.phone(rng),
                    "created_at": pools.past_date(rng, today, 10, 400)}
        cols = guarded("contacts", make_contact)
        cols["email"] = pools.contact_email(cols["name"], cols["company"], used_emails)
        contacts.append({"table": "contacts", "cols": cols,
                          "fk": {"rep_id": rng.choice(reps)}})

    leads = []
    for contact in rng.sample(contacts, _BG_COUNTS["leads"]):
        cols = guarded("leads", lambda: {
            "source": pools.source(rng), "score": pools.lead_score(rng),
            "status": pools.lead_status(rng),
            "created_at": pools.past_date(rng, today, 5, 200)})
        leads.append({"table": "leads", "cols": cols,
                       "fk": {"contact_id": contact, "rep_id": rng.choice(reps)}})

    deals = []
    for lead in rng.sample(leads, _BG_COUNTS["deals"]):
        company = lead["fk"]["contact_id"]["cols"]["company"]

        def make_deal():
            created = today - timedelta(days=rng.randint(10, 180))
            return {"name": pools.deal_name(rng, company),
                    "stage": pools.deal_stage(rng),
                    "value": pools.deal_value(rng), "currency": "USD",
                    "close_date": (created + timedelta(days=rng.randint(20, 160))).isoformat(),
                    "created_at": created.isoformat()}
        deals.append({"table": "deals", "cols": guarded("deals", make_deal),
                       "fk": {"lead_id": lead, "rep_id": rng.choice(reps)}})

    # Every noise activity records WHICH PERSON it involved (contact_id is
    # always set). ~70% are additionally tied to a deal — their contact_id
    # is derived from that deal's own chain (deal -> lead -> contact), so
    # the data stays coherent; ~30% are contact-only (deal_id NULL).
    activities = []
    for _ in range(_BG_COUNTS["activities"]):
        cols = guarded("activities", lambda: {
            "type": pools.activity_type(rng),
            "subject": pools.activity_subject(rng),
            "ts": (today - timedelta(days=rng.randint(0, 90))).isoformat() + "T12:00:00"})
        if rng.random() < 0.7:
            deal = rng.choice(deals)
            fk = {"deal_id": deal,
                  "contact_id": deal["fk"]["lead_id"]["fk"]["contact_id"],
                  "rep_id": rng.choice(reps)}
        else:
            cols["deal_id"] = None
            fk = {"contact_id": rng.choice(contacts), "rep_id": rng.choice(reps)}
        activities.append({"table": "activities", "cols": cols, "fk": fk})

    followups = [{"table": "followups", "cols": guarded("followups", lambda: {
        "due_date": (today + timedelta(days=rng.randint(-10, 30))).isoformat(),
        "note": pools.followup_note(rng),
        "status": pools.followup_status(rng)}),
        "fk": {"deal_id": rng.choice(deals), "rep_id": rng.choice(reps)}}
        for _ in range(_BG_COUNTS["followups"])]

    return {"reps": reps, "contacts": contacts, "leads": leads,
            "deals": deals, "activities": activities, "followups": followups}


def _ref_map(kernel: list[dict]) -> dict:
    """ref -> row spec (single) or ordered list (repeat group)."""
    out: dict = {}
    for row in kernel:
        if row["index"] is None:
            out[row["ref"]] = row
        else:
            out.setdefault(row["ref"], []).append(row)
    for v in out.values():
        if isinstance(v, list):
            v.sort(key=lambda r: r["index"])
    return out


def _target_row(value: str, row: dict, refs: dict) -> dict:
    """Resolve an "@ref" string to the target row spec, pairing element-wise
    when both sides are same-size repeat groups."""
    ref, _, field = value[1:].partition(".")
    target = refs[ref]
    if isinstance(target, list):
        if row.get("index") is not None and len(target) > row["index"]:
            target = target[row["index"]]
        else:
            raise ValueError(f"@{ref} is a group; pairing needs same-size groups")
    return target


def _kernel_parent(row: dict, col: str, refs: dict) -> dict | None:
    v = row["cols"].get(col)
    if isinstance(v, str) and v.startswith("@"):
        return _target_row(v, row, refs)
    return None


def _fill_kernel(kernel: list[dict], bg: dict, refs: dict, rng: random.Random,
                  used_emails: set[str], exclusions: dict) -> None:
    """Fill each kernel row's unspecified columns from the same pools the
    background uses — injected rows must be statistically unremarkable.
    Auto-filled names avoid the kernel's own anchor identities so a
    distractor contact can never coincidentally share the anchor's name."""
    today = date.fromisoformat(SIM_TODAY)
    for row in kernel:
        cols, table = row["cols"], row["table"]
        if table == "reps":
            cols.setdefault("team", pools.team(rng))
            cols.setdefault("active", 1)
        elif table == "contacts":
            if "name" not in cols:
                cols["name"] = _draw_excluding(pools.person_name, rng, exclusions["names"])
            cols.setdefault("company", pools.company(rng))
            cols.setdefault("phone", pools.phone(rng))
            cols.setdefault("created_at", pools.past_date(rng, today, 10, 400))
            cols.setdefault("email", pools.contact_email(cols["name"], cols["company"], used_emails))
            if "rep_id" not in cols:
                row["fk"] = {"rep_id": rng.choice(bg["reps"])}
        elif table == "leads":
            cols.setdefault("source", pools.source(rng))
            cols.setdefault("score", pools.lead_score(rng))
            cols.setdefault("status", pools.lead_status(rng))
            cols.setdefault("created_at", pools.past_date(rng, today, 5, 200))
            if "rep_id" not in cols:
                contact = _kernel_parent(row, "contact_id", refs)
                if contact is not None and "fk" in contact and "rep_id" in contact["fk"]:
                    row["fk"] = {"rep_id": contact["fk"]["rep_id"]}
                elif contact is not None and "rep_id" in contact["cols"]:
                    cols["rep_id"] = contact["cols"]["rep_id"]
                else:
                    row["fk"] = {"rep_id": rng.choice(bg["reps"])}
        elif table == "deals":
            if "name" not in cols:
                lead = _kernel_parent(row, "lead_id", refs)
                contact = _kernel_parent(lead, "contact_id", refs) if lead else None
                company = (contact["cols"].get("company") if contact
                           else pools.company(rng))
                cols["name"] = pools.deal_name(rng, company)
            cols.setdefault("stage", pools.deal_stage(rng))
            cols.setdefault("value", pools.deal_value(rng))
            cols.setdefault("currency", "USD")
            if "created_at" not in cols:
                created = today - timedelta(days=rng.randint(10, 180))
                cols["created_at"] = created.isoformat()
                cols.setdefault("close_date",
                                (created + timedelta(days=rng.randint(20, 160))).isoformat())
            cols.setdefault("close_date", None)
            if "rep_id" not in cols:
                row["fk"] = {"rep_id": rng.choice(bg["reps"])}
        elif table == "activities":
            cols.setdefault("contact_id", None)
            cols.setdefault("deal_id", None)
            cols.setdefault("type", pools.activity_type(rng))
            cols.setdefault("subject", pools.activity_subject(rng))
            cols.setdefault("ts", (today - timedelta(days=rng.randint(0, 90))).isoformat() + "T12:00:00")
            if "rep_id" not in cols:
                row["fk"] = {"rep_id": rng.choice(bg["reps"])}
        elif table == "followups":
            cols.setdefault("due_date", (today + timedelta(days=rng.randint(-10, 30))).isoformat())
            cols.setdefault("note", pools.followup_note(rng))
            cols.setdefault("status", pools.followup_status(rng))
            if "rep_id" not in cols:
                row["fk"] = {"rep_id": rng.choice(bg["reps"])}


def _assemble_and_write(bg: dict, kernel: list[dict], refs: dict,
                         rng: random.Random, out_path: Path) -> None:
    """Interleave kernel rows uniformly into each table's id space, resolve
    all references (object FKs and @refs) to real ids, write the sqlite."""
    for table in TABLES:
        combined = bg[table] + [r for r in kernel if r["table"] == table]
        rng.shuffle(combined)
        for pos, row in enumerate(combined):
            row["id"] = pos + 1
        bg[table] = combined  # now the full table, ids assigned

    # background reps' emails need their final id
    for row in bg["reps"]:
        row["cols"].setdefault(
            "email", f"{row['cols']['name'].lower().replace(' ', '.')}{row['id']}@example.com")

    # resolve FKs: object references (background) and @refs (kernel)
    for table in TABLES:
        for row in bg[table]:
            for col, target in (row.get("fk") or {}).items():
                row["cols"][col] = target["id"]
            for col, v in list(row["cols"].items()):
                if isinstance(v, str) and v.startswith("@"):
                    ref, _, field = v[1:].partition(".")
                    target = _target_row(v, row, refs)
                    row["cols"][col] = target["cols"][field] if field else target["id"]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)
    conn = db.connect(out_path)
    try:
        conn.executescript(CRM_SCHEMA)
        for table in TABLES:
            for row in bg[table]:
                cols = {"id": row["id"], **row["cols"]}
                names = ", ".join(cols)
                ph = ", ".join("?" for _ in cols)
                conn.execute(f"INSERT INTO {table} ({names}) VALUES ({ph})",
                             list(cols.values()))
        conn.commit()
    finally:
        conn.close()


def _merge_same_row_changes(fx: dict) -> None:
    """Two actions changing the SAME row (e.g. a lead's status and score)
    are one changed row in a real diff, not two — expected_changed must say
    so or verify()'s exact_changed_count would fail every correct solution.
    (The old search-based generator emitted the unmerged shape: a latent
    grading bug on multi-action same-table tasks, caught by the audit's
    golden-solution check on its first run.)"""
    for table, specs in fx["expected_changed"].items():
        merged: dict[int, dict] = {}
        for spec in specs:
            entry = merged.setdefault(spec["id"], {"id": spec["id"], "fields": {}})
            entry["fields"].update(spec["fields"])
        fx["expected_changed"][table] = list(merged.values())


def _make_resolver(refs: dict):
    def resolve(ref: str, field: str | None = None):
        target = refs[ref]
        if isinstance(target, list):
            if field == "__rows__":
                return [{"id": r["id"], **r["cols"]} for r in target]
            if field:
                return [r["cols"][field] for r in target]
            return [r["id"] for r in target]
        if field == "__rows__":
            return [{"id": target["id"], **target["cols"]}]
        if field:
            return target["cols"][field]
        return target["id"]
    return resolve


def build_task(task_seed: int, template: dict, world_path: Path,
                menus: dict | None = None) -> dict:
    """Build one task and its world file. Templates are fully self-contained
    (per-tier copies with literal knobs and their own phrasings), so no tier
    config is needed here. Returns the frozen-task dict (caller adds
    task_id/difficulty/template/world_seed bookkeeping)."""
    menus = menus or ti.load_actions()
    params_rng = random.Random(f"{task_seed}:params")
    world_rng = random.Random(f"{task_seed}:world")
    inject_rng = random.Random(f"{task_seed}:inject")

    params = ti.draw_params(template, params_rng, {}, menus)

    kernel = ti.expand_kernel(template, params, params_rng,
                               include_distractors="distractors" in template)
    guards = ti.expand_guards(template, params)
    exclusions = _kernel_identities(kernel)

    bg = _background(world_rng, exclusions, guards)
    refs = _ref_map(kernel)
    used_emails = {c["cols"]["email"] for c in bg["contacts"]}
    _fill_kernel(kernel, bg, refs, inject_rng, used_emails, exclusions)
    _assemble_and_write(bg, kernel, refs, inject_rng, world_path)

    resolve = _make_resolver(refs)
    fx = ti.expand_effects(template, params, resolve)
    _merge_same_row_changes(fx)

    if "query" in template:
        names = dict(params)
        if "chosen" in params:
            names["actions"] = ti.chosen_phrases_joined(params)
        query = ti.fill(template["query"], names)
    else:
        entity = template["entity"].format(**params)
        phrasing = params_rng.choice(template["phrasings"])
        query = phrasing.format(entity=entity,
                                 actions=ti.chosen_phrases_joined(params),
                                 answer_key=template["answer_keys"][0])

    return {
        "query": query,
        "answer_keys": list(template["answer_keys"]),
        "ground_truth": ti.build_answer(template, params, resolve),
        "expected_added": fx["expected_added"],
        "expected_changed": fx["expected_changed"],
        "exact_added_count": fx["exact_added_count"],
        "forbidden": _complete_forbidden(fx["expected_added"], fx["expected_changed"]),
        "n_functions": ti.n_functions(template, params),
        "n_actions": ti.n_actions(template, params),
    }
