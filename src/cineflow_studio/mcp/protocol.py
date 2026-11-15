"""MCP Protocol definitions and JSON-RPC 2.0 transport helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# JSON-RPC 2.0 Standard Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

LATEST_PROTOCOL_VERSION = "2024-11-05"


@dataclass
class JsonRpcError:
    code: int
    message: str
    data: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            res["data"] = self.data
        return res


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


def format_response(msg_id: int | str | None, result: Any) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": result,
    }
    return json.dumps(payload, ensure_ascii=False)


def format_error(msg_id: int | str | None, error: JsonRpcError) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": error.to_dict(),
    }
    return json.dumps(payload, ensure_ascii=False)


def format_tool_result(content: str, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": content,
            }
        ],
        "isError": is_error,
    }
