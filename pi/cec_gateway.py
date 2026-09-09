#!/usr/bin/env python3
"""Small HTTP gateway for a libCEC adapter."""

from __future__ import annotations

import json
import os
import re
import subprocess
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


CEC_CLIENT = os.environ.get("CEC_CLIENT", "/usr/bin/cec-client")
PORT = int(os.environ.get("CEC_GATEWAY_PORT", "8765"))
TV_ADDRESS = "0"
INITIATOR = "1"

COMMANDS = {
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "select": "select",
    "ok": "select",
    "back": "back",
    "home": "root menu",
    "menu": "menu",
    "play": "play",
    "pause": "pause",
    "stop": "stop",
    "next": "next",
    "previous": "previous",
    "volume_up": "volup",
    "volume_down": "voldown",
    "mute": "mute",
}


def cec(*commands: str) -> str:
    request = "\n".join(commands) + "\nquit\n"
    result = subprocess.run(
        [CEC_CLIENT, "-s", "-d", "1"],
        input=request,
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


def parse_active_source(output: str) -> str:
    match = re.search(r"currently active source:\s*(.+?)\s*\((\d+)\)", output, re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"currently active source:\s*(.+)", output, re.I)
    return match.group(1).strip() if match else "unknown"


def parse_audio_status(output: str) -> dict[str, str | int]:
    match = re.search(r"audio status.*?volume:\s*(\d+).*?mute:\s*(\w+)", output, re.I | re.S)
    if not match:
        return {"volume": "unknown", "mute": "unknown"}
    return {"volume": int(match.group(1)), "mute": match.group(2).lower()}


def status() -> dict[str, str | int]:
    output = cec("pow 0", "active", f"tx {INITIATOR}0:7A")
    result: dict[str, str | int] = {
        "power": "on" if "power status: on" in output.lower() else "off" if "power status: standby" in output.lower() else "unknown",
        "active_source": parse_active_source(output),
        "playback": "unknown",
    }
    result.update(parse_audio_status(output))
    return result


def set_source(source: str) -> None:
    physical = source.lower().removeprefix("0x")
    if not re.fullmatch(r"[0-9a-f]{4}", physical):
        raise ValueError("source must be a four-digit physical address, such as 2000")
    cec(f"tx {INITIATOR}f:82:{physical[:2]}:{physical[2:]}", f"tx {INITIATOR}f:04")


class Handler(BaseHTTPRequestHandler):
    server_version = "PiCecGateway/1.0"

    def _send(self, status: int, payload: dict[str, Any]) -> None:
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
            self._send(HTTPStatus.OK, status())
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

    def do_PUT(self) -> None:
        if self.path != "/api/command":
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            command = payload.get("command")
            if command == "source":
                set_source(str(payload.get("physical_address", "")))
            elif command in COMMANDS:
                cec(COMMANDS[command])
            else:
                raise ValueError("unsupported command")
            self._send(HTTPStatus.OK, {"command": command})
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
            self._send(HTTPStatus.BAD_REQUEST, {"error": str(error)})

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()
