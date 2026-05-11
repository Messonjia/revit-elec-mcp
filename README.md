# Revit Electrical MCP Server

An MCP (Model Context Protocol) server that gives AI assistants like Claude direct access
to a live Revit electrical model. Ask questions about panels, circuits, and devices in plain
language — Claude queries the model and reasons over the results.

## What this is

A bridge between Claude Desktop and Autodesk Revit, built in two layers:

1. **MCP server** (`mcp_server/main.py`) — a Python process that exposes Revit data as tools
   Claude can call. Runs locally, communicates with Claude Desktop over stdio.

2. **Revit add-in** (`revit_addin/`) — a C# add-in that loads into Revit at startup, exposes
   a WebSocket server on localhost, and executes Revit API calls on the UI thread via
   `ExternalEvent`. The MCP server connects to it to get live model data.

## Architecture

```
Claude Desktop
    │  JSON-RPC over stdio
    ▼
mcp_server/main.py  (Python, runs outside Revit)
    │  WebSocket  →  localhost:8765
    ▼
revit_addin/  (C# IExternalApplication, loaded by Revit at startup)
    │  Revit API
    ▼
Live .rvt model
```

The key threading constraint: Revit's API can only be called from the UI thread.
The WebSocket server runs on a background thread and schedules work via `ExternalEvent`,
which is Revit's sanctioned way to post work back to the UI thread.

## Tools

| Tool | Description | Status |
|---|---|---|
| `ping` | Verify the MCP server is reachable | Done |
| `query_elements` | Return all electrical elements from the live model | Fake data (Step 6) |
| `query_elements` (real) | Same tool, live Revit data via C# add-in | Planned (Step 7) |

## Current state

- MCP server scaffolded with `ping` and `query_elements` (hardcoded fake data)
- Wired into Claude Desktop and confirmed working end-to-end
- C# add-in not yet built — `query_elements` returns fake elements until Step 7

## Stack

- **Python 3.12** with `uv` for package management
- **FastMCP** (official Anthropic MCP SDK) for the MCP server layer
- **websockets** (Python async library) for the WebSocket client
- **C# / .NET 8** for the Revit add-in
- **Revit 2025** as the target Revit version
- **Claude Desktop** as the MCP client

## Setup

**Python MCP server:**
```powershell
cd mcp_server
uv sync
.venv\Scripts\python.exe main.py   # blocks, waiting for MCP client
```

**C# Revit add-in:**
```powershell
cd revit_addin
dotnet build                        # builds and copies .dll + .addin to Revit's addins folder
# then restart Revit
```

**Claude Desktop** — add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "revit-elec-mcp": {
      "command": "<absolute-path>\\mcp_server\\.venv\\Scripts\\python.exe",
      "args": ["<absolute-path>\\mcp_server\\main.py"]
    }
  }
}
```

## Project goal

Build a practical AI tool for AEC electrical workflows — panel schedule auditing, circuit
load analysis, coordination checks — while learning MCP, the Revit API, and how to design
tool interfaces that an LLM can actually use well.
