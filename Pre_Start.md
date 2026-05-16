# Set up

The concrete next steps, in order
Step 1 — Environment (30 min, do alone, no Claude Code). Python 3.10+, uv or poetry for package management, install the official mcp Python SDK from PyPI. Verify with python -c "import mcp; print(mcp.__version__)". Doing this yourself rather than letting Claude Code do it means you'll know what's actually installed when something breaks later.

Step 2 — Read the Architecture sub-page of the spec (45 min, alone). Specifically the transport section. You need to make one decision before writing code: stdio transport for now. It's what Claude Desktop uses by default, it's the simplest, and it sidesteps the HTTP/SSE complexity. You'll likely move to HTTP later when bridging to Revit's C# process, but not yet.

Step 3 — Build the hello_world server (Claude Code, teaching mode on). This is your first real session. Prompt to start with:

Before writing any code, walk me through the structure of a minimal MCP server in Python using the official SDK. What are the entry points, what does the initialization handshake look like in code, and what's the minimum I need to expose one tool? Don't write code yet — explain the shape, then I'll say go.

Read the explanation. Push back on anything vague. Then say go and let it write the smallest possible server with one tool. Should be ~50 lines.
Step 4 — Wire it into Claude Desktop and watch it run. Edit your Claude Desktop config (claude_desktop_config.json), point it at your server, restart Claude Desktop, and call the tool from a chat. The first time you see Claude actually invoke your tool and get a response back, the whole protocol clicks. This is the moment that's worth more than any amount of spec reading.
Step 5 — Rebuild it from scratch (Karpathy pattern, alone, no Claude Code). Close the file. New file. Rebuild the hello_world server with the SDK docs open but Claude Code closed. If you get stuck, don't reach for Claude Code — open the SDK source on GitHub and read it. This is non-negotiable for the learning goal.
Step 6 — Now add the first Revit-shaped tool, but still fake. Add a tool called query_elements that returns hardcoded JSON pretending to be Revit elements. No Revit yet. The point: practice tool schema design (parameters, descriptions, return types) without the Revit complexity. This is also where you start thinking about what your tool interface should look like — what would an LLM agent actually want to ask about a Revit model? The answer to that question is more important than any code, and it's the part your domain experience makes uniquely valuable.
Step 7 — Build the Revit bridge. This is where the C# add-in lives. It's a separate
concern from MCP work — don't blur the two. The steps below take you from zero C# Revit
knowledge to one working tool that returns real electrical elements from a live model.

---

## Where to learn before coding

Do these in order, alone, before any Claude Code sessions:

1. **Revit API docs** — https://www.revitapidocs.com/
   Reference only. Look up `FilteredElementCollector`, `BuiltInCategory`,
   `ElectricalSystem`, and `BuiltInParameter` as you need them.

2. **Learn Revit API (YouTube)** — https://www.youtube.com/channel/UC1LgjdE6zW3HNWg-IGo2d-Q
   Erik Frits's channel. His examples are Python/pyRevit, but the `FilteredElementCollector`
   concepts transfer directly to C# — the API shape is identical, only the syntax differs.

3. **Revit API GitHub samples** — https://github.com/jeremytammik/the_building_coder_samples
   Jeremy Tammik's sample code. Search for `IExternalApplication` and
   `ExternalEvent` — the two C# patterns you'll need most.

---

## The concrete steps, in order

### Step 7.1 — Read, don't build yet (alone, ~1 hour)

Before any code, read enough to understand three concepts. You're not trying to
master them — just build a mental model so you're not confused when you see the code.

**Concept 1 — IExternalApplication vs IExternalCommand**
Revit add-ins can be two things: a `Command` (runs when a user clicks a button) or an
`Application` (runs at Revit startup and stays alive the whole session). You need
`Application` because your WebSocket listener must run continuously, not just when clicked.
Read: https://thebuildingcoder.typepad.com/blog/2022/02/getting-started-once-again.html

**Concept 2 — ExternalEvent**
The Revit API is not thread-safe. Your WebSocket server will run on a background thread,
but Revit API calls must happen on the UI thread. `ExternalEvent` is how you schedule
work from a background thread onto the UI thread safely.
Read: https://thebuildingcoder.typepad.com/blog/2013/12/replacing-an-idling-event-handler-by-an-external-event.html

**Concept 3 — FilteredElementCollector**
This is the primary way to query elements in a Revit model. You give it a category
(e.g., electrical fixtures) and it returns matching elements.
Read: https://www.revitapidocs.com/2026/263cf06b-98be-6f91-c4da-fb47d01688f3.htm

After reading, you should be able to answer:
- Why can't I just call the Revit API from my WebSocket thread?
- What's the difference between `OnStartup` and a command's `Execute` method?

---

### Step 7.2 — Set up the C# project (Claude Code, teaching mode, ~1 hour)

Start your session with:

> Before writing any code, explain the structure of a minimal C# Revit add-in that uses
> IExternalApplication. What files do I need, what does the .addin manifest do, and how
> does Revit find and load the DLL? Don't write code yet.

Read the explanation. Push back on anything unclear. Then say go.

What you're building: an add-in that loads into Revit and writes one line to the Revit
journal file (or a message box) on startup. No WebSocket yet, no Revit API queries yet —
just prove that Revit finds your DLL and runs your code.

**You'll know it worked when:** Revit starts and you see your message.
Read them in the order Revit itself processes them:
                                                                  
  1. RevitElecMcp.addin — start here. This is the only file Revit reads directly.  Everything else flows from it. Understand what each XML tag does before moving on.
  2. RevitElecMcp.csproj — read this second. It answers "how does the DLL get built and how   does it end up in the Addins folder?" Focus on the ExcludeAssets="runtime" comment and
  the CopyToRevitAddins build target at the bottom.

  3. App.cs — read last. By this point you already know Revit found the manifest, loaded
  the DLL, and is looking for the class named in FullClassName. Now you're just reading
  what that class actually does.

  The mental thread connecting all three: manifest tells Revit where to find the code →
  .csproj controls how the code is built and deployed → App.cs is what runs.

---

### Step 7.3 — First Revit API call from C# (alone, ~1 hour)

Close Claude Code. Add code to your `OnStartup` or a test command that:
1. Gets the active document (`uiApp.ActiveUIDocument?.Document`)
2. Runs a `FilteredElementCollector` for `OST_ElectricalFixtures`
3. Prints the element count somewhere visible (message box or journal)

Use the Revit API docs + Jeremy Tammik's samples. Do not use Claude Code for this step.

**You'll know it worked when:** you open a model with electrical fixtures and see the
correct count.

---

### Step 7.4 — Add the WebSocket server + ExternalEvent (Claude Code, teaching mode, ~2 hours)

This is the hardest step. Start your session with:

> Before writing any code, explain how ExternalEvent works in a C# Revit add-in.
> Specifically: I have a WebSocket server running on a background thread. A message
> arrives. How do I safely call the Revit API in response, and how do I get the result
> back to the WebSocket thread to send as a reply? Don't write code yet.

Read the explanation carefully — this threading model is non-obvious and it's the heart
of the whole system. Then say go.

What you're building:
- A WebSocket server on `localhost:8765` that starts when Revit loads
- An `IExternalEventHandler` that receives a command, queries electrical elements, and
  returns JSON
- Wiring that connects the two: WebSocket receives request → raises ExternalEvent →
  handler runs on UI thread → result goes back over WebSocket

Test it by sending a raw WebSocket message from a Python script (not the MCP server yet).
You should get back a JSON list of electrical elements from the live model.

**You'll know it worked when:** a Python one-liner connects to `localhost:8765`, sends
`{"command": "get_elements"}`, and gets real Revit data back.

---

### Step 7.5 — Connect the Python MCP server (Claude Code, ~30 min)

Now replace `FAKE_ELEMENTS` in `mcp_server/main.py` with a WebSocket call to your C#
add-in. The `query_elements` tool should:
1. Send `{"id": "<uuid>", "command": "get_elements"}` over WebSocket
2. Await the response
3. Return the JSON string to Claude

This step should be short — the hard work is already done. You're just wiring two things
that already work individually.

**You'll know it worked when:** you ask Claude Desktop "list all electrical fixtures in
the model" and get back real element names and IDs from the open `.rvt` file.

---

## What success looks like

You type in Claude Desktop:
> "List all electrical fixtures in the model"

Claude calls `query_elements`, your Python MCP server sends a WebSocket message to the
C# add-in, the add-in runs `FilteredElementCollector` on the UI thread via ExternalEvent,
and Claude gets back real element data from the live `.rvt` file.

That's the full stack: Claude → Python → WebSocket → C# → Revit API → live model.

---

## Step 8 — Breaker sizing check (read-only)

The goal: a new MCP tool `check_breaker_sizing(panel)` that returns every circuit
connected to a named panel, with enough electrical data for Claude to reason about
whether each breaker is correctly sized for its load.

No writes yet. No agentic behaviour yet. Just getting the right data out of Revit.

---

### Step 8.1 — Read, don't build yet (alone, ~45 min)

Three new concepts before any code.

---

**Concept 1 — ElectricalSystem: the circuit object**

So far you've queried `OST_ElectricalFixtures` — physical devices (receptacles, lights).
Circuits are different. In Revit's data model, a circuit is its own element type:
`ElectricalSystem`. It lives in a different category: `OST_ElectricalCircuit`.

`ElectricalSystem` is a subclass of `MEPSystem`, which is a subclass of `Element`.
That means `FilteredElementCollector` can find it, but you query by a different category:

```csharp
new FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_ElectricalCircuit)
    .WhereElementIsNotElementType()
    .ToElements();
```

`ElectricalSystem` has first-class typed properties for the data you care about most:

```csharp
var sys = element as ElectricalSystem;
sys.ApparentLoad     // double, in VA — the total load on this circuit
sys.Voltage          // double, in volts
sys.PolesNumber      // int, 1 or 3
sys.CircuitNumber    // string, e.g. "3"
sys.PanelName        // string, e.g. "P-1"
```

These are real C# properties, not parameter lookups. You call them like any property on
any object. No `get_Parameter()` needed.

The breaker rating is different — covered in Concept 2.

---

**Concept 2 — Properties vs. get_Parameter(): why the split exists**

You'll notice that `ApparentLoad` and `Voltage` are typed C# properties on
`ElectricalSystem`, but the breaker rating is not. You have to read it like this:

```csharp
var param = element.get_Parameter(BuiltInParameter.RBS_ELEC_CIRCUIT_RATING_PARAM);
double rating = param?.AsDouble() ?? 0;
```

Why the inconsistency? It's an API design decision Autodesk made over time.

Revit's parameter system is a generic key-value store. Every element in a Revit model
has a bag of parameters — some built-in (keyed by `BuiltInParameter` enum values),
some user-defined. Early in Revit's history, *everything* was in that bag.

Over time, Autodesk "promoted" the most fundamental, frequently-used data points for
key element types to first-class typed properties. This makes them faster to call,
easier to discover in autocomplete, and harder to misuse. `ApparentLoad` was promoted
because every piece of electrical analysis code needs it. The breaker rating was not —
it's more of a design/spec attribute that fewer callers need.

The practical rule: **check the class docs first for a typed property. If there isn't
one, fall back to `get_Parameter(BuiltInParameter.XXX)`.**

The `BuiltInParameter` enum has thousands of entries, prefixed by system:
- `RBS_` = Revit Building Systems (MEP — what you're working with)
- `ROOM_` = room-related
- `STRUCT_` = structural
- etc.

For electrical circuits, the parameters you'll use are all `RBS_ELEC_*`.

---

**Concept 3 — Casting in C#: `element as ElectricalSystem`**

`FilteredElementCollector` always returns `IList<Element>` — the base type. The elements
inside are actually `ElectricalSystem` objects, but the list doesn't know that. To get
access to `ElectricalSystem`'s typed properties, you have to *cast*:

```csharp
var element = collector.First();       // type: Element
var sys = element as ElectricalSystem; // type: ElectricalSystem (or null if wrong type)

if (sys is null) continue; // safety check — skip if cast failed
sys.ApparentLoad;          // now this compiles and works
```

The `as` keyword in C# is a *safe cast* — if the object is not actually an
`ElectricalSystem`, it returns `null` instead of throwing an exception. Always null-check
after `as`. Compare to a *hard cast* `(ElectricalSystem)element`, which throws if wrong.

Use `as` + null check when you're not 100% certain about the type. Use a hard cast only
when you are certain and want the exception as a bug signal.

After reading, you should be able to answer:
- What's the difference between `OST_ElectricalFixtures` and `OST_ElectricalCircuit`?
  You got "different element types" right. The deeper answer is what kind of thing
  each represents: OST_ElectricalFixtures are physical devices placed in the model  (a receptacle on a wall, a light fixture on a ceiling). OST_ElectricalCircuit
  elements are logical connections — the circuit itself, linking a group of
  fixtures to a panel. You can have a fixture with no circuit (un-circuited), or a
  circuit with no fixtures (empty circuit). They model different real-world
  concepts, which is why they're separate categories.
- Why does `sys.ApparentLoad` work but breaker rating needs `get_Parameter()`?
  Your instinct — "almost everyone uses it so it got promoted" — is in the right
  direction, but two corrections:

  - ApparentLoad is a property of ElectricalSystem (the circuit), not of the
  fixture. It's the total load of everything connected to that circuit.
  - The breaker rating is also on ElectricalSystem, not optional or missing — it's
  on every circuit. The difference isn't presence/absence, it's how Autodesk stored   it internally. ApparentLoad was given a typed C# property because it's
  computed/fundamental to the circuit object. The breaker rating was stored in the
  generic parameter bag and never promoted to a first-class property — a historical   API decision, not a design rule about fixtures.

  Both are always there. You just reach them differently.
- What does `as` return if the cast fails?
  Exactly right. as returns null on failure. That's the whole reason you always
  null-check after it.
---

### Step 8.2 — Build the circuit query (Claude Code, teaching mode, ~1.5 hours)

Two things to build in one session:

**Part A — `CircuitQueryHandler.cs`**
A new `IExternalEventHandler` (same pattern as `ElementQueryHandler`) that:
1. Reads a panel name from shared state
2. Queries `OST_ElectricalCircuit` with `FilteredElementCollector`
3. Casts each to `ElectricalSystem`
4. Filters by `sys.PanelName == requestedPanel`
5. Reads `ApparentLoad`, `Voltage`, `PolesNumber`, `CircuitNumber`, and breaker rating via `get_Parameter`
6. Serializes to JSON and signals the `TaskCompletionSource`

**Part B — Command routing in `WebSocketServer.cs`**
Right now `WebSocketServer` ignores the message payload entirely and always queries
fixtures. That needs to become a dispatcher: read the `command` field from the JSON,
route to the right handler and `ExternalEvent`.

The shape of the routing:

```
receive {"command": "get_circuits", "panel": "P-1"}
  → deserialize
  → if command == "get_circuits" → raise circuitEvent
  → if command == "get_elements" → raise elementEvent  (existing)
```

`App.cs` will need to create both handlers and both `ExternalEvent` objects at startup,
and pass both to `WebSocketServer`.

**Part C — `check_breaker_sizing` tool in `main.py`**
A new MCP tool that accepts a `panel` string, sends
`{"command": "get_circuits", "panel": panel}` over WebSocket, and returns the JSON.
Claude will do the breaker sizing math and NEC reasoning on the returned data — the tool
itself is just a data fetch.

Start your session with:

> Before writing any code, explain how I should refactor WebSocketServer to route
> different commands to different ExternalEvent handlers. What's the cleanest pattern,
> and what are the tradeoffs? Don't write code yet.

**You'll know it worked when:** you ask Claude Desktop "check breaker sizing on panel P-1"
and get back a JSON list of circuits with load, voltage, poles, and breaker rating — and
Claude tells you which ones are incorrectly sized.

---

### Step 8.3 — Verify the reasoning (alone, ~20 min)

Pick one circuit from the returned data. Manually calculate:

```
load_amps = ApparentLoad / Voltage        (single phase)
required  = load_amps × 1.25             (NEC 210.20(A) — continuous load rule)
correct_breaker = next standard size ≥ required
```

Standard sizes: 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100...

Check that Claude's reasoning matches your manual calc. If it doesn't, the issue is
either in the data (wrong parameter read) or in the prompt (tool description is misleading
the model). Both are worth understanding before adding write capability.

---

## Step 9 — Agentic breaker fix (write operation)

The goal: when Claude identifies an incorrectly sized breaker, a second MCP tool
`fix_breaker_size(circuit_id, new_rating)` lets Claude propose a fix and — after you
confirm — write it back to the live Revit model.

This is the first time we write to Revit. Writing introduces new constraints.

---

### Step 9.1 — Read, don't build yet (alone, ~30 min)

One new concept: **Transaction**.

---

**Concept — Transaction: Revit's write lock**

Every modification to a Revit model — setting a parameter, creating an element, deleting
one — must happen inside a `Transaction`. Revit enforces this strictly. Writing outside
a transaction throws `InvalidOperationException` immediately.

A transaction is Revit's version of a database transaction. The pattern:

```csharp
using var tx = new Transaction(doc, "Fix breaker size");
tx.Start();
try
{
    // ... make your changes here ...
    tx.Commit();
}
catch
{
    tx.RollBack(); // undo everything if anything went wrong
    throw;
}
```

The string `"Fix breaker size"` is the name that appears in Revit's undo history
(Edit → Undo → "Fix breaker size"). Choose it to be meaningful — the user will see it
when they Ctrl+Z.

Three possible outcomes of a transaction:
- **Commit** — changes are saved to the model. The user can undo with Ctrl+Z.
- **RollBack** — all changes since `Start()` are discarded. Model unchanged.
- **Abandon** (if you forget to Commit/RollBack and the object is disposed) — same as
  RollBack. Revit is defensive here.

**Why transactions must also happen on the UI thread**

Transactions call the Revit API. All Revit API calls must be on the UI thread. So your
`BreakerFixHandler.Execute()` — which already runs on the UI thread via `ExternalEvent`
— is exactly the right place to open a transaction.

The threading model doesn't change. The only thing that changes is that inside
`Execute()`, your code goes from read-only to read-write.

After reading, you should be able to answer:
- What happens if you forget to call `tx.Commit()` or `tx.RollBack()`?
- Why does the transaction also have to be on the UI thread?
- Where does the transaction name appear in Revit?

---

### Step 9.2 — Build the write handler (Claude Code, teaching mode, ~1 hour)

Two things in one session:

**Part A — `BreakerFixHandler.cs`**
A new `IExternalEventHandler` that:
1. Reads `circuit_id` (long) and `new_rating` (double) from shared state
2. Finds the element: `doc.GetElement(new ElementId(circuit_id))`
3. Opens a `Transaction`
4. Sets `RBS_ELEC_CIRCUIT_RATING_PARAM` to `new_rating` via `element.get_Parameter(...).Set(...)`
5. Commits (or rolls back on error)
6. Signals `TaskCompletionSource` with a success/error JSON

**Part B — `fix_breaker_size` tool in `main.py`**
A new MCP tool that accepts `circuit_id: int` and `new_rating: int`, sends
`{"command": "fix_breaker", "circuit_id": ..., "new_rating": ...}` over WebSocket.

The tool description (the docstring Claude reads) should be explicit that this writes
to the model and is not reversible via this tool — only via Revit's undo.

Start your session with:

> Before writing any code, explain how Transaction works in a C# Revit add-in —
> specifically Start, Commit, and RollBack. Where does it have to live relative to our
> ExternalEvent handler? Don't write code yet.

**You'll know it worked when:** you send a raw WebSocket message with
`{"command": "fix_breaker", "circuit_id": <id>, "new_rating": 40}` and the breaker
rating updates in the live Revit model.

---

### Step 9.3 — Wire the agentic loop (Claude Code, ~30 min)

Now both tools exist. This step is about making sure the *interaction design* is right —
not new code, just the tool descriptions and how Claude uses them together.

The correct flow:

```
User: "Check breaker sizing on P-1 and fix anything wrong"

1. Claude calls check_breaker_sizing(panel="P-1")
2. Claude reasons over the data — identifies circuit 3 as undersized
3. Claude explains the problem and proposes the fix — does NOT call fix_breaker_size yet
4. User confirms: "yes, fix it"
5. Claude calls fix_breaker_size(circuit_id=5544, new_rating=40)
6. Claude confirms the fix was applied
```

Step 3 is the key one. Claude must propose before acting. This is controlled by the
tool description — the docstring of `fix_breaker_size` should make clear that this tool
modifies the model and should only be called after user confirmation.

Test the full loop in Claude Desktop. Verify that Claude never calls `fix_breaker_size`
without first stating what it intends to do and waiting for your response.

**You'll know it worked when:** a broken breaker size in your live model gets corrected
through a natural language conversation, and you can Ctrl+Z in Revit to verify the
change was really written.

---

## What success looks like (Steps 8–9)

You type in Claude Desktop:
> "Check all breakers on panel P-1. Fix anything that's wrong."

Claude calls `check_breaker_sizing("P-1")`, reasons about the data using NEC 210.20(A),
identifies circuit 3 as undersized (30A load, 20A breaker, needs 40A), tells you what
it found, asks for confirmation, and — after you say yes — calls `fix_breaker_size` to
update the model.

You open Revit, check circuit 3 on P-1, and see the breaker is now 40A.
Ctrl+Z in Revit undoes the change. That's the full agentic loop: read → reason →
propose → confirm → write → verifiable in the model.