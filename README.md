# Revit Electrical MCP Server

An MCP (Model Context Protocol) server that gives AI assistants like Claude direct access
to a live Revit electrical model. Ask questions about panels, circuits, and devices in plain
language — Claude queries the model and reasons over the results.

## What this is

A bridge between Claude Desktop and Autodesk Revit, built in two layers:

1. **MCP server** (`main.py`) — a Python process that exposes Revit data as tools Claude
   can call. Runs locally, communicates with Claude Desktop over stdio.

2. **Revit bridge** (pyRevit, coming in Step 7) — a Python script running *inside* Revit's
   process with full API access. Exposes a local HTTP endpoint. The MCP server calls it to
   get live model data.

## Architecture

```
Claude Desktop
    │  JSON-RPC over stdio
    ▼
main.py  (MCP server — Python, runs outside Revit)
    │  HTTP  →  localhost:PORT
    ▼
pyRevit script  (runs inside Revit's process)
    │  Revit API
    ▼
Live .rvt model
```

## Tools

| Tool | Description | Status |
|---|---|---|
| `ping` | Verify the server is reachable | Done |
| `query_elements` | Query electrical elements by voltage, ampere, location, or load classification | Fake data (Step 6) |
| `query_elements` (real) | Same tool, live Revit data via pyRevit bridge | Planned (Step 7) |
| Clash detection | TBD | Planned |

## Current state

- MCP server scaffolded with `ping` and `query_elements` (hardcoded fake data)
- Wired into Claude Desktop and confirmed working end-to-end
- pyRevit bridge not yet built — `query_elements` returns fake elements until Step 7

## Stack

- **Python 3.12** with `uv` for package management
- **FastMCP** (official Anthropic MCP SDK) for the server layer
- **pyRevit** for the Revit-side bridge (planned)
- **Claude Desktop** as the MCP client

## Setup

```powershell
# Clone and install dependencies
git clone https://github.com/Messonjia/revit-elec-mcp.git
cd revit-elec-mcp
uv sync

# Run the server manually (should hang — waiting for MCP client)
.venv\Scripts\python.exe main.py
```

To connect to Claude Desktop, add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "revit-elec-mcp": {
      "command": "<absolute-path-to-repo>\\.venv\\Scripts\\python.exe",
      "args": ["<absolute-path-to-repo>\\main.py"]
    }
  }
}
```

## Project goal

Build a practical AI tool for AEC electrical workflows — panel schedule auditing, circuit
load analysis, coordination checks — while learning MCP, the Revit API, and how to design
tool interfaces that an LLM can actually use well.
