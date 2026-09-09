#!/usr/bin/env python3
"""Small HTTP gateway for a libCEC adapter."""

from __future__ import annotations

import json
import os
import subprocess
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


CEC_CLIENT = os.environ.get("CEC_CLIENT", "/usr/bin/cec-client")
PORT = int(os.environ.get("CEC_GATEWAY_PORT", "8765"))


def cec(command: str) -> str:
    result = subprocess.run(
        [CEC_CLIENT, "-s", "-d", "1"],
        input=f"{command}\nquit\n",
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        raise RuntimeError(output.strip() or "cec-client failed")
    return output


def power_state() -> str:
    output = cec("pow 0").lower()
    if "power status: on" in output:
        return "on"
    if "power status: standby" in output:
        return "off"
    return "unknown"


class Handler(BaseHTTPRequestHandler):
    server_version = "PiCecGateway/1.0"

    def _send(self, status: int, payload: dict[str, str]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/api/status":
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            self._send(HTTPStatus.OK, {"power": power_state()})
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(error)})

    def do_POST(self) -> None:
        if self.path != "/api/power":
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            state = json.loads(self.rfile.read(length)).get("state")
            if state not in {"on", "off"}:
                raise ValueError("state must be 'on' or 'off'")
            cec("on 0" if state == "on" else "standby 0")
            self._send(HTTPStatus.OK, {"power": state})
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
