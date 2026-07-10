# cheater.py — leakage measurement. Tries to guess each task's ground_truth
# from the world file using ONLY dumb shortcuts (never reading the query,
# never filtering by the task's actual predicates). Its accuracy is the
# corpus's "guessing floor": on a clean corpus the shortcuts should score
# near chance — a jump means injected kernel rows carry a detectable
# fingerprint (e.g. always the newest/highest-id row). Permanent regression
# test: re-run after any generator change.
#
# Only id-shaped answers (deal_id/lead_id/...) are guessable this way;
# count-shaped answers (n_deals/n_updated/n_escalated) are skipped and
# reported separately.
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from src.db import db
from src.db.scenarios.crm_scenario.tasks.build_tasks import load_tasks

_ANSWER_TABLE = {"deal_id": "deals", "lead_id": "leads",
                  "contact_id": "contacts", "followup_id": "followups"}
_HAS_CREATED_AT = {"deals", "leads", "contacts"}


def _world_path(task: dict) -> Path:
    return Path(task["world_db"])


def _guesses(conn, table: str) -> dict[str, int | None]:
    out = {}
    row = conn.execute(f"SELECT MAX(id) AS id FROM {table}").fetchone()
    out["max_id"] = row["id"]
    if table in _HAS_CREATED_AT:
        row = conn.execute(
            f"SELECT id FROM {table} ORDER BY created_at DESC, id DESC LIMIT 1").fetchone()
        out["newest_created_at"] = row["id"] if row else None
    return out


def run(selector: str = "all") -> dict:
    tasks = load_tasks(selector)
    hits: dict[str, int] = defaultdict(int)
    per_tier_hits: dict[tuple[str, str], int] = defaultdict(int)
    per_tier_n: dict[str, int] = defaultdict(int)
    n_id_tasks, n_count_tasks = 0, 0

    for task in tasks:
        key = task["answer_keys"][0]
        if key not in _ANSWER_TABLE:
            n_count_tasks += 1
            continue
        n_id_tasks += 1
        per_tier_n[task["difficulty"]] += 1
        truth = task["ground_truth"][key]
        conn = db.connect(_world_path(task))
        try:
            for name, guess in _guesses(conn, _ANSWER_TABLE[key]).items():
                if guess == truth:
                    hits[name] += 1
                    per_tier_hits[(task["difficulty"], name)] += 1
        finally:
            conn.close()

    return {"n_id_tasks": n_id_tasks, "n_count_tasks": n_count_tasks,
            "hits": dict(hits), "per_tier_hits": dict(per_tier_hits),
            "per_tier_n": dict(per_tier_n)}


def main() -> None:
    result = run()
    n = result["n_id_tasks"]
    lines = [f"cheater baseline over {n} id-answer tasks "
             f"({result['n_count_tasks']} count-answer tasks skipped)"]
    for name, h in sorted(result["hits"].items()):
        lines.append(f"  {name}: {h}/{n} = {h / n:.1%}")
    for tier, tn in sorted(result["per_tier_n"].items()):
        for name in sorted({k[1] for k in result["per_tier_hits"]} | set(result["hits"])):
            h = result["per_tier_hits"].get((tier, name), 0)
            lines.append(f"    {tier:8s} {name}: {h}/{tn}")
    report = "\n".join(lines)
    print(report)
    out = Path("results/cheater_baseline.txt")
    out.parent.mkdir(exist_ok=True)
    out.write_text(report + "\n")
    print(f"\nsaved to {out}")


if __name__ == "__main__":
    main()
