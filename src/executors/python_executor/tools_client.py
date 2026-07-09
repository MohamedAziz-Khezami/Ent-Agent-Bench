# tools_client.py — lives inside the Python executor container. The `Tools`
# class is what generated code sees as `tools`. Genuinely synchronous —
# requests.post() blocks by default, no background thread or event loop
# needed. Every call is a real HTTP request to the tool-server, reached only
# over the private per-episode Docker network (this container has no direct
# database access at all).
from __future__ import annotations

import requests

#this is basically the python sdk that runs the requests to the backend server from tool.get_contact() etc...
class Tools:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.call_count = 0  # reset per /exec call by exec_server.py; feeds the meter's tool_calls_made

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)

        def call(**kwargs):
            self.call_count += 1
            resp = requests.post(f"{self.base_url}/{name}", json=kwargs, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            if not result["ok"]:
                err = result["error"]
                exc = RuntimeError(f"{err['code']}: {err['message']}")
                exc.code = err["code"]  # was previously lost, only baked into the message text
                raise exc
            return result["result"]
        return call
