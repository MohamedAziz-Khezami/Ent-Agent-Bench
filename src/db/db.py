from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path



#Scenario agnostic DB helpers

def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def snapshot(db_path: str | Path) -> Path:
    """Copy the DB as an episode baseline; returns the snapshot path."""
    db_path = Path(db_path)
    snap = db_path.with_suffix(".baseline.sqlite")
    shutil.copyfile(db_path, snap)
    return snap


def _all_rows(path: str | Path, tables: list[str]) -> dict[str, dict[int, dict]]:
    conn = connect(path)
    try:
        return {t: {r["id"]: dict(r) for r in conn.execute(f"SELECT * FROM {t}")}
                for t in tables}
    finally:
        conn.close()


def state_diff(before_path, after_path, tables: list[str]) -> dict:
    """{table: {added: [row], removed: [row], changed: [(id, {col: (a,b)})]}}
    Only tables with differences appear. `tables` comes from the scenario."""
    before, after = _all_rows(before_path, tables), _all_rows(after_path, tables)
    diff: dict = {}
    for t in tables:
        b, a = before[t], after[t]
        added = [a[i] for i in sorted(a.keys() - b.keys())]
        removed = [b[i] for i in sorted(b.keys() - a.keys())]
        changed = []
        for i in sorted(a.keys() & b.keys()):
            delta = {c: (b[i][c], a[i][c]) for c in a[i] if a[i][c] != b[i][c]}
            if delta:
                changed.append((i, delta))
        if added or removed or changed:
            diff[t] = {"added": added, "removed": removed, "changed": changed}
    return diff
