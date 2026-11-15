"""Model Context Protocol (MCP) Prompts Surface for CineFlow.

Prompts provide user-driven prompt templates and slash-commands (Host-driven workflows)
that guide host IDE agents (Cursor, Trae, Kimi Code, OpenCode) through complex film production tasks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PromptArgument:
    name: str
    description: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "required": self.required,
        }


@dataclass
class PromptDefinition:
    name: str
    description: str
    arguments: list[PromptArgument] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": [arg.to_dict() for arg in self.arguments],
        }


STATIC_PROMPTS = [
    PromptDefinition(
        name="direct_scene",
        description="Interactive director co-pilot for planning, blocking, character continuity, and ComfyUI generation of a scene.",
        arguments=[
            PromptArgument(
                name="project_name",
                description="Target project title or slug (e.g. 'noir-film', 'detective-story').",
                required=True,
            ),
            PromptArgument(
                name="scene_number",
                description="Scene number or identifier (e.g. 'scene_01', '3').",
                required=True,
            ),
            PromptArgument(
                name="style_preset",
                description="Visual aesthetic and lens style (e.g. 'cinematic-35mm', 'cyberpunk-neon', 'vintage-noir').",
                required=False,
            ),
            PromptArgument(
                name="shot_count",
                description="Planned number of shots in the scene (default: 3).",
                required=False,
            ),
        ],
    ),
    PromptDefinition(
        name="audit_continuity",
        description="Audit character cast slots, costume consistency, dialogue speakers, and reference slot assignments.",
        arguments=[
            PromptArgument(
                name="project_name",
                description="Project title or ID to audit.",
                required=True,
            ),
            PromptArgument(
                name="scene_range",
                description="Scene range to audit (e.g. 'all', 'scene_01-scene_03').",
                required=False,
            ),
        ],
    ),
    PromptDefinition(
        name="transfer_universe_assets",
        description="Transfer heroes, locations, or props from an existing project into a new movie or episode with provenance tracking.",
        arguments=[
            PromptArgument(
                name="source_project",
                description="Source project title or ID to import assets from.",
                required=True,
            ),
            PromptArgument(
                name="target_project",
                description="Target project title or ID to receive the assets.",
                required=True,
            ),
            PromptArgument(
                name="asset_types",
                description="Comma-separated asset types ('characters,locations' or 'all').",
                required=False,
            ),
        ],
    ),
]


def get_prompt_definitions() -> list[PromptDefinition]:
    return list(STATIC_PROMPTS)


def render_prompt(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Renders prompt messages for the requested prompt name and arguments."""
    clean_name = name.strip()

    prompt_map = {p.name: p for p in STATIC_PROMPTS}
    if clean_name not in prompt_map:
        raise KeyError(f"Prompt '{clean_name}' not found.")

    prompt_def = prompt_map[clean_name]

    # Validate required arguments
    for arg in prompt_def.arguments:
        if arg.required and (arg.name not in arguments or not str(arguments[arg.name]).strip()):
            raise ValueError(f"Missing required argument '{arg.name}' for prompt '{clean_name}'.")

    if clean_name == "direct_scene":
        project = arguments["project_name"]
        scene = arguments["scene_number"]
        style = arguments.get("style_preset", "cinematic-35mm")
        shots = arguments.get("shot_count", "3")
        instructions = (
            f"You are the Lead AI Director directing Scene {scene} for project '{project}'.\n\n"
            f"Style Preset: {style}\n"
            f"Target Shot Count: {shots}\n\n"
            "Execution Instructions:\n"
            "1. Activate or inspect scene using `cineflow_scene_activate`.\n"
            "2. Retrieve scene dramatic explication and beat sheet with `cineflow_scene_directing_set`.\n"
            "3. Enforce Rule A (visual prompts in cinematic English) and Rule B (ref_policy: all attached reference images explicitly addressed as `<Subject N>`).\n"
            "4. Enforce Rule D (Issue #600): for reaction or silent shots, add explicit closed-mouth tokens ('lips firmly closed, silent expression').\n"
            "5. Plan the shot progression (Master -> Over-the-shoulder -> Close-up) and generate keyframes.\n"
            "6. Inspect output using `cineflow_vision_inspect` for aesthetic quality, anatomy, and closed-mouth compliance.\n"
            "7. Record ComfyUI workflow artifacts (`.comfy.json`) and sidecars (`.cineflow.json`).\n"
            "Present your directorial plan and ask the user for confirmation before firing ComfyUI render jobs."
        )
        return {
            "description": prompt_def.description,
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": instructions,
                    },
                }
            ],
        }

    elif clean_name == "audit_continuity":
        project = arguments["project_name"]
        scene_range = arguments.get("scene_range", "all")
        instructions = (
            f"Execute a comprehensive Production Continuity Audit for project '{project}' (Range: {scene_range}).\n\n"
            "Audit Checklist:\n"
            "1. Cast Name Aliasing: Verify authorial name vs render_name alias resolution via `Character.id`.\n"
            "2. Dialogue Cast Reconciliation: Confirm dialogue speakers match characters present in shot cast slots.\n"
            "3. Costume & Prop Carryover: Check `continuity_carryover` across scene transitions in Directed Narrative Scene Graph.\n"
            "4. Rule D Closed-Mouth Lip-Sync: Verify silent/reaction shots contain mouth restraint tokens.\n"
            "5. Reference Slot Assignment: Check that each reference in `ref_policy` is indexed 1..K and addressed in prompt.\n\n"
            "Report discrepancies and recommended corrective actions."
        )
        return {
            "description": prompt_def.description,
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": instructions,
                    },
                }
            ],
        }

    elif clean_name == "transfer_universe_assets":
        source = arguments["source_project"]
        target = arguments["target_project"]
        asset_types = arguments.get("asset_types", "characters,locations")
        instructions = (
            f"Transfer cinematic universe assets from '{source}' to '{target}' (Types: {asset_types}).\n\n"
            "Execution Steps:\n"
            "1. Locate source project using `cineflow_projects_list`.\n"
            "2. Check existing assets in target project to prevent unintended overwrites.\n"
            "3. Execute transfer via `cineflow_assets_transfer` with `conflict_strategy='skip'`.\n"
            "4. Confirm physical file cloning in `materials/` and provenance record creation.\n"
            "5. Guide user on whether costume/appearance adaptations are needed for the new storyline."
        )
        return {
            "description": prompt_def.description,
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": instructions,
                    },
                }
            ],
        }

    raise KeyError(f"Prompt '{clean_name}' renderer not implemented.")
