"""CineFlow FastMCP stdio server (JSON-RPC 2.0).

Communicates with host IDE agents (Cursor, Trae, Kimi Code, Zed, Cline, OpenCode) over standard I/O.
Exposes Tools, Resources, and Prompts according to the MCP specification.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys

from cineflow_studio.mcp.prompts import get_prompt_definitions, render_prompt
from cineflow_studio.mcp.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    LATEST_PROTOCOL_VERSION,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JsonRpcError,
    format_error,
    format_response,
    format_tool_result,
)
from cineflow_studio.mcp.resources import get_resource_definitions, read_resource_contents
from cineflow_studio.mcp.tools import execute_tool, get_tool_definitions

# Configure logger to output strictly to stderr, protecting stdout for JSON-RPC
logger = logging.getLogger("cineflow_studio.mcp")
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("[%(asctime)s] [CineFlow MCP] %(levelname)s: %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class McpServer:
    def __init__(self, name: str = "cineflow-mcp", version: str = "1.0.0") -> None:
        self.name = name
        self.version = version
        self.initialized = False

    async def handle_message(self, line: str) -> str | None:
        line = line.strip()
        if not line:
            return None

        try:
            req = json.loads(line)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Failed to parse JSON: %s", exc)
            return format_error(None, JsonRpcError(PARSE_ERROR, "Parse error: Invalid JSON"))

        if not isinstance(req, dict) or req.get("jsonrpc") != "2.0":
            return format_error(req.get("id"), JsonRpcError(INVALID_REQUEST, "Invalid Request: expected jsonrpc 2.0"))

        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        logger.debug("Received request id=%s method=%s", msg_id, method)

        # Handle notifications (no id)
        if msg_id is None:
            if method == "notifications/initialized":
                self.initialized = True
                logger.info("Client completed initialization handshake.")
            return None

        # Handle RPC requests (has id)
        if method == "initialize":
            self.initialized = True
            client_info = params.get("clientInfo", {})
            logger.info("Initializing connection with client: %s", client_info)
            result = {
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {
                        "listChanged": False,
                    },
                    "resources": {
                        "subscribe": False,
                        "listChanged": False,
                    },
                    "prompts": {
                        "listChanged": False,
                    },
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            }
            return format_response(msg_id, result)

        elif method == "ping":
            return format_response(msg_id, {})

        elif method == "tools/list":
            tools = [tool.to_dict() for tool in get_tool_definitions()]
            return format_response(msg_id, {"tools": tools})

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if not tool_name:
                return format_error(msg_id, JsonRpcError(INVALID_PARAMS, "Missing tool name in params"))

            content, is_error = await execute_tool(tool_name, tool_args)
            return format_response(msg_id, format_tool_result(content, is_error))

        elif method == "resources/list":
            resources = [r.to_dict() for r in get_resource_definitions()]
            return format_response(msg_id, {"resources": resources})

        elif method == "resources/read":
            uri = params.get("uri")
            if not uri:
                return format_error(msg_id, JsonRpcError(INVALID_PARAMS, "Missing 'uri' parameter"))
            try:
                content = read_resource_contents(uri)
                return format_response(msg_id, {"contents": [content]})
            except KeyError as exc:
                return format_error(msg_id, JsonRpcError(INVALID_PARAMS, str(exc)))
            except Exception as exc:  # noqa: BLE001
                logger.error("Error reading resource '%s': %s", uri, exc)
                return format_error(msg_id, JsonRpcError(INTERNAL_ERROR, f"Internal error reading resource: {exc}"))

        elif method == "prompts/list":
            prompts = [p.to_dict() for p in get_prompt_definitions()]
            return format_response(msg_id, {"prompts": prompts})

        elif method == "prompts/get":
            prompt_name = params.get("name")
            prompt_args = params.get("arguments", {})
            if not prompt_name:
                return format_error(msg_id, JsonRpcError(INVALID_PARAMS, "Missing 'name' parameter for prompt"))
            try:
                result = render_prompt(prompt_name, prompt_args)
                return format_response(msg_id, result)
            except (KeyError, ValueError) as exc:
                return format_error(msg_id, JsonRpcError(INVALID_PARAMS, str(exc)))
            except Exception as exc:  # noqa: BLE001
                logger.error("Error rendering prompt '%s': %s", prompt_name, exc)
                return format_error(msg_id, JsonRpcError(INTERNAL_ERROR, f"Internal error rendering prompt: {exc}"))

        else:
            return format_error(msg_id, JsonRpcError(METHOD_NOT_FOUND, f"Method '{method}' not found"))

    async def run_stdio(self) -> None:
        logger.info("Starting CineFlow MCP Server (%s v%s) over stdio...", self.name, self.version)
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            line_bytes = await reader.readline()
            if not line_bytes:
                logger.info("EOF received on stdin, shutting down CineFlow MCP server.")
                break

            line_str = line_bytes.decode("utf-8")
            response = await self.handle_message(line_str)
            if response:
                sys.stdout.write(response + "\n")
                sys.stdout.flush()


def main() -> None:
    server = McpServer()
    try:
        asyncio.run(server.run_stdio())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Server terminated by signal.")


if __name__ == "__main__":
    main()
