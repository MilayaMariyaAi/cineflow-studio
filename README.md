# CineFlow Studio: Universal AI Filmmaker & Video Director

In-IDE AI Filmmaking Studio powered by the Model Context Protocol (MCP),
ComfyUI, and DaVinci Resolve. Turn screenplays and book stories into
cinematic AI videos: character turnaround sheets, scene graphs, closed-mouth
lip-sync guards, and 1-click round-trip editing in DaVinci Resolve.

## Install (no GitHub needed)

```bash
# Run the MCP server straight from PyPI
uvx cineflow-studio

# Or install the toolkit and set up the IDE integration
pip install cineflow-studio
cineflow-setup
```

`cineflow-setup` installs the CineFlow skill into your IDE skill folders
(Cursor, Claude Code, Kimi, Cline, …), writes the MCP config with the
`uvx cineflow-studio` command, and prints your GPU profile.

### MCP config snippet (manual setup)

```json
{
  "mcpServers": {
    "cineflow": {
      "command": "uvx",
      "args": ["cineflow-studio"]
    }
  }
}
```

## Modes

- **Community (free):** everything local — project store, ComfyUI workflow
  builder/runner, installers for models and custom nodes. Requires your own
  GPU (RTX 3090/4090 recommended) with local ComfyUI on `127.0.0.1:8188`.
- **Cloud director (CineFlow API key):** set `CINEFLOW_API_KEY` (and
  optionally `CINEFLOW_CLOUD_URL`) to let the CineFlow server handle
  narrative planning, cross-scene continuity, and reference policy. The tier
  and entitlements are decided by the CineFlow server — this client never
  grants them locally.

## AI Director persona

Follow the bundled skill: `cineflow_studio/skill/cineflow/SKILL.md`
(installed into your IDE skill folder by `cineflow-setup`). Production
invariants: English-only diffusion prompts, explicit `<Subject N>` reference
naming, `render_name` aliases instead of real character names, closed-mouth
guard for silent shots.

## Install from this repository (no PyPI needed)

```bash
uvx --from git+https://github.com/MariyaLoginova/cineflow-studio cineflow-mcp
```

## License

Proprietary; see LICENSE. License terms are under consideration.
