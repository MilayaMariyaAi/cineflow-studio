from __future__ import annotations

from typing import Any

from cineflow_studio.comfy.errors import ComfyUIPromptFormatError


def is_ui_graph_workflow(data: dict) -> bool:
    return isinstance(data.get("nodes"), list) and "links" in data


def is_api_prompt_workflow(data: dict) -> bool:
    if not isinstance(data, dict) or not data:
        return False
    for key, value in data.items():
        if key in {"nodes", "links", "groups", "config", "extra"}:
            return False
        if not isinstance(value, dict):
            return False
        if "class_type" not in value or "inputs" not in value:
            return False
        if not isinstance(value.get("inputs"), dict):
            return False
    return True


def validate_api_prompt_links(api_prompt: dict[str, Any]) -> None:
    for node_id, node_payload in api_prompt.items():
        if not isinstance(node_payload, dict):
            continue
        inputs = node_payload.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for input_name, input_value in inputs.items():
            if (
                isinstance(input_value, list)
                and len(input_value) >= 2
                and isinstance(input_value[0], (str, int))
                and isinstance(input_value[1], int)
            ):
                linked_node_id = str(input_value[0])
                if linked_node_id not in api_prompt:
                    class_type = str(node_payload.get("class_type") or "unknown")
                    raise ComfyUIPromptFormatError(
                        "Broken workflow link: "
                        f"node {node_id} ({class_type}) input {input_name} "
                        f"references missing node {linked_node_id} [source=api_prompt]"
                    )


def _collect_ui_nodes(workflow_json: dict[str, Any]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    visited_graph_ids: set[int] = set()

    def walk_graph(graph: dict[str, Any]) -> None:
        obj_id = id(graph)
        if obj_id in visited_graph_ids:
            return
        visited_graph_ids.add(obj_id)

        graph_nodes = graph.get("nodes")
        if isinstance(graph_nodes, list):
            for node in graph_nodes:
                if isinstance(node, dict):
                    nodes.append(node)

        definitions = graph.get("definitions")
        if not isinstance(definitions, dict):
            return
        subgraphs = definitions.get("subgraphs")
        if not isinstance(subgraphs, list):
            return
        for subgraph in subgraphs:
            if isinstance(subgraph, dict):
                walk_graph(subgraph)

    walk_graph(workflow_json)
    return nodes


_SKIP_WIDGET_KEYS = frozenset(
    {
        "fixed",
        "randomize",
        "choose audio to upload",
        "choose image to upload",
        "control_after_generate",
    }
)


def _scalar_widget_inputs(node: dict[str, Any]) -> dict[str, Any]:
    """Widget-only inputs (VHS dicts, CLIPTextEncode text, PrimitiveInt value)."""
    out: dict[str, Any] = {}
    named = node.get("widgets_values_named")
    if isinstance(named, dict):
        for key, value in named.items():
            name = str(key)
            if name in _SKIP_WIDGET_KEYS or isinstance(value, dict) or value is None:
                continue
            out[name] = value
    values = node.get("widgets_values")
    if isinstance(values, dict):
        for key, value in values.items():
            name = str(key)
            if name in out or name in _SKIP_WIDGET_KEYS or isinstance(value, dict) or value is None:
                continue
            out[name] = value
    if (
        "text" not in out
        and str(node.get("type") or "") == "CLIPTextEncode"
        and isinstance(values, list)
        and values
        and isinstance(values[0], str)
    ):
        out["text"] = values[0]
    if (
        "value" not in out
        and str(node.get("type") or "") == "PrimitiveInt"
        and isinstance(values, list)
        and values
        and isinstance(values[0], (int, float, str))
    ):
        out["value"] = values[0]
    return out


_VIRTUAL_PASSTHROUGH_TYPES = frozenset({"SetNode", "GetNode"})


def _virtual_slot_name(node: dict[str, Any]) -> str:
    values = node.get("widgets_values")
    if isinstance(values, list):
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(values, dict):
        for value in values.values():
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _resolve_virtual_passthrough(
    prompt: dict[str, Any],
    set_sources: dict[str, list[Any]],
    get_slots: dict[str, str],
) -> None:
    """Inline KJNodes Set/Get pairs. They are frontend-only; Comfy has no class."""
    if not get_slots and not set_sources:
        return

    def resolve(source: list[Any], seen: set[str]) -> list[Any]:
        node_id = str(source[0])
        if node_id not in get_slots:
            return source
        if node_id in seen:
            raise ComfyUIPromptFormatError(
                f"Workflow payload conversion failed: Set/Get cycle at node {node_id}"
            )
        seen.add(node_id)
        slot = get_slots[node_id]
        upstream = set_sources.get(slot)
        if upstream is None:
            raise ComfyUIPromptFormatError(
                f"Workflow payload conversion failed: GetNode {node_id} has no SetNode for '{slot}'"
            )
        return resolve(upstream, seen)

    for node_payload in prompt.values():
        inputs = node_payload.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for input_name, input_value in list(inputs.items()):
            if (
                isinstance(input_value, list)
                and len(input_value) >= 2
                and isinstance(input_value[1], int)
                and str(input_value[0]) in get_slots
            ):
                inputs[input_name] = resolve(input_value, set())

    for node_id, node_payload in list(prompt.items()):
        if node_payload.get("class_type") in _VIRTUAL_PASSTHROUGH_TYPES:
            del prompt[node_id]


def _convert_ui_graph_to_api_prompt(workflow_json: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    nodes = _collect_ui_nodes(workflow_json)
    links = workflow_json.get("links")
    warnings: list[str] = []
    if not nodes or not isinstance(links, list):
        raise ComfyUIPromptFormatError(
            "Workflow payload is UI graph format and cannot be queued until converted to ComfyUI API prompt format."
        )

    link_map: dict[tuple[str, int], list[Any]] = {}
    for item in links:
        # Comfy UI link format: [id, from_node, from_slot, to_node, to_slot, type]
        if isinstance(item, list) and len(item) >= 5:
            to_node = item[3]
            to_slot = item[4]
            link_map[(str(to_node), int(to_slot))] = [str(item[1]), int(item[2])]

    prompt: dict[str, Any] = {}
    set_sources: dict[str, list[Any]] = {}
    get_slots: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        class_type = node.get("type")
        if node_id is None or not class_type:
            warnings.append("Skipped UI node with missing id/type.")
            continue
        node_key = str(node_id)
        if class_type in _VIRTUAL_PASSTHROUGH_TYPES:
            slot = _virtual_slot_name(node)
            if class_type == "GetNode":
                get_slots[node_key] = slot
            else:
                upstream = link_map.get((node_key, 0))
                if upstream is not None:
                    set_sources[slot] = upstream
        inputs: dict[str, Any] = {}

        widgets_values = node.get("widgets_values")
        input_meta = node.get("inputs")
        named_widgets = node.get("widgets_values_named")
        if not isinstance(named_widgets, dict):
            named_widgets = None
        if isinstance(input_meta, list):
            widget_values_list = widgets_values if isinstance(widgets_values, list) else []
            widget_idx = 0
            for idx, meta in enumerate(input_meta):
                if not isinstance(meta, dict):
                    continue
                input_name = meta.get("name")
                if not input_name:
                    continue
                link_val = link_map.get((node_key, idx))
                if link_val:
                    inputs[input_name] = link_val
                    continue
                if not isinstance(meta.get("widget"), dict):
                    # Optional socket left unconnected (e.g. MiniMaxH3ImageToVideo's
                    # last_frame) — has no widget backing it, so it has no entry in
                    # widgets_values either. Leaving it out of inputs is correct;
                    # treating it as a positional widget slot (the old behavior)
                    # both fabricates a bogus value here and desyncs every widget
                    # that follows it in this node.
                    continue
                # widgets_values is positional and ComfyUI silently inserts an
                # extra "control_after_generate" entry right after a seed-style
                # widget with no matching input_meta slot for it — so positional
                # indexing desyncs for every widget after the first seed. The
                # named dict (when present) is keyed by actual input name and
                # immune to that, so prefer it; positional stays only as a
                # fallback for exports that lack it.
                if named_widgets is not None and input_name in named_widgets:
                    inputs[input_name] = named_widgets[input_name]
                elif widget_idx < len(widget_values_list):
                    inputs[input_name] = widget_values_list[widget_idx]
                    widget_idx += 1
        elif isinstance(widgets_values, list):
            warnings.append(f"UI node {node_key} has widgets without named input metadata.")

        for widget_name, widget_value in _scalar_widget_inputs(node).items():
            inputs.setdefault(widget_name, widget_value)

        prompt[node_key] = {"class_type": class_type, "inputs": inputs}

    _resolve_virtual_passthrough(prompt, set_sources, get_slots)

    if not is_api_prompt_workflow(prompt):
        raise ComfyUIPromptFormatError(
            "Workflow payload is UI graph format and cannot be queued until converted to ComfyUI API prompt format."
        )
    validate_api_prompt_links(prompt)
    if warnings:
        warnings.append("Best-effort UI->API conversion was used.")
    return prompt, warnings


def ensure_api_prompt_format(workflow_json: dict) -> tuple[dict, list[str]]:
    if is_api_prompt_workflow(workflow_json):
        validate_api_prompt_links(workflow_json)
        return workflow_json, []
    if is_ui_graph_workflow(workflow_json):
        try:
            return _convert_ui_graph_to_api_prompt(workflow_json)
        except ComfyUIPromptFormatError as exc:
            text = str(exc)
            if "Broken workflow link:" in text and "references missing node" in text:
                tail = text.split("references missing node", 1)[1].strip()
                missing_node = tail.split(" ", 1)[0]
                raise ComfyUIPromptFormatError(
                    f"Workflow payload conversion failed: missing linked node {missing_node}"
                ) from exc
            raise
    raise ComfyUIPromptFormatError(
        "Workflow payload is neither ComfyUI API prompt format nor recognized UI graph format."
    )
