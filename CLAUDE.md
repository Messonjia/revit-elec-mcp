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
Then restart Claude Desktop. No automated tests exist yet — test tools manually by invoking them in a Claude Desktop chat session.

# Architecture

## Current state (Phase 1 — MCP scaffold)

```
Claude Desktop
    ↓ JSON-RPC over stdio
main.py  (FastMCP server, runs outside Revit)
    ↓ (hardcoded FAKE_ELEMENTS for now)
```

`main.py` is the entire server. FastMCP introspects each `@mcp.tool()` decorated function automatically: function name → tool name, docstring → LLM-visible description, type annotations → JSON Schema for parameters. Return type `str` is auto-wrapped in `TextContent`.

## Tool status

| Tool | Description | Status |
|---|---|---|
| `ping` | Verify the MCP server is reachable | Done |
| `query_elements` | Electrical elements filtered by voltage/ampere/location/classification | Fake data (Step 6) |
| `query_elements` (real) | Same tool, live Revit data via C# add-in | Planned (Step 7) |

## Planned state (Phase 2 — C# add-in bridge, Step 7)

```
Claude Desktop
    ↓ JSON-RPC over stdio
main.py
    ↓ WebSocket ws://localhost:8765
C# Revit add-in (RevitElecMcp.dll, inside Revit's process)
    ↓ ExternalEvent → UI thread → FilteredElementCollector
Live .rvt model
```

**Planned C# file structure for Step 7.4:**

- `App.cs` — creates handler and ExternalEvent at startup, starts WebSocketServer on background thread, stops it on shutdown
- `ElementQueryHandler.cs` — implements `IExternalEventHandler`; the only place Revit API calls happen. Runs `FilteredElementCollector`, serializes to JSON, signals the awaiting background thread via `TaskCompletionSource`
- `WebSocketServer.cs` — background listener on `localhost:8765`. On message: stores a `TaskCompletionSource` on the handler, calls `ExternalEvent.Raise()`, awaits the result, sends JSON reply

**Key constraints for Phase 2:**

- Revit's API is only callable from its own process on the **UI thread**. The C# add-in uses `ExternalEvent` to marshal calls from the WebSocket background thread onto the UI thread. `main.py` cannot call Revit directly.
- `ExternalEvent.Raise()` is non-blocking — it sets a flag. Revit calls `Execute()` on its own schedule (typically within milliseconds, unless Revit is in a modal dialog). If it returns `Denied`, the `TaskCompletionSource` will never complete — add a timeout guard.
- The C# project targets `net8.0-windows` and references Revit 2025 API via NuGet (`Nice3point.Revit.Api.*`) with `ExcludeAssets="runtime"` — Revit loads its own API DLLs at runtime, don't bundle them.
- The add-in manifest (`RevitElecMcp.addin`) declares `Type="Application"`, meaning it loads automatically when Revit starts (no user button required).

**Reading order for the addin files** (the order Revit itself processes them):
1. `RevitElecMcp.addin` — only file Revit reads directly; everything else flows from it
2. `RevitElecMcp.csproj` — how the DLL is built and deployed; focus on `ExcludeAssets="runtime"` and the `CopyToRevitAddins` build target
3. `App.cs` — what actually runs after Revit finds and loads the class named in `FullClassName`

## Element schema

Each electrical element carries both element-level data (`voltage`, `ampere`, `load_classification`) and connection-level data (`panel`, `circuit_number`). `panel` and `circuit_number` are `None` for un-circuited elements — this is normal in AEC workflows where circuiting happens after placement.

## Package manager

This project uses `uv` (not pip). Always use `uv add <package>` to add dependencies; `uv sync` to install from the lock file. The lock file (`uv.lock`) is committed and should stay in sync.

## Reference documents

- `Pre_Start.md` — step-by-step roadmap (Steps 1–7) with time estimates; Step 7 is the WebSocket + ExternalEvent bridge
- `Learning_Note.md` — learning journal covering `uv`, MCP protocol mechanics, and the ExternalEvent threading model
