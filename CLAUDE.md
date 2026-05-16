# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Working style for this repo

I'm building this Revit MCP server partly to learn. Default to teaching mode:

1. Before writing code for a new concept, explain what we're about to build,
   why this approach over alternatives, and what the key abstractions are.
   Wait for me to say "go" before writing code.
2. When you write code, add inline comments on anything non-obvious — 
   especially MCP protocol details, async patterns, and Revit API quirks.
3. After writing a non-trivial chunk, give me a 3-5 bullet recap of what 
   the code does and one question I should be able to answer about it.
4. When I ask "why", give the real answer including tradeoffs — not the 
   reassuring version.
5. Prefer small, reviewable diffs. I want to read every line you write.
6. If I'm about to do something that won't scale or has a known footgun, 
   tell me before doing it, not after.

# Commands

**Python MCP server setup (one-time):**
```powershell
uv sync   # creates .venv and installs dependencies
```

**Run the MCP server standalone (blocks on stdio):**
```powershell
.venv\Scripts\python.exe main.py
```

**Build the C# Revit add-in:**
```powershell
dotnet build revit_addin\RevitElecMcp\RevitElecMcp.csproj
```
The post-build step automatically copies `RevitElecMcp.dll` and `RevitElecMcp.addin` to `%AppData%\Autodesk\Revit\Addins\2025\`. Restart Revit after each build.

**Wire into Claude Desktop** — edit `%APPDATA%\Claude\claude_desktop_config.json`:
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
Then restart Claude Desktop. No automated tests exist — test tools manually by invoking them in a Claude Desktop chat session.

# Architecture

## Current state (Phase 2 — full stack, Steps 1–7.5 complete)

```
Claude Desktop
    ↓ JSON-RPC over stdio
main.py  (FastMCP server, runs outside Revit)
    ↓ WebSocket ws://localhost:8765
C# Revit add-in (RevitElecMcp.dll, inside Revit's process)
    ↓ ExternalEvent → UI thread → FilteredElementCollector
Live .rvt model
```

`main.py` is the entire Python server. FastMCP introspects each `@mcp.tool()` decorated function: function name → tool name, docstring → LLM-visible description, type annotations → JSON Schema for parameters. Return type `str` is auto-wrapped in `TextContent`.

## Tool status

| Tool | Description | Status |
|---|---|---|
| `ping` | Verify the MCP server is reachable | Done |
| `query_elements` | Returns electrical fixtures from live Revit model via WebSocket | Done (id + name only) |
| `query_elements` (enriched) | Add electrical parameters: voltage, load, panel, circuit, level | Step 8 |
| `check_model_integrity` | Flag broken panel references, duplicate circuits, orphaned elements | Step 9 |
| `check_code_compliance` | NEC 2023 compliance via RAG — query specific rules against model data | Step 10 |

## C# add-in file structure

Reading order (the order Revit itself processes them):
1. `RevitElecMcp.addin` — the only file Revit reads directly. Declares `Type="Application"` (loads at Revit startup, no user button required) and points to the DLL and `FullClassName`.
2. `RevitElecMcp.csproj` — controls build and deploy. Key details: targets `net8.0-windows`, references Revit 2025 API via `Nice3point.Revit.Api.*` with `ExcludeAssets="runtime"` (don't bundle Revit's own DLLs), and the `CopyToRevitAddins` post-build target copies both files to `%AppData%\Autodesk\Revit\Addins\2025\`.
3. `App.cs` — `IExternalApplication` entry point. `OnStartup` creates the handler and `ExternalEvent` on the UI thread, then fires `WebSocketServer.StartAsync()` on a background thread via `Task.Run`. `OnShutdown` calls `Stop()`.
4. `ElementQueryHandler.cs` — implements `IExternalEventHandler`. The **only place Revit API calls happen**. `Execute()` runs on the UI thread: queries `FilteredElementCollector` for `OST_ElectricalFixtures`, serializes to JSON, signals the waiting background thread via `TaskCompletionSource<string>`.
5. `WebSocketServer.cs` — background `HttpListener` on `localhost:8765`. On message: stores a fresh `TaskCompletionSource` on the handler, calls `ExternalEvent.Raise()`, awaits the result (5-second timeout guard), sends JSON reply.

## Threading model (the non-obvious part)

Revit's API has no thread safety — it is only callable from Revit's own UI thread inside a "valid Revit API context." The WebSocket server runs on a background thread, so it cannot call the Revit API directly.

**`ExternalEvent` is the handoff mechanism:**
- Background thread stores a `TaskCompletionSource` on the handler, calls `Raise()` (non-blocking — sets a flag), then `await`s the task.
- Revit polls the flag on the UI thread during idle time, calls `Execute()` in a valid context.
- `Execute()` runs the Revit API call and calls `tcs.SetResult()`, unblocking the background thread.
- Background thread sends the JSON response over WebSocket.

`ExternalEvent.Raise()` returns an `ExternalEventRequest` enum:
- `Accepted` / `Pending` — `Execute()` will fire; the 5-second timeout guards against unexpected hangs.
- `Denied` — add-in isn't properly registered; `Execute()` will never fire. `WebSocketServer` detects this and sends an error response immediately rather than hanging.

## Element schema

Currently `ElementQueryHandler.Execute()` returns `id` (long) and `name` (string) per element — only `OST_ElectricalFixtures` instances, not type definitions.

**Target schema for Step 8** (key `BuiltInParameter` names for reading each field):

| Field | Source | BuiltInParameter |
|---|---|---|
| `id` | ElementId.Value | — |
| `name` | Element.Name | — |
| `level` | Level name | `LEVEL_PARAM` |
| `voltage` | Electrical system voltage | `RBS_ELEC_VOLTAGE` |
| `apparent_load` | Load in VA | `RBS_ELEC_APPARENT_LOAD` |
| `load_classification` | Load type label | `RBS_ELEC_LOAD_CLASSIFICATION` |
| `num_poles` | Number of poles | `RBS_ELEC_NUMBER_OF_POLES` |
| `panel` | Connected panel name | `RBS_ELEC_CIRCUIT_PANEL_PARAM` |
| `circuit_number` | Circuit number string | `RBS_ELEC_CIRCUIT_NUMBER` |
| `phase` | 1 / 3 phase | `RBS_ELEC_CIRCUIT_PHASE_PARAM` |

`panel` and `circuit_number` are `None` for un-circuited fixtures — normal in AEC workflows where circuiting happens after placement. The integrity checker (Step 9) flags fixtures where `panel` is set but that panel element doesn't exist in the model.

## Planned features

### Step 8 — Enrich element data
Extend `ElementQueryHandler` to read the parameters above using `element.get_Parameter(BuiltInParameter.XXX)?.AsString()` (or `AsDouble()` for numeric). Also add `OST_ElectricalEquipment` (panels, switchboards, transformers) as a second category so we have both sides of a circuit for Step 9.

### Step 9 — Model integrity checks (`check_model_integrity`)
A new MCP tool that runs a set of deterministic checks against the data returned by the enriched query:

- **Broken panel reference** — fixture's `panel` field names a panel that has no matching element in `OST_ElectricalEquipment`. This is the primary conflict class.
- **Duplicate circuit** — two fixtures share the same `panel` + `circuit_number` but are not on the same `ElectricalSystem`.
- **Overcapacity** — sum of `apparent_load` on a circuit exceeds the panel breaker rating.
- **Un-circuited fixtures** — fixtures with `panel = None` (informational, not always a problem).

All checks run in Python on the JSON payload returned from Revit — no new C# needed for most of them.

### Step 10 — NEC 2023 code compliance (`check_code_compliance`) — RAG
A retrieval-augmented tool that answers "does this model comply with NEC 2023 article X?" questions:

- **Corpus**: NEC 2023 (PDF → chunked text → vector embeddings stored locally, e.g. ChromaDB)
- **Flow**: user asks → retrieve relevant NEC sections → Claude reasons over those sections + live model data → cites specific article numbers in response
- **Python stack**: `sentence-transformers` or OpenAI embeddings for indexing; `chromadb` for local vector store; retrieval integrated into the MCP tool handler in `main.py`
- **Future options**: let user select NEC edition (2020, 2023), add ASHRAE 90.1 (energy), LEED electrical credits

## Package manager

This project uses `uv` (not pip). Always use `uv add <package>` to add dependencies; `uv sync` to install from the lock file. The lock file (`uv.lock`) is committed and should stay in sync.

## Reference documents

- `Pre_Start.md` — step-by-step roadmap (Steps 1–7) with time estimates and learning notes for each step
- `Learning_Note.md` — learning journal covering `uv`, PowerShell vs cmd, MCP protocol mechanics, the ExternalEvent threading model, and design decisions with alternatives considered
