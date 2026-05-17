# Revit Electrical MCP Server

An MCP (Model Context Protocol) server that gives AI assistants like Claude direct access
to a live Revit electrical model. Ask questions about panels, circuits, and devices in plain
language — Claude queries the model and reasons over the results.

## What this is

A bridge between Claude Desktop and Autodesk Revit, built in two layers:

1. **MCP server** (`main.py`) — a Python process that exposes Revit data as tools Claude can
   call. Runs locally, communicates with Claude Desktop over stdio.

2. **Revit add-in** (`revit_addin/`) — a C# add-in that loads into Revit at startup, exposes
   a WebSocket server on localhost, and executes Revit API calls on the UI thread via
   `ExternalEvent`. The MCP server connects to it to get live model data.

## Architecture

```
Claude Desktop
    │  JSON-RPC over stdio
    ▼
main.py  (Python, runs outside Revit)
    │  WebSocket  →  ws://localhost:8765
    ▼
revit_addin/  (C# IExternalApplication, loaded by Revit at startup)
    │  ExternalEvent → UI thread → Revit API
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
| `query_elements` | Return all electrical fixtures from the live model | Done |
| `check_breaker_sizing` | Return circuits on a panel with load + breaker data; Claude checks NEC 210.20(A) sizing | Done |
| `fix_breaker_size` | Write a corrected breaker rating back to Revit (agentic, confirms before writing) | Step 9 |

## Current state

- Full read stack working end-to-end: Claude Desktop → MCP server → WebSocket → C# add-in → live Revit model
- `check_breaker_sizing` returns circuit load, voltage, poles, breaker rating, and load classification per circuit
- Motor/HVAC loads reported as "manual review required" — NEC 430/440 rules not yet implemented
- Write capability (Step 9) not yet built — agentic breaker fix coming next

## Stack

- **Python 3.12** with `uv` for package management
- **FastMCP** (official Anthropic MCP SDK) for the MCP server layer
- **websockets** (Python async library) for the WebSocket client
- **C# / .NET 8** for the Revit add-in
- **Revit 2025** as the target Revit version
- **Claude Desktop** as the MCP client

## Setup

**Python MCP server (one-time):**
```powershell
uv sync
```

**C# Revit add-in:**
```powershell
dotnet build revit_addin\RevitElecMcp\RevitElecMcp.csproj
# Post-build step copies .dll + .addin to %AppData%\Autodesk\Revit\Addins\2025\
# Restart Revit after each build
```

**Claude Desktop** — add to `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "revit-elec-mcp": {
      "command": "<absolute-path>\\.venv\\Scripts\\python.exe",
      "args": ["<absolute-path>\\main.py"]
    }
  }
}
```

## Project goal

Build a practical AI tool for AEC electrical workflows — panel schedule auditing, circuit
load analysis, NEC code compliance checks — while learning MCP, the Revit API, and how to
design tool interfaces that an LLM can actually use well.
