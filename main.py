# main.py — entrypoint. Reads models.yaml + the frozen task corpus, runs
# every requested (model x surface x interaction_mode x task) combination
# through agent/loop.py's run_episode(), and appends one CSV row per episode
# as it completes (not buffered — a crash partway through a long run still
# leaves you a usable partial CSV).
from __future__ import annotations

import csv
import datetime
from pathlib import Path

from cli import parse_args
from src.agent.loop import run_episode
from src.db.scenarios.crm_scenario.tasks.build_tasks import FROZEN_DIR, build_all, load_tasks
from src.llm_clients.registry import load_model_registry

CSV_FIELDS = [
    "episode_id", "model", "surface", "interaction_mode", "task_id", "difficulty", "world_seed",
    "passed", "answer_correct", "db_correct", "fulfillment_score",
    "n_functions_expected", "tool_calls_made", "model_turns",
    "total_latency_seconds", "model_latency_seconds", "execution_latency_seconds",
    "input_tokens", "output_tokens", "total_tokens",
    "tool_error_count", "syntax_error_count", "type_error_count", "runtime_error_count", "parse_error_count",
    "recovered", "hit_turn_budget", "infra_error", "model_api_error", "model_api_error_message",
    "episode_error", "episode_error_message",
    "verifier_reasons",
]


def main() -> None:
    args = parse_args()

    if args.command == "generate-tasks":
        n = build_all(n_per_tier=args.n_per_tier, seed_base=args.seed_base)
        print(f"[build] total: {n} task+world pairs frozen under {FROZEN_DIR}")
        return

    all_configs = {c.name: c for c in load_model_registry(args.models_yaml)}
    requested_names = [n.strip() for n in args.models.split(",")]
    unknown = [n for n in requested_names if n not in all_configs]
    if unknown:
        available = "\n".join(f"  {n}" for n in sorted(all_configs))
        raise SystemExit(
            f"unknown model name(s): {', '.join(unknown)}\n"
            f"available models in {args.models_yaml}:\n{available}")
    selected_models = [all_configs[name] for name in requested_names]

    surfaces = args.surfaces.split(",")

    selector = "all" if args.difficulty == "all" else args.difficulty
    tasks = load_tasks(selector)
    if args.limit:
        by_tier: dict[str, list[dict]] = {}
        for t in tasks:
            by_tier.setdefault(t["difficulty"], []).append(t)
        tasks = [t for tier_tasks in by_tier.values() for t in tier_tasks[: args.limit]]

    out_path = Path(args.out) if args.out else Path(
        f"results/run_{datetime.datetime.now():%Y-%m-%d_%H%M%S}.csv")
    if not out_path.suffix:
        # trajectory_dir below is out_path with its suffix stripped — an
        # --out with NO suffix at all would make trajectory_dir identical to
        # out_path itself, and since trajectory_dir.mkdir() runs first, the
        # later out_path.open("w") would fail with IsADirectoryError.
        # Defaulting a missing suffix to .csv keeps the two paths distinct.
        out_path = out_path.with_suffix(".csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # trajectories for this run live in a folder named after the CSV itself
    # (e.g. results/sub10b_easy.csv -> results/sub10b_easy/), not one shared
    # results/trajectories folder every invocation dumps into regardless of run
    trajectory_dir = out_path.with_suffix("")
    trajectory_dir.mkdir(parents=True, exist_ok=True)

    def modes_for(model_config):
        if args.interaction_modes:
            return args.interaction_modes.split(",")
        return ["tool_call"] if model_config.supports_tool_calling else ["text_block"]

    total = sum(len(modes_for(m)) for m in selected_models) * len(surfaces) * len(tasks)
    done = 0
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for model_config in selected_models:
            for surface in surfaces:
                for mode in modes_for(model_config):
                    for task in tasks:
                        row = run_episode(model_config, surface, mode, task, trajectory_dir=str(trajectory_dir))
                        writer.writerow(row)
                        f.flush()
                        done += 1
                        print(f"[{done}/{total}] {model_config.name} {surface} {mode} "
                              f"{task['task_id']} -> passed={row['passed']} turns={row['model_turns']}")

    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
