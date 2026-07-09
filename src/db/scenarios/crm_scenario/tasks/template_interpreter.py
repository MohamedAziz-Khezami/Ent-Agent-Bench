# template_interpreter.py — the YAML task-template DSL. Templates declare a
# task's parameters, kernel rows, effects, and query as data; this module is
# the only code that knows the DSL's conventions. The construct list is a
# deliberate scope fence (see the plan): a new task type needing a construct
# not implemented here is a conscious DSL extension, not a silent hack.
#
# Constructs:
#   draw specs   {choice: [...]}, {draw: pool_fn}, {sample: menu, k: n},
#                {value_between: [lo, hi]}, {sim_date_offset: spec},
#                {randint: [lo, hi]}, {if: [{when, then}, ...]}, {expr: "..."}
#   expressions  safe ast-whitelisted arithmetic/comparison, names from
#                params, `item.field` attribute access, date_offset(d, days)
#   placeholders "{param}" (typed if the whole string is one placeholder),
#                str.format specs like "${threshold:,}"
#   refs         "@ref" / "@ref.field" strings — left untouched here, the
#                world builder resolves them to injected row ids/values
#   kernel       {ref, table, row} entries; repeat: n makes a group (list);
#                a "@group" ref from a same-size group pairs element-wise
#   effects      added/changed lists, {if: ...} branching, {for_each: group},
#                {from_chosen_actions: {anchor: "@ref"}}
#   guards       predicates no background row may match
from __future__ import annotations

import ast
import operator
import re
from datetime import date, timedelta
from pathlib import Path

import yaml

from src.db.scenarios.crm_scenario.crm_db import SIM_TODAY

TEMPLATES_DIR = Path(__file__).parent / "templates"

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv}
_CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne,
        ast.Gt: operator.gt, ast.Lt: operator.lt,
        ast.GtE: operator.ge, ast.LtE: operator.le}


def _date_offset(date_str: str, days: int) -> str:
    return (date.fromisoformat(date_str) + timedelta(days=int(days))).isoformat()


_FUNCS = {"date_offset": _date_offset}

_DRAW_KEYS = {"choice", "draw", "sample", "value_between", "sim_date_offset",
              "randint", "if", "expr"}
_SINGLE_PLACEHOLDER = re.compile(r"^\{(\w+)\}$")


def load_template(name: str, tier: str) -> dict:
    """Templates live in per-tier folders (templates/<tier>/<name>.yaml) —
    each tier owns its own self-contained copy, knobs baked in as literals."""
    return yaml.safe_load((TEMPLATES_DIR / tier / f"{name}.yaml").read_text())


def load_actions() -> dict:
    return yaml.safe_load((TEMPLATES_DIR / "actions.yaml").read_text())


def eval_expr(src: str, names: dict):
    """Safe expression evaluator: arithmetic, one comparison, whitelisted
    function calls, `item.field` access. Anything else is rejected."""
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in names:
                return names[node.id]
            raise ValueError(f"unknown name {node.id!r} in expression {src!r}")
        if isinstance(node, ast.Attribute):
            base = ev(node.value)
            if isinstance(base, dict) and node.attr in base:
                return base[node.attr]
            raise ValueError(f"unknown attribute {node.attr!r} in expression {src!r}")
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP:
            return _CMP[type(node.ops[0])](ev(node.left), ev(node.comparators[0]))
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _FUNCS):
            return _FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ValueError(f"disallowed node {type(node).__name__} in expression {src!r}")
    return ev(ast.parse(src, mode="eval"))


def fill(value, names: dict):
    """Resolve "{param}" placeholders. A string that is exactly one
    placeholder returns the TYPED value; "@..." refs pass through for the
    world builder; other strings go through str.format."""
    if isinstance(value, str):
        if value.startswith("@"):
            return value
        m = _SINGLE_PLACEHOLDER.match(value)
        if m and m.group(1) in names:
            return names[m.group(1)]
        if "{" in value:
            return value.format(**names)
        return value
    if isinstance(value, dict):
        return {k: fill(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [fill(v, names) for v in value]
    return value


def _as_int(value, names: dict) -> int:
    resolved = fill(value, names) if isinstance(value, str) else value
    if isinstance(resolved, str):
        resolved = eval_expr(resolved, names)
    return int(resolved)


def resolve_spec(spec, rng, names: dict, menus: dict | None = None):
    """Resolve one draw spec (or literal) to a concrete value."""
    if isinstance(spec, dict) and len(spec) <= 2 and _DRAW_KEYS & spec.keys():
        if "choice" in spec:
            return rng.choice(fill(spec["choice"], names))
        if "draw" in spec:
            from src.db.scenarios.crm_scenario import pools
            return getattr(pools, spec["draw"])(rng)
        if "sample" in spec:
            menu = (menus or load_actions())[spec["sample"]]
            return rng.sample(menu, k=_as_int(spec["k"], names))
        if "value_between" in spec:
            from src.db.scenarios.crm_scenario import pools
            lo, hi = spec["value_between"]
            lo = eval_expr(lo, names) if isinstance(lo, str) else lo
            hi = eval_expr(hi, names) if isinstance(hi, str) else hi
            return pools.deal_value_between(rng, lo, hi)
        if "sim_date_offset" in spec:
            from src.db.scenarios.crm_scenario.crm_db import sim_date
            return sim_date(_as_int(resolve_spec(spec["sim_date_offset"], rng, names, menus), names)
                             if isinstance(spec["sim_date_offset"], dict)
                             else _as_int(spec["sim_date_offset"], names))
        if "randint" in spec:
            lo, hi = (_as_int(v, names) for v in spec["randint"])
            return rng.randint(lo, hi)
        if "if" in spec:
            for branch in spec["if"]:
                if eval_expr(branch["when"], names):
                    return resolve_spec(branch["then"], rng, names, menus)
            raise ValueError(f"no `if` branch matched: {spec}")
        if "expr" in spec:
            return eval_expr(spec["expr"], names)
    return fill(spec, names)


def draw_params(template: dict, rng, template_args: dict | None = None,
                 menus: dict | None = None) -> dict:
    """Evaluate the template's `params:` in declared order; later entries may
    reference earlier ones (and tier-provided template_args)."""
    names = dict(template_args or {})
    for key, spec in (template.get("params") or {}).items():
        names[key] = resolve_spec(spec, rng, names, menus)
    return names


def expand_kernel(template: dict, params: dict, rng,
                   include_distractors: bool = False) -> list[dict]:
    """Expand kernel (and optionally distractor) entries into concrete row
    specs: {"ref", "table", "index" (for groups), "cols"}. Draw specs inside
    rows are resolved per instance; "@ref" strings stay for the builder."""
    entries = list(template.get("kernel") or [])
    if include_distractors:
        entries += list(template.get("distractors") or [])
    out = []
    for entry in entries:
        n = _as_int(entry["repeat"], params) if "repeat" in entry else None
        count = n if n is not None else 1
        for i in range(count):
            cols = {k: resolve_spec(v, rng, params) for k, v in entry["row"].items()}
            out.append({"ref": entry["ref"], "table": entry["table"],
                         "index": i if n is not None else None, "cols": cols})
    return out


def expand_guards(template: dict, params: dict) -> list[dict]:
    return [fill(g, params) for g in (template.get("guards") or [])]


def _instantiate_action_row(action: dict, anchor_id: int, params: dict) -> dict:
    row = fill(action["row"], params)

    def sub(v):
        if v == "@anchor":
            return anchor_id
        if isinstance(v, dict):
            return {k: sub(x) for k, x in v.items()}
        return v
    return {k: sub(v) for k, v in row.items()}


def expand_effects(template: dict, params: dict, resolve) -> dict:
    """resolve(ref) -> injected row id; resolve(ref, field) -> column value;
    for repeat groups both return lists. Returns expected_added /
    expected_changed / exact_added_count in the frozen-task shape."""
    added: dict[str, list] = {}
    changed: dict[str, list] = {}

    def handle(block: dict, item: dict | None = None):
        names = dict(params)
        if item is not None:
            names["item"] = item

        def resolve_value(v):
            if isinstance(v, str) and v.startswith("@item."):
                return item[v[len("@item."):]]
            if v == "@item":
                return item["id"]
            if isinstance(v, str) and v.startswith("@"):
                ref, _, field = v[1:].partition(".")
                return resolve(ref, field) if field else resolve(ref)
            if isinstance(v, dict) and "expr" in v:
                return eval_expr(v["expr"], names)
            if isinstance(v, dict):
                return {k: resolve_value(x) for k, x in v.items()}
            return fill(v, names)

        if "if" in block:
            for branch in block["if"]:
                if eval_expr(branch["when"], names):
                    handle(branch["then"], item)
                    return
            return
        if "for_each" in block:
            for row in resolve(block["for_each"], "__rows__"):
                inner = {k: v for k, v in block.items() if k != "for_each"}
                handle(inner, item=row)
            return
        if "from_chosen_actions" in block:
            anchor_id = resolve_value(block["from_chosen_actions"]["anchor"])
            for action in params["chosen"]:
                row = _instantiate_action_row(action, anchor_id, params)
                if action["kind"] == "added":
                    added.setdefault(action["table"], []).append(row)
                else:
                    changed.setdefault(action["table"], []).append(row)
            return
        for spec in block.get("added", []):
            added.setdefault(spec["table"], []).append(resolve_value(spec["row"]))
        for spec in block.get("changed", []):
            changed.setdefault(spec["table"], []).append(
                {"id": resolve_value(spec["id"]), "fields": resolve_value(spec["fields"])})

    effects = template.get("effects")
    if effects:
        if isinstance(effects, list):
            for block in effects:
                handle(block)
        else:
            handle(effects)

    exact_added_count = {t: len(rows) for t, rows in added.items()}
    return {"expected_added": added, "expected_changed": changed,
            "exact_added_count": exact_added_count}


def build_answer(template: dict, params: dict, resolve) -> dict:
    out = {}
    for key, v in template["answer"].items():
        if isinstance(v, str) and v.startswith("@"):
            ref, _, field = v[1:].partition(".")
            out[key] = resolve(ref, field) if field else resolve(ref)
        else:
            out[key] = fill(v, params)
    return out


def chosen_phrases_joined(params: dict) -> str:
    return ", then ".join(a["phrase"].format(**params) for a in params["chosen"])


def n_functions(template: dict, params: dict) -> int:
    return _as_int(template["n_functions"], params)


def n_actions(template: dict, params: dict) -> int:
    return _as_int(template["n_actions"], params)
