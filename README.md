# CineFlow Studio: Universal AI Filmmaker & Video Director


## Установка с нуля (агент сделает сам)

Киньте в чистый чат IDE одну строку — агент сделает всё остальное:

```
Установи CineFlow Studio из https://github.com/MilayaMariyaAi/cineflow-studio
по инструкции из README — сделай всё сам, спрашивай только токен.
```

Агент: поставит uv, развернёт MCP-сервер и скилл, пропишет конфиги IDE и
попросит только персональный токен CineFlow (cineflow.aimari.ru →
POST /me/tokens → `cfp_…`). Полная пошаговая инструкция — в
[QUICKSTART_RU.md](QUICKSTART_RU.md).


In-IDE AI Filmmaking Studio powered by the Model Context Protocol (MCP),
ComfyUI, and DaVinci Resolve. Turn screenplays and book stories into
cinematic AI videos: character turnaround sheets, scene graphs, closed-mouth
lip-sync guards, and 1-click round-trip editing in DaVinci Resolve.

## Why Studio, not just an agent

Your IDE agent can already call image/video APIs — that is not what you pay
for here. A raw agent flow loses the project when the session ends,
re-derives the craft rules at your expense (unaddressed references → lost
character identity → re-shoots; Cyrillic in prompts; open mouths on
lip-synced reaction shots), and regenerates everything after one line
changes. CineFlow Studio keeps:

- **a persistent project** — characters, locations, plan, shots survive
  sessions, IDEs and agents;
- **production invariants as code** — the boring lessons that each cost a
  real production incident, enforced on every generation;
- **partial rebuilds** — change one line, only the affected scenes are
  re-asked (replayed model answers are free);
- **one visual surface** — you review cards, storyboards and shots while the
  agent works on the same state.

Community mode is free and local. The subscription buys the cloud director
core — the plan, continuity and reference policy — not access to generation.

---

## Install

```bash
# Run the MCP server straight from this repo (PyPI release comes later)
uvx --from git+https://github.com/MilayaMariyaAi/cineflow-studio cineflow-mcp

# Or install the toolkit and set up the IDE integration
pip install git+https://github.com/MilayaMariyaAi/cineflow-studio
cineflow-setup
```

`cineflow-setup` installs the CineFlow skill into your IDE skill folders
(Cursor, Claude Code, Kimi, Cline, …), writes the MCP config with the
git-`uvx` command (see QUICKSTART_RU.md), and prints your GPU profile.

### MCP config snippet (manual setup)

```json
{
  "mcpServers": {
    "cineflow": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/MilayaMariyaAi/cineflow-studio", "cineflow-mcp"],
      "env": {
        "CINEFLOW_CLOUD_URL": "https://cineflow.aimari.ru",
        "CINEFLOW_API_KEY": "cfp_..."
      }
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

## License

Proprietary; see LICENSE. License terms are under consideration.
