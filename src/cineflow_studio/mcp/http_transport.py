"""HTTP transport for the CineFlow MCP server (Cursor-audit #752, P0).

Some IDE agents (Cursor Enterprise on Windows) sandbox every local stdio
command, and that sandbox is broken on Windows — the server never starts.
The bypass is to REMOVE the launched command from the chain: this module
serves the same JSON-RPC over plain HTTP on loopback, so the IDE config
uses ``"url": "http://127.0.0.1:<port>/mcp"`` and Cursor never spawns a
process (nothing to sandbox, no admin allowlist).

stdlib only — the package gains no new dependency. Single JSON response
per POST (the streamable-HTTP spec allows it for non-streaming servers).
Loopback-only by default: this transport carries the user's cloud token,
it must not listen on a routable interface.
"""
from __future__ import annotations

import asyncio
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cineflow.logging_config import get_logger
from cineflow_studio.mcp.server import McpServer

logger = get_logger("cineflow_studio.mcp.http_transport")


def serve_http(host: str, port: int) -> None:
    """Blocking: POST /mcp → one JSON-RPC response; GET /mcp → a health line."""
    server = McpServer()

    class Handler(BaseHTTPRequestHandler):
        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "content-type, authorization")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

        def do_OPTIONS(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler name
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path.split("?")[0] != "/mcp":
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "server": server.name,
                        "version": server.version,
                        "transport": "http",
                        "endpoint": "/mcp",
                        "hint": "POST JSON-RPC 2.0 here (initialize, tools/list, tools/call)",
                    }
                ).encode("utf-8")
            )

        def do_POST(self) -> None:  # noqa: N802
            if self.path.split("?")[0] != "/mcp":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("content-length") or 0)
            line = self.rfile.read(length).decode("utf-8") if length else ""
            try:
                # handle_message is async; this transport thread has no event
                # loop of its own — one fresh loop per request (stdio parity).
                response = asyncio.run(server.handle_message(line))
            except Exception as exc:  # noqa: BLE001 — a tool crash must not kill the transport
                logger.exception("handle_message failed")
                response = json.dumps(
                    {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32603, "message": f"internal error: {exc}"}}
                )
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write((response or "").encode("utf-8"))

        def log_message(self, fmt, *args) -> None:  # noqa: ANN001 — quiet access log
            pass

    httpd = ThreadingHTTPServer((host, port), Handler)
    logger.info("CineFlow MCP over HTTP on http://%s:%s/mcp", host, port)
    print(f"CineFlow MCP over HTTP: http://{host}:{port}/mcp  (Ctrl+C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    host = "127.0.0.1"
    port = 8765
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == "--host" and i + 1 < len(argv):
            host = argv[i + 1]
        elif arg == "--port" and i + 1 < len(argv):
            port = int(argv[i + 1])
    if host != "127.0.0.1":
        print(
            "Refusing a non-loopback host: this transport carries the user's cloud "
            "token and must stay on 127.0.0.1 (edit the code if you really mean it).",
            file=sys.stderr,
        )
        return 2
    serve_http(host, port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
