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

**Test tools interactively without Claude Desktop (MCP Inspector UI in browser):**
```powershell
uv run mcp dev main.py
```
Note: tools that call `_send` will fail unless Revit is also open — `ping` works standalone.

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

## Current state (Steps 1–10 complete)

```
Claude Desktop
    ↓ JSON-RPC over stdio
main.py  (FastMCP server, runs outside Revit)
    ├── nec_rules.py  (pure Python NEC logic — no Revit, no MCP, no WebSocket)
    ↓ WebSocket ws://localhost:8765
C# Revit add-in (RevitElecMcp.dll, inside Revit's process)
    ↓ ExternalEvent → UI thread → FilteredElementCollector / ElectricalSystem
Live .rvt model
```

`main.py` is the MCP server. FastMCP introspects each `@mcp.tool()` decorated function: function name → tool name, docstring → LLM-visible description, type annotations → JSON Schema for parameters. Return type `str` is auto-wrapped in `TextContent`.

`_send(payload)` is a shared async helper in `main.py` — all tools use it to connect, send, and receive over WebSocket rather than duplicating that logic.

`nec_rules.py` is a pure Python module imported by `main.py`. It contains deterministic NEC rule logic that operates on circuit dicts already extracted by C#. **The split:** C# handles everything that requires the Revit API; `nec_rules.py` handles everything that is just math on data already in Python.

## Tool status

| Tool | Description | Status |
|---|---|---|
| `ping` | Verify the MCP server is reachable | Done |
| `query_elements` | Returns electrical fixtures (id + name) from live Revit model | Done |
| `list_panels` | Returns all electrical panels (distribution equipment) — call this first to discover panel names | Done |
| `check_breaker_sizing(panel)` | Returns circuits on a panel with load + breaker data; Claude applies NEC 210.20(A) | Done |
| `fix_breaker_size(circuit_id, new_rating)` | Writes corrected breaker rating to Revit inside a Transaction (agentic) | Done (Step 9) |
| `check_breaker_compliance(panel)` | NEC 210.20(A) breaker sizing compliance — deterministic Python rules, circuit-by-circuit report | Done (Step 10) |

## C# add-in file structure

Reading order (the order Revit itself processes them):
1. `RevitElecMcp.addin` — the only file Revit reads directly. Key fields:
   - `Type="Application"` — loads at Revit startup, no user button required
   - `Assembly` — bare filename (`RevitElecMcp.dll`); works because both files land in the same Addins folder
   - `FullClassName` — `RevitElecMcp.App`; must match namespace + class exactly (Revit uses reflection)
   - `AddInId` — a GUID; generate once, never change — Revit uses it to track the add-in's identity across installs
2. `RevitElecMcp.csproj` — controls build and deploy. Key details: targets `net8.0-windows`, references Revit 2025 API via `Nice3point.Revit.Api.*` with `ExcludeAssets="runtime"` (don't bundle Revit's own DLLs), and the `CopyToRevitAddins` post-build target copies both files to `%AppData%\Autodesk\Revit\Addins\2025\`.
3. `App.cs` — `IExternalApplication` entry point. `OnStartup` creates all handlers and `ExternalEvent` objects on the UI thread, then fires `WebSocketServer.StartAsync()` on a background thread via `Task.Run`. `OnShutdown` calls `Stop()`.
4. `ElementQueryHandler.cs` — `IExternalEventHandler` for `get_elements`. Queries `OST_ElectricalFixtures` (receptacles, luminaires, HRU connections — devices wired *to* circuits, not the panels themselves), returns `id` + `name` per fixture.
5. `CircuitQueryHandler.cs` — `IExternalEventHandler` for `get_circuits`. Queries `OST_ElectricalCircuit`, casts each to `ElectricalSystem` (in `Autodesk.Revit.DB.Electrical`), filters by `PanelName`, returns circuit data including `load_classification` for NEC rule routing. `is_spare` is derived by checking `sys.Elements.Size == 0`.
6. `PanelQueryHandler.cs` — `IExternalEventHandler` for `list_panels`. Queries `OST_ElectricalEquipment` (panels, switchboards, MCCs — not fixtures), returns `id` + `name`.
7. `BreakerFixHandler.cs` — `IExternalEventHandler` for `fix_breaker`. Accepts `CircuitId` + `NewRating` from shared state, resolves the element, wraps the `RBS_ELEC_CIRCUIT_RATING_PARAM` write in a `Transaction`. Uses `UnitUtils.ConvertToInternalUnits` before calling `param.Set()`.
8. `WebSocketServer.cs` — background `HttpListener` on `localhost:8765`. Parses the `command` field from incoming JSON and routes via a switch to the appropriate handler + `ExternalEvent`. Shared `RaiseAndWaitAsync` helper centralises the Denied-check and 5-second timeout so each command arm doesn't repeat it. **Protocol constraint:** each connection handles exactly one request/response cycle then closes. **Known footgun:** the receive buffer is 4096 bytes — responses larger than this are silently truncated at the byte boundary, producing unparseable JSON. A panel with ~40+ circuits will exceed this. If adding a new handler that could return large datasets, increase `buffer` in `HandleConnectionAsync` or implement chunked reads.

## Adding a new tool

**Does the tool need new data from Revit?** If yes, touch all four places below. If no (it applies rules to data an existing WebSocket command already returns), skip straight to step 4 and add rule logic to `nec_rules.py` — no C# required.

Every tool that needs new Revit data requires touching four places in this order:

1. **New `XxxHandler.cs`** — implement `IExternalEventHandler`. Add shared-state properties (request params + `TaskCompletionSource<string>`), do the Revit API work in `Execute()`, call `Tcs.SetResult(json)` when done.
2. **`App.cs`** — in `OnStartup`, construct the handler + `ExternalEvent.Create(handler)`, pass both to `WebSocketServer`.
3. **`WebSocketServer.cs`** — add a `Handle*Async()` method following the same TCS pattern, add an arm to the `command` switch, and update the constructor signature to accept the new handler and event.
4. **`main.py`** — add an `@mcp.tool()` async function that calls `_send({"command": "xxx", ...})`. The function name → tool name, docstring → what the LLM sees, type annotations → JSON schema. All tools that touch Revit must be `async def`; `ping` is the only synchronous tool because it never calls `_send`.

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
| `breaker_rating` | `RBS_ELEC_CIRCUIT_RATING_PARAM` | Amps, via `get_Parameter` — NOT run through `ConvertFromInternalUnits` because Revit's internal current unit is already Amps (1:1 ratio). The write path still calls `ConvertToInternalUnits(value, UnitTypeId.Amperes)` for correctness, even though it's a no-op today. |
| `load_classification` | `RBS_ELEC_LOAD_CLASSIFICATION` | String; drives NEC rule selection |

**NEC rule routing by `load_classification`:**
- `Lighting` / `Power` / `General` → NEC 210.20(A): breaker ≥ 125% of continuous load current
- `Motor` / `HVAC` → NEC 430/440: do not apply 125% rule; report as "manual review required"

## Revit write pattern (implemented in BreakerFixHandler)

Every Revit write must be wrapped in `new Transaction(doc, "name")` → `Start()` → `Commit()` / `RollBack()`. The transaction name shows up in Revit's undo history (`Ctrl+Z`). Using `using var tx` ensures `Dispose()` is called on exception, which abandons (not rolls back) the transaction — but the effect is the same. Transactions also run on the UI thread inside `Execute()` — no threading changes needed.

`param.Set()` takes internal units — always call `UnitUtils.ConvertToInternalUnits(value, UnitTypeId.Amperes)` before setting, just as you call `ConvertFromInternalUnits` when reading.

**Interaction design:** `fix_breaker_size` must only be called after user confirmation. This is enforced through the tool docstring (which the LLM sees), not code.

## `nec_rules.py` — NEC rule engine

Pure Python, no external dependencies. Three public symbols (plus `MOTOR_LOAD_TYPES`, which is module-level but not imported by `main.py`):

- **`STANDARD_SIZES`** — NEC 240.6(A) list `[15, 20, 25, ..., 200]`. Single source of truth; `next_standard_size` and the tool docstrings both reference this.
- **`next_standard_size(amps: float) -> int`** — returns the smallest standard size `>= amps`. Exact matches are not rounded up (e.g. `20.0 → 20`, not `25`).
- **`check_circuit(circuit: dict) -> dict`** — three-path dispatch:
  - `is_spare == True` → `status: "spare"`, no NEC article applied
  - `load_classification in {"Motor", "HVAC"}` → `status: "manual_review"`, `nec_ref: "NEC 430/440"`
  - everything else → NEC 210.20(A): `load_amps * 1.25` → `next_standard_size` → compare to `breaker_rating`

### Compliance result dict schema

Every `check_circuit` result contains:

| Field | Type | Note |
|---|---|---|
| `status` | str | `"pass"`, `"fail"`, `"spare"`, `"manual_review"` |
| `circuit_number` | str | From input |
| `panel` | str | From input |
| `load_classification` | str | From input |
| `actual_rating` | int | Current breaker in Revit model |
| `is_non_standard` | bool | `actual_rating` not in `STANDARD_SIZES` — data quality flag, separate from safety |
| `load_amps` | float\|None | `apparent_load_va / (voltage * phase_factor)`; null for spare/motor |
| `required_amps` | float\|None | `load_amps * 1.25` before rounding; null for spare/motor |
| `required_rating` | int\|None | `next_standard_size(required_amps)`; null for spare/motor |
| `is_oversized` | bool | `actual_rating > required_rating` — protected but larger than needed |
| `nec_ref` | str\|None | Article string Claude quotes verbatim, e.g. `"NEC 210.20(A)"` |
| `reason` | str | Full plain-English sentence; Claude can quote or paraphrase |

`check_breaker_compliance` wraps these per-circuit results in `{"panel": ..., "summary": {total, pass, fail, manual_review, spare}, "circuits": [...]}` so Claude can lead with headline counts before enumerating failures.

## Planned features

- **Additional NEC rules** — conductor sizing (NEC 310), service entrance (NEC 230), GFCI/AFCI requirements — each as a new function in `nec_rules.py` + a new `@mcp.tool()` in `main.py`. No C# required.
- **User-selectable code edition** — NEC 2020 vs. 2023 differ in arc-fault requirements; parameterise the rule set.
- **ASHRAE 90.1 lighting power density checks** — would require a new C# handler to query lighting fixture loads by space type.

## Package manager

This project uses `uv` (not pip). Always use `uv add <package>` to add dependencies; `uv sync` to install from the lock file. The lock file (`uv.lock`) is committed and should stay in sync.

Runtime Python dependencies (from `pyproject.toml`): `mcp[cli]` (FastMCP + CLI tooling) and `websockets` (async WebSocket client). Everything else is transitive. `nec_rules.py` has no dependencies — it is pure Python stdlib.

## Reference documents

- `Pre_Start.md` — step-by-step roadmap (Steps 1–9) with concept explanations and learning notes
- `Learning_Note.md` — learning journal covering `uv`, PowerShell vs cmd, MCP protocol mechanics, the ExternalEvent threading model, and design decisions with alternatives considered
- `Data_Layer_Fixes.md` — four Revit API bugs found in first real test (internal units, parameter StorageType, spare circuit detection, ElectricalEquipment vs ElectricalFixtures categories)
