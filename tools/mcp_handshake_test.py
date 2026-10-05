#!/usr/bin/env python3
"""JSON-RPC MCP handshake test for the local code-review-graph server.

Starts the CRG MCP server as a subprocess, sends an `initialize` JSON-RPC
request, reads the response, then sends an `initialized` notification.
Exits with status 0 on success, 1 on any error, and 2 if the router/tool
explicitly rejects the project (negative isolation test).

Usage:
    .venv\\Scripts\\python.exe tools\\mcp_handshake_test.py [EXPECTED_SUCCESS]

    EXPECTED_SUCCESS:
        0/yes/true   (default)  → expect successful handshake
        1/no/false             → expect failure / no unique project
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRG_EXE = ROOT / ".venv" / "Scripts" / "code-review-graph.exe"


def _parse_bool(arg: str | None) -> bool:
    if arg is None or arg == "":
        return True
    return arg.lower() in {"1", "true", "t", "yes", "y"}


def _write_message(stdin, msg: dict) -> None:
    body = json.dumps(msg, separators=(",", ":"))
    stdin.write(f"Content-Length: {len(body)}\r\n\r\n{body}")
    stdin.flush()


def _read_message(stdout) -> dict | None:
    headers = {}
    while True:
        line = stdout.readline()
        if not line:
            return None
        line = line.strip()
        if line == "":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length == 0:
        return None
    raw = stdout.read(length)
    if len(raw) < length:
        return None
    return json.loads(raw)


def main() -> int:
    expected_success = _parse_bool(sys.argv[1] if len(sys.argv) > 1 else None)

    if not CRG_EXE.exists():
        print(f"CRG executable not found: {CRG_EXE}", file=sys.stderr)
        return 1

    env = {
        **dict(subprocess.os.environ),
        "CRG_REPO_ROOT": str(ROOT),
        "CRG_DATA_DIR": str(ROOT / ".code-review-graph"),
    }

    proc = subprocess.Popen(
        [str(CRG_EXE), "serve", "--repo", str(ROOT)],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    deadline = time.monotonic() + 10.0
    try:
        # Give the server a moment to start
        time.sleep(0.5)

        if proc.poll() is not None:
            stderr = proc.stderr.read() if proc.stderr else ""
            print(f"Server exited early with code {proc.returncode}", file=sys.stderr)
            if stderr:
                print(stderr, file=sys.stderr)
            return 2 if not expected_success else 1

        _write_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-handshake-test", "version": "0.1.0"},
                },
            },
        )

        response = None
        while time.monotonic() < deadline:
            response = _read_message(proc.stdout)
            if response is not None:
                break
            time.sleep(0.05)

        if response is None:
            print("No initialize response received within timeout", file=sys.stderr)
            return 1

        if response.get("id") != 1 or "result" not in response:
            print(f"Unexpected initialize response: {response}", file=sys.stderr)
            return 1

        _write_message(
            proc.stdin,
            {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        )

        # Optionally verify a known tool is listed
        _write_message(
            proc.stdin,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
        )

        tools_response = None
        deadline2 = time.monotonic() + 5.0
        while time.monotonic() < deadline2:
            tools_response = _read_message(proc.stdout)
            if tools_response is not None:
                break
            time.sleep(0.05)

        if tools_response is None or "result" not in tools_response:
            print(f"Unexpected tools/list response: {tools_response}", file=sys.stderr)
            return 1

        tools = tools_response.get("result", {}).get("tools", [])
        print(f"Handshake OK. Server reported {len(tools)} tool(s).")
        expected_tools = {
            "detect_changes",
            "get_impact_radius",
            "query_graph",
            "semantic_search_nodes",
        }
        names = {t.get("name") for t in tools}
        missing = expected_tools - names
        if missing:
            print(f"Missing expected tools: {missing}", file=sys.stderr)
            return 1
        return 0

    except Exception as exc:
        print(f"Handshake error: {exc}", file=sys.stderr)
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
