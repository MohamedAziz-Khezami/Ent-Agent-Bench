# episode.py — per-episode Docker orchestration. Creates a private network,
# starts the (trusted) tool-server container with the episode's world DB
# bind-mounted, starts the (untrusted) language executor on the same
# network (skipped for the json_mcp surface, which has no executor at all),
# and exposes exec()/teardown() for the agent loop to call.
#
# The world arrives as a FROZEN ARTIFACT (frozen/<tier>/task_XXX.sqlite,
# built once by tasks/build_tasks.py) and is COPIED into the episode's tmp
# dir — episodes mutate the copy, never the corpus, and reproducibility
# doesn't depend on any generator code at runtime.
#
# CONFIRMED (empirically, with a real Docker daemon): the earlier plan to use
# internal=True on the shared network was wrong. `internal=True` doesn't just
# block outbound internet routing — it blocks Docker's inbound port-publishing
# (DNAT) entirely, so `docker port` shows no host mapping at all and the host
# can never reach a container on that network. Since the harness (on the
# host) MUST reach both the tool-server and the executor via published
# ports, `internal=True` is incompatible with this design and has been
# removed below. Consequence: this network does NOT currently block the
# executor container's outbound internet access — that property from the
# plan is not enforced yet. The trust boundary that IS still fully intact
# regardless: executor containers have zero filesystem access to src/db/,
# src/core/, or the sqlite file (see docker/python-executor.Dockerfile,
# docker/js-executor.Dockerfile, docker/ts-executor.Dockerfile — those
# directories are simply never COPYed in), so untrusted code can only ever
# reach data through the tool-server's validated HTTP API. True
# internet-egress blocking would need
# a different mechanism (e.g. a gateway/proxy container straddling two
# networks, or per-container iptables rules) — out of scope unless asked for.
from __future__ import annotations

import shutil
import tempfile
import time
import uuid
from pathlib import Path

import docker
import requests

# A container that's genuinely dead will fail every retry too (these are
# short/cheap, not a substitute for fixing an actual OOM/crash root cause) —
# but a real transient blip (brief Docker networking hiccup, momentary
# resource pressure under several simultaneous heavy containers) gets a
# chance to self-heal instead of failing the whole episode on one refused
# connection. Only retries connection-level failures (the container
# unreachable at all); an actual non-2xx response from a live container is
# a real application error, not something a retry would fix.
_EXEC_RETRY_DELAYS_S = (0.5, 1.0, 2.0)

_TOOL_SERVER_IMAGE = "ent-agent-bench/tool-server"
_EXECUTOR_IMAGES = {
    "python": "ent-agent-bench/python-executor",
    "js": "ent-agent-bench/js-executor",
    "ts": "ent-agent-bench/ts-executor",
}


class Episode:
    def __init__(self, world_db: str | Path, surface: str, ready_timeout_s: float = 15.0):
        if surface not in ("python", "js", "ts", "json_mcp"):
            raise ValueError(f"unknown surface: {surface}")
        self.surface = surface
        self.client = docker.from_env()
        self.episode_id = uuid.uuid4().hex[:8]
        self.tmp_dir = Path(tempfile.mkdtemp(prefix=f"episode-{self.episode_id}-"))
        self.executor = None

        self.network = self.client.networks.create(
            f"episode-{self.episode_id}", driver="bridge")

        self.db_path = self.tmp_dir / "world.sqlite"
        shutil.copyfile(world_db, self.db_path)

        #this is the fatapi / fastmcp server
        self.tool_server = self.client.containers.run(
            _TOOL_SERVER_IMAGE, detach=True,
            name=f"tools-{self.episode_id}",
            network=self.network.name,
            volumes={str(self.db_path): {"bind": "/data/world.sqlite", "mode": "rw"}},
            ports={"8000/tcp": None},   # published so the harness (on host) can reach it
        )
        self._tool_server_url = self._wait_ready(self.tool_server, 8000, ready_timeout_s)

        # if it is json/mcp no need for another docker , it is already there with the fastapi (fastmcp)
        if surface != "json_mcp":
            image = _EXECUTOR_IMAGES[surface]
            self.executor = self.client.containers.run(
                image,
                detach=True,
                name=f"exec-{self.episode_id}",
                network=self.network.name,
                environment={"TOOL_SERVER_URL": f"http://tools-{self.episode_id}:8000"}, # noqa
                ports={"8001/tcp": None},  # published so the harness can POST /exec
            )
            self._executor_url = self._wait_ready(self.executor, 8001, ready_timeout_s)

    def _wait_ready(self, container, internal_port: int, timeout_s: float) -> str:
        container.reload()
        host_port = container.ports[f"{internal_port}/tcp"][0]["HostPort"]
        url = f"http://localhost:{host_port}"
        deadline = __import__("time").monotonic() + timeout_s
        last_error = None
        while __import__("time").monotonic() < deadline:
            try:
                path = "/openapi.json" if internal_port == 8000 else "/health"
                requests.get(f"{url}{path}", timeout=1)
                return url
            except requests.RequestException as e:
                last_error = e
                __import__("time").sleep(0.3)
        raise RuntimeError(f"{container.name} never became ready on port {internal_port}: {last_error}")

    def tool_server_url(self) -> str:
        return self._tool_server_url

    def exec(self, code: str, lang: str | None = None) -> dict:
        if self.executor is None:
            raise RuntimeError(f"no executor container for surface={self.surface!r}")
        last_error = None
        for attempt, delay in enumerate((0.0, *_EXEC_RETRY_DELAYS_S)):
            if delay:
                time.sleep(delay)
            try:
                resp = requests.post(f"{self._executor_url}/exec",
                                      json={"code": code, "lang": lang or self.surface},
                                      timeout=60)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.ConnectionError as e:
                last_error = e  # container unreachable — worth a retry, see module comment
            except requests.exceptions.HTTPError:
                raise  # a real response from a live container — not a connectivity issue, don't retry
        raise last_error

    def teardown(self) -> None:
        for container in (self.executor, self.tool_server):
            if container is None:
                continue
            try:
                container.stop(timeout=3)
            except Exception:  # noqa: BLE001 — best-effort cleanup, never let one failure block the rest
                pass
            try:
                container.remove(force=True)
            except Exception:  # noqa: BLE001
                pass
        try:
            self.network.remove()
        except Exception:  # noqa: BLE001
            pass
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def __enter__(self) -> "Episode":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.teardown()
