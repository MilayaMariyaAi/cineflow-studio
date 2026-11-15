"""Model Context Protocol (MCP) Resources Surface for CineFlow.

Resources provide read-only data surfaces mapped to URIs (Host-driven context)
without consuming token context until requested by the client.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from cineflow_studio.installer.hardware import inspect_hardware
from cineflow_studio.installer.manifest import MODELS_CATALOG, WORKFLOWS_CATALOG
from cineflow_studio.mcp.project_store import list_all_projects


@dataclass
class ResourceDefinition:
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


STATIC_RESOURCES = [
    ResourceDefinition(
        uri="cineflow://projects",
        name="Studio Projects Inventory",
        description="List of all registered projects, production stages, cast sizes, and scene counts.",
    ),
    ResourceDefinition(
        uri="cineflow://models/catalog",
        name="ComfyUI Models Catalog",
        description="Comprehensive inventory of weights (LTX, FLUX, Qwen Vision CV, Higgs TTS) and hardware profiles.",
    ),
    ResourceDefinition(
        uri="cineflow://workflows/catalog",
        name="ComfyUI Workflows Catalog",
        description="Verified ComfyUI pipeline blueprints (photo-to-video, turnaround cards, speech cloning, CV inspection).",
    ),
    ResourceDefinition(
        uri="cineflow://hardware/profile",
        name="Hardware & VRAM Profile",
        description="Current machine hardware profile (GPU model, VRAM capacity, CPU cores, recommended flags).",
    ),
]


def get_resource_definitions() -> list[ResourceDefinition]:
    return list(STATIC_RESOURCES)


def read_resource_contents(uri: str) -> dict[str, Any]:
    """Reads and serializes the contents of an MCP resource URI."""
    clean_uri = uri.strip()

    if clean_uri == "cineflow://projects":
        data = list_all_projects()
        return {
            "uri": clean_uri,
            "mimeType": "application/json",
            "text": json.dumps(data, ensure_ascii=False, indent=2),
        }
    elif clean_uri == "cineflow://models/catalog":
        data = [m.to_dict() for m in MODELS_CATALOG]
        return {
            "uri": clean_uri,
            "mimeType": "application/json",
            "text": json.dumps(data, ensure_ascii=False, indent=2),
        }
    elif clean_uri == "cineflow://workflows/catalog":
        return {
            "uri": clean_uri,
            "mimeType": "application/json",
            "text": json.dumps(WORKFLOWS_CATALOG, ensure_ascii=False, indent=2),
        }
    elif clean_uri == "cineflow://hardware/profile":
        hw = inspect_hardware()
        return {
            "uri": clean_uri,
            "mimeType": "application/json",
            "text": json.dumps(hw.to_dict(), ensure_ascii=False, indent=2),
        }

    raise KeyError(f"Resource URI '{clean_uri}' not found.")
