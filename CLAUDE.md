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
Requires Python 3.12 (pinned in `.python-version`; `uv` manages this automatically).

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

## Current state (Steps 1–8 complete)

```
Claude Desktop
    ↓ JSON-RPC over stdio
main.py  (FastMCP server, runs outside Revit)
    ↓ WebSocket ws://localhost:8765
C# Revit add-in (RevitElecMcp.dll, inside Revit's process)
    ↓ ExternalEvent → UI thread → FilteredElementCollector / ElectricalSystem
Live .rvt model
```

`main.py` is the entire Python server. FastMCP introspects each `@mcp.tool()` decorated function: function name → tool name, docstring → LLM-visible description, type annotations → JSON Schema for parameters. Return type `str` is auto-wrapped in `TextContent`.

`_send(payload)` is a shared async helper in `main.py` — all tools use it to connect, send, and receive over WebSocket rather than duplicating that logic.

## Tool status

| Tool | Description | Status |
|---|---|---|
| `ping` | Verify the MCP server is reachable | Done |
| `query_elements` | Returns electrical fixtures (id + name) from live Revit model | Done |
| `check_breaker_sizing(panel)` | Returns circuits on a panel with load + breaker data; Claude applies NEC 210.20(A) | Done (Step 8) |
| `fix_breaker_size(circuit_id, new_rating)` | Writes corrected breaker rating to Revit inside a Transaction (agentic) | Step 9 |
| `check_code_compliance` | NEC 2023 compliance via RAG | Step 10 |

## C# add-in file structure

Reading order (the order Revit itself processes them):
1. `RevitElecMcp.addin` — the only file Revit reads directly. Key fields:
   - `Type="Application"` — loads at Revit startup, no user button required
   - `Assembly` — bare filename (`RevitElecMcp.dll`); works because both files land in the same Addins folder
   - `FullClassName` — `RevitElecMcp.App`; must match namespace + class exactly (Revit uses reflection)
   - `AddInId` — a GUID; generate once, never change — Revit uses it to track the add-in's identity across installs
2. `RevitElecMcp.csproj` — controls build and deploy. Key details: targets `net8.0-windows`, references Revit 2025 API via `Nice3point.Revit.Api.*` with `ExcludeAssets="runtime"` (don't bundle Revit's own DLLs), and the `CopyToRevitAddins` post-build target copies both files to `%AppData%\Autodesk\Revit\Addins\2025\`.
3. `App.cs` — `IExternalApplication` entry point. `OnStartup` creates all handlers and `ExternalEvent` objects on the UI thread, then fires `WebSocketServer.StartAsync()` on a background thread via `Task.Run`. `OnShutdown` calls `Stop()`.
4. `ElementQueryHandler.cs` — `IExternalEventHandler` for `get_elements`. Queries `OST_ElectricalFixtures`, returns `id` + `name` per fixture.
5. `CircuitQueryHandler.cs` — `IExternalEventHandler` for `get_circuits`. Queries `OST_ElectricalCircuit`, casts each to `ElectricalSystem` (in `Autodesk.Revit.DB.Electrical`), filters by `PanelName`, returns circuit data including `load_classification` for NEC rule routing.
6. `WebSocketServer.cs` — background `HttpListener` on `localhost:8765`. Parses the `command` field from incoming JSON and routes via a switch to the appropriate handler + `ExternalEvent`. Shared `RaiseAndWaitAsync` helper centralises the Denied-check and 5-second timeout so each command arm doesn't repeat it.

## Adding a new tool

Every new tool requires touching four places in this order:

1. **New `XxxHandler.cs`** — implement `IExternalEventHandler`. Add shared-state properties (request params + `TaskCompletionSource<string>`), do the Revit API work in `Execute()`, call `Tcs.SetResult(json)` when done.
2. **`App.cs`** — in `OnStartup`, construct the handler + `ExternalEvent.Create(handler)`, pass both to `WebSocketServer`.
3. **`WebSocketServer.cs`** — add a `Handle*Async()` method following the same TCS pattern, add an arm to the `command` switch, and update the constructor signature to accept the new handler and event.
4. **`main.py`** — add an `@mcp.tool()` async function that calls `_send({"command": "xxx", ...})`. The function name → tool name, docstring → what the LLM sees, type annotations → JSON schema.

After step 4: rebuild the C# project, restart Revit, restart Claude Desktop.

## Threading model (the non-obvious part)

Revit's API has no thread safety — it is only callable from Revit's own UI thread inside a "valid Revit API context." The WebSocket server runs on a background thread, so it cannot call the Revit API directly.

**`ExternalEvent` is the handoff mechanism:**
- Background thread sets handler shared state (e.g. `PanelName`), creates a `TaskCompletionSource`, calls `Raise()` (non-blocking — sets a flag), then `await`s the task.
- Revit polls the flag on the UI thread during idle time, calls `Execute()` in a valid context.
- `Execute()` runs the Revit API call and calls `tcs.SetResult()`, unblocking the background thread.
- Background thread sends the JSON response over WebSocket.

`ExternalEvent.Raise()` returns an `ExternalEventRequest` enum:
- `Accepted` / `Pending` — `Execute()` will fire; the 5-second timeout in `RaiseAndWaitAsync` guards against unexpected hangs.
- `Denied` — add-in isn't properly registered; `Execute()` will never fire. `RaiseAndWaitAsync` detects this and returns an error immediately.

**Shared state safety:** each handler stores request parameters (e.g. `PanelName`) as fields. This is safe because only one WebSocket connection is handled at a time — the background thread blocks on the TCS until `Execute()` completes before the next connection can arrive.

## Circuit schema (implemented in CircuitQueryHandler)

`ElectricalSystem` is in `Autodesk.Revit.DB.Electrical` (not the parent `Autodesk.Revit.DB`). Key distinction: `ApparentLoad` and `Voltage` are first-class typed properties; `breaker_rating` and `load_classification` are in the parameter bag (`get_Parameter(BuiltInParameter.XXX)`).

| Field | Source | Note |
|---|---|---|
| `id` | `ElementId.Value` | Pass to `fix_breaker_size` |
| `circuit_number` | `ElectricalSystem.CircuitNumber` | String, e.g. `"3"` |
| `panel` | `ElectricalSystem.PanelName` | String |
| `apparent_load_va` | `ElectricalSystem.ApparentLoad` | VA, internal Revit units |
| `voltage` | `ElectricalSystem.Voltage` | Volts |
| `poles` | `ElectricalSystem.PolesNumber` | 1 or 3 |
| `breaker_rating` | `RBS_ELEC_CIRCUIT_RATING_PARAM` | Amps, via `get_Parameter` |
| `load_classification` | `RBS_ELEC_LOAD_CLASSIFICATION` | String; drives NEC rule selection |

**NEC rule routing by `load_classification`:**
- `Lighting` / `Power` / `General` → NEC 210.20(A): breaker ≥ 125% of continuous load current
- `Motor` / `HVAC` → NEC 430/440: do not apply 125% rule; report as "manual review required"

## Planned features

### Step 9 — Agentic breaker fix (`fix_breaker_size`)

New write capability. Neither file exists yet — follow the "Adding a new tool" pattern above.

- **`BreakerFixHandler.cs`** (to create) — `IExternalEventHandler` that accepts `circuit_id` + `new_rating` from shared state, finds the element via `doc.GetElement(new ElementId(circuit_id))`, opens a `Transaction`, sets `RBS_ELEC_CIRCUIT_RATING_PARAM`, commits.
- **`WebSocketServer.cs`** — add `fix_breaker` arm to the existing switch.

New Python tool in `main.py`:
- `fix_breaker_size(circuit_id: int, new_rating: int)` — sends `{"command": "fix_breaker", ...}` over WebSocket. Docstring must make clear this writes to the model and should only be called after user confirmation.

**Transaction** is the new concept: every Revit write must be wrapped in `new Transaction(doc, "name")` → `Start()` → `Commit()` / `RollBack()`. The transaction name appears in Revit's undo history. Transactions also run on the UI thread inside `Execute()` — no threading changes needed.

**Interaction design:** Claude must propose the fix and wait for confirmation before calling `fix_breaker_size`. This is enforced through the tool docstring, not code.

### Step 10 — NEC 2023 code compliance (`check_code_compliance`) — RAG

- **Corpus**: NEC 2023 PDF → chunked text → vector embeddings stored locally (ChromaDB)
- **Flow**: user asks → retrieve relevant NEC sections → Claude reasons over sections + live model data → cites specific article numbers
- **Python stack**: `sentence-transformers` or OpenAI embeddings; `chromadb` for local vector store; retrieval in `main.py`
- **Future**: user-selectable NEC edition, ASHRAE 90.1, LEED electrical credits

## Package manager

This project uses `uv` (not pip). Always use `uv add <package>` to add dependencies; `uv sync` to install from the lock file. The lock file (`uv.lock`) is committed and should stay in sync.

## Reference documents

- `Pre_Start.md` — step-by-step roadmap (Steps 1–9) with concept explanations and learning notes
- `Learning_Note.md` — learning journal covering `uv`, PowerShell vs cmd, MCP protocol mechanics, the ExternalEvent threading model, and design decisions with alternatives considered
