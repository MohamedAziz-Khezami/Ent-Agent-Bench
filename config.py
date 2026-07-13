# config.py — shared benchmark configuration.
from __future__ import annotations

# ── agent loop (src/agent/loop.py) ───────────────────────────────────────

TURN_BUDGET = 20


TRAJECTORY_DIR = "results/trajectories"

# Retry backoff (seconds) for a momentarily-unreachable container.
RETRY_DELAYS_S = (0.5, 1.0, 2.0)

# HTTP request timeouts (seconds)
EXEC_HTTP_TIMEOUT_S = 60        # code-mode execute() call to the executor container
TOOL_CALL_HTTP_TIMEOUT_S = 30   # json_mcp direct tool-server call

# ── Docker orchestration (src/docker_runner/episode.py) ──────────────────
CONTAINER_READY_TIMEOUT_S = 15.0        # max wait for a container to answer /health or /openapi.json
CONTAINER_READY_POLL_INTERVAL_S = 0.3
CONTAINER_READY_REQUEST_TIMEOUT_S = 1.0

TOOL_SERVER_IMAGE = "ent-agent-bench/tool-server"
EXECUTOR_IMAGES = {
    "python": "ent-agent-bench/python-executor",
    "js": "ent-agent-bench/js-executor",
    "ts": "ent-agent-bench/ts-executor",
}

# ── task generation (build_tasks.py / crm_db.py / world_builder.py) ──────
SEED_BASE = 1000
TASKS_PER_TIER = 30
TIERS = ("easy", "medium", "hard", "expert")

SIM_TODAY = "2026-06-01"  # frozen simulation clock every frozen task/world uses

# Background (noise) row counts per table, injected alongside each task's
# own kernel rows — same distribution regardless of task/tier.
BACKGROUND_COUNTS = {"reps": 6, "contacts": 60, "leads": 40, "deals": 35,
                      "activities": 50, "followups": 15}
GUARD_REDRAW_LIMIT = 30  # max redraw attempts before a guard-violating background row gives up

# ── CLI defaults (cli.py) ─────────────────────────────────────────────────
DEFAULT_MODELS_YAML = "models.yaml"
DEFAULT_DIFFICULTY = "easy"
DEFAULT_SURFACES = "python,js,ts,json_mcp"
