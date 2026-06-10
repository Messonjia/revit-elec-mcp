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

> **Keep `AGENTS.md` in sync** — it is a near-identical copy of this file for Codex agents. Update it whenever this file changes.

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

**Smoke-test the NEC rule engine without Revit (pure Python, no dependencies):**
```powershell
.venv\Scripts\python.exe -c "from nec_rules import check_circuit; print(check_circuit({'circuit_number':'1','panel':'P1','apparent_load_va':1800,'voltage':120,'poles':1,'breaker_rating':15,'load_classification':'Lighting','is_spare':False}))"
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

## Current state

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
| `check_breaker_sizing(panel)` | Returns raw circuit data; Claude applies NEC 210.20(A) inline | Done |
| `fix_breaker_size(circuit_id, new_rating)` | Writes corrected breaker rating to Revit inside a Transaction (agentic) | Done (Step 9) |
| `check_breaker_compliance(panel)` | NEC 210.20(A) breaker sizing compliance — deterministic Python rules, circuit-by-circuit report | Done (Step 10) |

## Tool workflow

`list_panels` → `check_breaker_compliance(panel)` is the primary compliance workflow. `check_breaker_compliance` calls `check_circuit()` in `nec_rules.py` — the result is deterministic Python, not Claude inference.

`check_breaker_sizing` exists as a parallel "raw data" tool: it returns the same circuit data but instructs Claude to apply NEC rules inline. Use it for ad-hoc investigation; use `check_breaker_compliance` for structured reports. They both issue `get_circuits` to the C# add-in — only the Python post-processing differs.

## C# add-in file structure

Reading order (the order Revit itself processes them):
1. `RevitElecMcp.addin` (`revit_addin\RevitElecMcp\RevitElecMcp.addin`) — the only file Revit reads directly. Key fields:
   - `Type="Application"` — loads at Revit startup, no user button required
   - `Assembly` — bare filename (`RevitElecMcp.dll`); works because both files land in the same Addins folder
   - `FullClassName` — `RevitElecMcp.App`; must match namespace + class exactly (Revit uses reflection)
   - `AddInId` — a GUID; generate once, never change — Revit uses it to track the add-in's identity across installs
2. `RevitElecMcp.csproj` — controls build and deploy. Key details: targets `net8.0-windows`, references Revit 2025 API via `Nice3point.Revit.Api.*` with `ExcludeAssets="runtime"` (don't bundle Revit's own DLLs), and the `CopyToRevitAddins` post-build target copies both files to `%AppData%\Autodesk\Revit\Addins\2025\`.
3. `App.cs` — `IExternalApplication` entry point. `OnStartup` creates all handlers and `ExternalEvent` objects on the UI thread, then fires `WebSocketServer.StartAsync()` on a background thread via `Task.Run`. `OnShutdown` calls `Stop()`.
4. `ElementQueryHandler.cs` — `IExternalEventHandler` for `get_elements`. Queries `OST_ElectricalFixtures` (receptacles, luminaires, HRU connections — devices wired *to* circuits, not the panels themselves), returns `id` + `name` per fixture.
5. `CircuitQueryHandler.cs` — `IExternalEventHandler` for `get_circuits`. Queries `OST_ElectricalCircuit`, casts each to `ElectricalSystem` (in `Autodesk.Revit.DB.Electrical`), filters by `PanelName`, returns circuit data including `load_classification` for NEC rule routing. `is_spare` is derived by checking `sys.Elements.Size == 0`.
6. `PanelQueryHandler.cs` — `IExternalEventHandler` for `list_panels`. Queries `OST_ElectricalEquipment` (panels, switchboards, MCCs — distribution equipment that *has* circuit spaces). Contrast with `OST_ElectricalFixtures` (used by `ElementQueryHandler`), which covers the *devices connected to* those circuits. Returns `id` + `name`.
7. `BreakerFixHandler.cs` — `IExternalEventHandler` for `fix_breaker`. Accepts `CircuitId` + `NewRating` from shared state, resolves the element, wraps the `RBS_ELEC_CIRCUIT_RATING_PARAM` write in a `Transaction`. Uses `UnitUtils.ConvertToInternalUnits` before calling `param.Set()`.
8. `WebSocketServer.cs` — background `HttpListener` on `localhost:8765`. Parses the `command` field from incoming JSON and routes via a switch to the appropriate handler + `ExternalEvent`. Shared `RaiseAndWaitAsync` helper centralises the Denied-check and 5-second timeout so each command arm doesn't repeat it. **Protocol constraint:** each connection handles exactly one request/response cycle then closes. **Receive loop:** `HandleConnectionAsync` accumulates WebSocket frames into a `MemoryStream` until `EndOfMessage` is true — 4096 bytes is the chunk size, not the message size limit. This handles panels with 80+ circuits without truncation.

## Adding a new tool

**Does the tool need new data from Revit?** If yes, touch all four places below. If no (it applies rules to data an existing WebSocket command already returns), skip straight to step 4 and add rule logic to `nec_rules.py` — no C# required.

Every tool that needs new Revit data requires touching four places in this order:

1. **New `XxxHandler.cs`** — implement `IExternalEventHandler`. Add shared-state properties (request params + `TaskCompletionSource<string>`), do the Revit API work in `Execute()`, call `Tcs.SetResult(json)` when done. Also implement `GetName() => "RevitElecMcp.XxxHandler"` — Revit writes this to the journal file and shows it in Add-In Manager diagnostics. **Error convention:** always call `Tcs.SetResult(JsonSerializer.Serialize(new { error = "..." }))`, never `Tcs.SetException()` — the WebSocket server expects a string it can send back, not an exception to propagate.
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
| `id` | `ElementId.Value` | `long` (int64) in Revit 2024+ — `IntegerValue` is deprecated. Pass to `fix_breaker_size`. Python `int` handles it transparently. |
| `circuit_number` | `ElectricalSystem.CircuitNumber` | String, e.g. `"3"` |
| `panel` | `ElectricalSystem.PanelName` | String |
| `apparent_load_va` | `ElectricalSystem.ApparentLoad` | VA, converted via `ConvertFromInternalUnits` |
| `voltage` | `ElectricalSystem.Voltage` | Volts, converted via `ConvertFromInternalUnits` |
| `poles` | `ElectricalSystem.PolesNumber` | 1 or 3 |
| `breaker_rating` | `RBS_ELEC_CIRCUIT_RATING_PARAM` | Amps, via `AsDouble()` — NOT run through `ConvertFromInternalUnits` because Revit's internal current unit is already Amps (1:1 ratio). The write path still calls `ConvertToInternalUnits(value, UnitTypeId.Amperes)` for correctness, even though it's a no-op today. |
| `load_classification` | `RBS_ELEC_LOAD_CLASSIFICATION` | Usually stored as an `ElementId` reference — resolve with `doc.GetElement(param.AsElementId()).Name`. In some model configurations `StorageType` is `String` instead; the handler checks both. `AsString()` is not reliable alone. |

| `hp` | `RBS_ELEC_MOTOR_SIZE` on connected element | HP as `double?`; `null` when not a motor/HVAC circuit or parameter absent. Only read for `Motor`/`HVAC` load classifications. |

**`PanelName` filter:** if `PanelName` is `null`, `CircuitQueryHandler` returns every circuit in the model (no panel filter). No Python tool currently exposes this, but it is available to future tools by passing `"panel": null` (or omitting the key with a null-coalescing read on the C# side).

**NEC rule routing by `load_classification`:**
- `Lighting` / `Power` / `General` → NEC 210.20(A): breaker ≥ 125% of continuous load current
- `Motor` / `HVAC` with `hp` present → NEC 430.52: breaker ≤ 250% of FLC (from NEC Table 430.248/430.250); fail if breaker exceeds this cap
- `Motor` / `HVAC` with `hp` absent → `status: "manual_review"` — HP required to apply NEC 430.52

## Revit write pattern (implemented in BreakerFixHandler)

Every Revit write must be wrapped in `new Transaction(doc, "name")` → `Start()` → `Commit()` / `RollBack()`. The transaction name shows up in Revit's undo history (`Ctrl+Z`). Using `using var tx` ensures `Dispose()` is called on exception, which abandons (not rolls back) the transaction — but the effect is the same. Transactions also run on the UI thread inside `Execute()` — no threading changes needed.

`param.Set()` takes internal units — always call `UnitUtils.ConvertToInternalUnits(value, UnitTypeId.Amperes)` before setting, just as you call `ConvertFromInternalUnits` when reading.

**Interaction design:** `fix_breaker_size` must only be called after user confirmation. This is enforced through the tool docstring (which the LLM sees), not code.

## `nec_rules.py` — NEC rule engine

Pure Python, no external dependencies. Three public symbols (plus `MOTOR_LOAD_TYPES`, which is module-level but not imported by `main.py`):

- **`STANDARD_SIZES`** — NEC 240.6(A) full list, 15A through 6000A. Single source of truth; `next_standard_size` and the tool docstrings both reference this.
- **`next_standard_size(amps: float) -> int`** — returns the smallest standard size `>= amps`. Exact matches are not rounded up (e.g. `20.0 → 20`, not `25`).
- **`_FLC_1PH` / `_FLC_3PH`** — NEC Table 430.248 / 430.250 encoded as nested dicts `{hp: {voltage: flc_amps}}`. Private; accessed only through `_lookup_motor_flc`.
- **`_snap_voltage(circuit_v, table_voltages)`** — returns the largest table voltage ≤ `circuit_v` (e.g. 480V → 460V column). Returns `None` if below all table entries.
- **`_snap_hp(hp, table)`** — returns the closest HP key in the table (handles minor rounding artifacts from Revit).
- **`_lookup_motor_flc(hp, voltage, poles)`** — wraps `_snap_hp` + `_snap_voltage` into one call. Returns `(flc, snapped_hp, snapped_v)` or `None` when voltage is below all table entries (e.g. a 100V system). `None` triggers `manual_review` even when HP is present. Selects `_FLC_1PH` when `poles == 1`, `_FLC_3PH` for everything else — a 2-pole 240V single-phase motor uses the three-phase table.
- **`_check_motor_circuit(circuit, base, hp)`** — NEC 430.52 path: looks up FLC from HP + voltage, computes 250% cap, compares to `breaker_rating`. For motors, `required_rating` is a **maximum** (not minimum); fail if `actual > required`.
- **`check_circuit(circuit: dict) -> dict`** — four-path dispatch:
  - `is_spare == True` → `status: "spare"`, no NEC article applied
  - `load_classification in {"Motor", "HVAC"}` and `hp` present → `_check_motor_circuit()` → NEC 430.52
  - `load_classification in {"Motor", "HVAC"}` and `hp` absent → `status: "manual_review"`
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
| `required_amps` | float\|None | `load_amps * 1.25` for 210.20(A); `flc * 2.5` for 430.52; null for spare |
| `required_rating` | int\|None | `next_standard_size(required_amps)` — minimum for 210.20(A), **maximum** for 430.52 |
| `is_oversized` | bool | 210.20(A): `actual > required` — status still `"pass"`. Motor: always `False` — being too large is already a `"fail"`, not a flag |
| `is_zero_load` | bool | `apparent_load_va == 0` on a non-spare circuit — NEC math technically passes (0A → 15A min) but result is meaningless; flag to user as model data issue |
| `hp` | float\|None | Motor HP used for FLC lookup; `None` for non-motor circuits |
| `flc_amps` | float\|None | Full-load current from NEC Table 430.248/430.250; `None` for non-motor circuits |
| `nec_ref` | str\|None | Article string Claude quotes verbatim, e.g. `"NEC 210.20(A)"` |
| `reason` | str | Full plain-English sentence; Claude can quote or paraphrase |

`check_breaker_compliance` wraps these per-circuit results in `{"panel": ..., "summary": {total, pass, fail, manual_review, spare, zero_load_warning}, "circuits": [...]}` so Claude can lead with headline counts before enumerating failures. If `_send` returns an error object (e.g. Revit not open), `check_breaker_compliance` detects `isinstance(data, dict) and "error" in data` and surfaces it directly without attempting to apply NEC rules.

## Non-obvious behaviors

**ExternalEvent modal dialog constraint** — `Execute()` won't fire when Revit is showing any modal dialog (property editor, file dialog, or no-document state). `RaiseAndWaitAsync` hits its 5-second timeout and returns `"Timed out waiting for Revit"`. Close the dialog and retry — not a bug.

**Port 8765 binding failure** — if something else holds port 8765 when Revit starts, `HttpListener.Start()` throws inside `Task.Run`, which silently swallows the exception. The add-in appears loaded but the WebSocket server never starts; the Python side always returns `"Could not connect to Revit"`. Diagnose with `netstat -an | findstr 8765`.

**`poles` in NEC 210.20(A) path** — only `poles == 3` gets `phase_factor = 1.732`; `poles = 1` and `poles = 2` both use `1.0`. A 2-pole 240V single-phase circuit correctly computes `I = VA / (240 * 1.0)`. The same asymmetry applies in `_lookup_motor_flc`: `poles == 1` → `_FLC_1PH`, everything else → `_FLC_3PH`.

**Zero-load circuits** — `apparent_load_va = 0` produces `load_amps = 0`, `required_rating = 15`. Any 15A breaker passes. Zero-load non-spare circuits likely have bad model data; `is_spare` (checked first via `sys.Elements.Size == 0`) catches the common case but not miscategorized circuits.

## Planned features

- **Schedule Export (Step 11) — Next** — `list_schedules()` + `export_schedule(schedule_name)` tools. C# side: `ScheduleListHandler` uses `OfClass(typeof(ViewSchedule))` (not `OfCategory`); `ScheduleExportHandler` reads `GetTableData()` → `GetSectionData(SectionType.Header/Body)` → `GetCellText(row, col)`. Key quirk: `GetCellText()` always returns a formatted string (e.g. `"20 A"`, not `20.0`) and throws on out-of-range indices — guard with `NumberOfRows`/`NumberOfColumns`. Return shape: `{"schedule_name": ..., "columns": [...], "rows": [[...], ...]}`. Requires 4-file wiring (new handlers, App.cs, WebSocketServer.cs, main.py).
- **Additional NEC rules** — conductor sizing (NEC 310), service entrance (NEC 230), GFCI/AFCI requirements — each as a new function in `nec_rules.py` + a new `@mcp.tool()` in `main.py`. No C# required.
- **User-selectable code edition** — NEC 2020 vs. 2023 differ in arc-fault requirements; parameterise the rule set.
- **ASHRAE 90.1 lighting power density checks** — would require a new C# handler to query lighting fixture loads by space type.

## Package manager

This project uses `uv` (not pip). Always use `uv add <package>` to add dependencies; `uv sync` to install from the lock file. The lock file (`uv.lock`) is committed and should stay in sync.

Runtime Python dependencies (from `pyproject.toml`): `mcp[cli]>=1.27.0` (FastMCP + CLI tooling) and `websockets>=16.0` (async WebSocket client). Everything else is transitive. `nec_rules.py` has no dependencies — it is pure Python stdlib.

## Reference documents

- `Pre_Start.md` — step-by-step learning guide (Steps 1–11) with teaching notes, concept explanations, and "you'll know it worked when" checks. Contains the full design spec for Step 11 (Schedule Export). Read this for the rationale behind architectural decisions.
- `Learning_Note.md` — learning journal covering `uv`, PowerShell vs cmd, MCP protocol mechanics, the ExternalEvent threading model, and design decisions with alternatives considered
- `Data_Layer_Fixes.md` — four Revit API bugs found in first real test (internal units, parameter StorageType, spare circuit detection, ElectricalEquipment vs ElectricalFixtures categories)
- `AGENTS.md` — near-identical copy of this file for Codex agents (see sync note at top).
