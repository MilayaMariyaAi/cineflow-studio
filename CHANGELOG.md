# Changelog

## 0.1.0 (unreleased)

First package release.

- CineFlow MCP server: 42 studio tools (projects, scene graphs, ComfyUI
  workflow builder/runner, model/node installer, DaVinci Resolve live link,
  vision inspection), 4 resources, 3 prompt templates.
- Director skill (`cineflow_studio/skill/cineflow`) installed into IDE skill
  folders by `cineflow-setup`; MCP configs written automatically.
- Community mode: everything local. Cloud mode: the CineFlow server decides
  the tier and entitlements (`GET /me`); script->plan through the server.
- Model manifest with verified public sources (see
  scripts/verify_manifest_urls.py).
