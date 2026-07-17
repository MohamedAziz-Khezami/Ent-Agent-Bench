# tools_client.py — lives inside the Python executor container.
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
            result = resp.json()  # every response is HTTP 200; success/failure is signaled by result["success"]
            if not result["success"]:
                err = result["error"]
                exc = RuntimeError(f"{err['code']}: {err.get('technical_message')}")
                exc.code = err["code"]  # was previously lost, only baked into the message text
                raise exc
            return result["data"]
        return call
