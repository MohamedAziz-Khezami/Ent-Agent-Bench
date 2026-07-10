# cli.py — argument parsing for main.py. Kept separate from the actual
# benchmark execution logic so the CLI surface (flags, help text, defaults)
# can be read/changed without touching how a run is actually driven.
#
# Two subcommands: `run` (drive episodes against the frozen task corpus) and
# `generate-tasks` (freeze/refresh that corpus). Separate flag sets because
# they're separate concerns — `run` cares about which episodes to execute,
# `generate-tasks` only cares about how many tasks per tier.
from __future__ import annotations

import argparse

from config import DEFAULT_DIFFICULTY, DEFAULT_MODELS_YAML, DEFAULT_SURFACES, SEED_BASE, TASKS_PER_TIER


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run episodes against the frozen task corpus")
    run_parser.add_argument("--models", required=True, help="comma-separated model names from models.yaml")
    run_parser.add_argument("--surfaces", default=DEFAULT_SURFACES,
                             help="comma-separated: python,js,ts,json_mcp")
    run_parser.add_argument("--interaction-modes", default=None,
                             help='comma-separated: tool_call,text_block. '
                                  "Default: tool_call for models with supports_tool_calling, else text_block.")
    run_parser.add_argument("--difficulty", default=DEFAULT_DIFFICULTY, help="easy,medium,hard,expert,all")
    run_parser.add_argument("--limit", type=int, default=None, help="max tasks per difficulty tier")
    run_parser.add_argument("--models-yaml", default=DEFAULT_MODELS_YAML)
    run_parser.add_argument("--out", default=None)

    gen_parser = subparsers.add_parser("generate-tasks", help="freeze/refresh the task corpus")
    gen_parser.add_argument("--n-per-tier", type=int, default=TASKS_PER_TIER,
                             help=f"tasks to generate per difficulty tier (default: {TASKS_PER_TIER})")
    gen_parser.add_argument("--seed-base", type=int, default=SEED_BASE,
                             help=f"first task's seed; each subsequent task increments by 1 "
                                  f"(default: {SEED_BASE}). Same seed_base + n_per_tier always "
                                  "reproduces the identical corpus; change it to generate a different one.")

    return parser.parse_args(argv)
