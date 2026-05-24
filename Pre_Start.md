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

1. Forget tx.Commit() or tx.RollBack()

  Half right. If you forget Commit(), yes — the change won't persist. But here's the   more accurate picture: if the Transaction object gets disposed (goes out of
  scope) without a Commit() or RollBack(), Revit automatically abandons it, which  behaves the same as RollBack(). Revit is deliberately defensive — it won't leave a   half-open transaction hanging.

  RollBack() isn't for Ctrl+Z — that's a separate concept. RollBack() is what you
  call inside your own code when something goes wrong during the write, to undo the
  partial changes before returning an error. Ctrl+Z is what the user does after a
  committed transaction to undo a complete, successful change.

  The two are independent:
  - RollBack() = "my code detected a problem, discard everything" (user never sees
  it)
  - Ctrl+Z = "the user changed their mind after a successful commit"

  2. Transaction must be on the UI thread

  Correct. All Revit API calls — read or write — are restricted to the UI thread. A
  transaction is a Revit API operation. Same rule, no exception.

  3. Where the transaction name appears

  Not at the moment you start the transaction — after it's committed. It shows up in   Revit's undo history: when the user presses Ctrl+Z, the tooltip or undo menu
  shows the name you passed to new Transaction(doc, "Fix breaker size"). That's how
  the user knows what they're undoing. If you name it something vague like
  "Transaction1", the undo history is useless. Name it to describe what actually
  changed.

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
Recap:
  - BreakerFixHandler.cs — validates the element exists and is an ElectricalSystem,
  checks the parameter isn't read-only, then opens a Transaction, sets the rating
  with ConvertToInternalUnits, and commits. The using inside try means if anything
  throws after Start(), the transaction is auto-abandoned before the catch runs —
  the catch only needs to report the error.
  - main.py — the fix_breaker_size docstring carries the entire interaction
  contract: what it writes, that it's immediate and permanent, what Ctrl+Z shows,
  and that confirmation must come before calling it.
  - App.cs / WebSocketServer.cs — same 4-file wiring pattern as every other tool.
  - "fix_breaker" switch arm — extracts both circuit_id (as Int64) and new_rating
  (as Double) from the incoming JSON before handing off to the handler.

  Question you should be able to answer: Why is the Transaction declared with using
  inside the try block rather than outside it — and what exactly happens to the
  transaction if param.Set() throws an exception?
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
 ##Start here:
 Step 9.3 is different from all the previous steps — there's no code to write. Both
   tools exist. This step is entirely about verifying that the interaction design
  works correctly in practice.

  The key thing to understand first:

  There is no code that prevents Claude from calling fix_breaker_size immediately  without asking you. No lock, no guard, no gate in the C# or Python layer. The only   enforcement mechanism is the tool docstring — what Claude reads when it decides
  how to use the tool. This is a deliberate design choice in MCP: the LLM's behavior   is shaped by the tool description, not by code constraints.

  The docstring we wrote says:

  ▎ "Only call this tool after explaining the proposed change to the user and
  ▎ receiving explicit confirmation."

  That instruction to Claude is the entire safety mechanism. If it works, Claude
  will always propose before acting. If the docstring were vague, Claude might act
  immediately.

  ---
  What you need to do for 9.3:

  First, rebuild and restart everything (the C# changes from Step 9.2 aren't in
  Revit yet):

  dotnet build revit_addin\RevitElecMcp\RevitElecMcp.csproj

  Then restart Revit (with a model open) and restart Claude Desktop.

  Test the full loop with this prompt in Claude Desktop:

  ▎ "Check breaker sizing on [your panel name] and fix anything that's wrong."

  Watch for this exact sequence — Claude should:
  1. Call check_breaker_sizing → get circuit data
  2. Reason over it, identify which circuits are undersized
  3. Stop and explain what it found and what it proposes — without writing anything
  yet
  4. Wait for you to say yes
  5. Only then call fix_breaker_size

  Then verify it actually wrote to the model:
  - Open the panel schedule in Revit — the breaker rating should be updated
  - Press Ctrl+Z in Revit — you should see "Undo: Fix breaker size" and the old
  rating should come back

  You'll know it worked when the Ctrl+Z in Revit confirms the change was really
  written and is reversible — not just that Claude said it was done.

  ---
  If Claude skips the confirmation step and calls fix_breaker_size immediately, the
  fix is to strengthen the docstring — not add code. Come back and we can revise the   wording. That's a prompt engineering problem, not a code problem.
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

---

## Step 10 — Structured NEC compliance checks

The goal: a new MCP tool `check_code_compliance(panel)` that applies NEC rules as
explicit Python logic and returns a circuit-by-circuit compliance report. Claude reads
the report and explains it — but the pass/fail determination is made by code, not by
the model interpreting a docstring.

This is a deliberate design shift. Right now, the NEC 210.20(A) rule lives in the
`check_breaker_sizing` docstring — Claude reads it and applies it in-context. That
works, but it has a problem: the same input might get slightly different reasoning on
different runs. For compliance work, the determination of "this breaker is undersized"
should be deterministic and auditable — the same input must always produce the same
output, and you should be able to read the code to see exactly which rule was applied.

No NEC text is stored or embedded. The rules are encoded directly as Python logic,
which avoids copyright questions and is more reliable for the fixed numerical thresholds
we actually need.

---

### Step 10.1 — Read, don't build yet (alone, ~30 min)

Two concepts before any code.

---

**Concept 1 — Rules as code vs. rules as prompts: why it matters**

The current approach embeds the NEC rule in the `check_breaker_sizing` docstring:

```
required_rating = next standard size >= load_amps * 1.25
```

Claude reads that and applies it. It works. But consider what you're relying on:
- Claude must parse the docstring correctly every time
- Claude must apply the arithmetic correctly
- If Claude makes an error, there's no way to catch it before the output reaches you
- The "rule" isn't testable — you can't write a unit test against a docstring

Move that same logic into Python:

```python
def required_breaker(load_va: float, voltage: float, poles: int) -> int:
    load_amps = load_va / voltage if poles == 1 else load_va / (voltage * 1.732)
    continuous = load_amps * 1.25  # NEC 210.20(A)
    return next_standard_size(continuous)
```

Now the logic is deterministic, testable, and readable. Claude's job changes: instead
of doing the math, it reads a structured compliance report and explains what it means.

This is a general principle in AI system design: **move deterministic logic into code;
leave judgment and explanation to the model.**

---

**Concept 2 — NEC 240.6(A): standard breaker sizes**

NEC 240.6(A) lists the standard ampere ratings for fuses and fixed-trip circuit
breakers. These are not arbitrary — they're what manufacturers actually produce.
A "37A breaker" does not exist. If your load requires 46.25A, the correct breaker is
50A (next standard size up).

The standard sizes you'll need:

```
15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200
```

Two failure modes to check against this list:
- **Undersized**: `breaker_rating < required` — dangerous; the circuit can carry more
  current than the breaker protects against
- **Non-standard**: `breaker_rating not in STANDARD_SIZES` — shouldn't exist in a
  real model but worth flagging as a data quality issue

After reading, you should be able to answer:
- Why is it better to encode the 210.20(A) formula in Python rather than leave it in
  the docstring?

  The docstring approach works but it's non-deterministic — Claude applies the rule,
  and LLM output can vary between runs. Moving it to Python means the same load always
  produces the same required breaker rating. You can write a test against that function.
  You can read it in a code review. The model's role becomes explaining the result, not
  computing it.

- What does NEC 240.6(A) govern, and why does it constrain which breaker sizes are valid?

  240.6(A) lists the standard ampere ratings for overcurrent protective devices — the
  sizes that manufacturers actually produce. Specifying a non-standard size (e.g., 37A)
  isn't meaningful because no such device exists. The list constrains the output of
  `next_standard_size()` to values that can actually be purchased and installed.

---

### Step 10.2 — Build `nec_rules.py` (Claude Code, teaching mode, ~45 min)

One new file: pure Python, no Revit, no MCP, no WebSocket. It takes circuit data as
dicts and returns compliance results as dicts. Nothing in it touches the rest of the
system — that's the point.

> Before writing any code, explain the design: I want to encode NEC 210.20(A) and
> NEC 240.6(A) as pure Python functions that take a circuit dict as input and return
> a compliance result. What should the return dict contain to be most useful to Claude
> when it reads the report? Don't write code yet.

What you're building:

**`nec_rules.py`**

The key function is `check_circuit(circuit: dict) -> dict`. It handles three cases:

1. **Spare circuits** (`is_spare == True`) — skip NEC sizing, return `"status": "spare"`
2. **Motor / HVAC loads** — do not apply the 125% rule (NEC 430/440 governs instead),
   return `"status": "manual_review"` with the NEC reference
3. **Everything else** — apply NEC 210.20(A), compare `required_rating` to
   `breaker_rating`, return `"status": "pass"` or `"fail"`

Every result dict must include a `nec_ref` field (e.g. `"NEC 210.20(A)"`) so the
report is self-documenting — Claude cites the article without having to look it up.

The `next_standard_size(amps: float) -> int` helper finds the smallest value in
`STANDARD_SIZES` that is greater than or equal to `amps`. Watch the edge case: if
`amps` is exactly 20.0, the result must be 20, not 25.

**You'll know it worked when:** you call

```python
check_circuit({
    "apparent_load_va": 1800, "voltage": 120, "poles": 1,
    "breaker_rating": 15, "is_spare": False, "load_classification": "Lighting",
    "circuit_number": "3", "panel": "P-1", "id": 5544
})
```

and get back `{"status": "fail", "required_rating": 20, "actual_rating": 15,
"nec_ref": "NEC 210.20(A)", ...}`.

---

### Step 10.3 — Build the `check_code_compliance` tool (Claude Code, ~30 min)

Wire `nec_rules.py` into a new MCP tool. No new C# required — this reuses the
existing `get_circuits` WebSocket command already implemented in Step 8.

> Before writing any code: check_code_compliance needs to fetch live circuit data
> from Revit and then apply the Python rules from nec_rules.py. Should it reuse the
> _send() helper directly, or call check_breaker_sizing internally? What are the
> tradeoffs? Don't write code yet.

What you're building in `main.py`:

**`check_code_compliance(panel: str)`**

1. Sends `{"command": "get_circuits", "panel": panel}` via `_send()` — same command
   as `check_breaker_sizing`, same C# handler, no new wiring needed
2. Parses the JSON into a list of circuit dicts
3. Calls `nec_rules.check_circuit()` on each
4. Returns the full compliance report as JSON

The docstring should tell Claude that this tool returns a structured pass/fail report
and that Claude's job is to summarize and explain — not to redo the arithmetic.

**You'll know it worked when:** you ask Claude Desktop "check code compliance for
panel P-1" and get back a per-circuit pass/fail list with NEC article citations —
and Claude's explanation contains no arithmetic, only interpretation of the report.

---

### Step 10.4 — Verify the results (alone, ~20 min)

Pick two circuits from your panel — one that should pass, one that should fail.
Manually compute the required breaker for the failing one:

```
load_amps = apparent_load_va / voltage          (single-phase)
           apparent_load_va / (voltage × 1.732) (three-phase)
required  = load_amps × 1.25                    (NEC 210.20(A))
breaker   = next standard size ≥ required       (NEC 240.6(A))
```

Confirm the tool returns the same answer. If it doesn't, the bug is in `nec_rules.py`
— readable code you can step through, not a prompt you have to re-word.

Test one edge case: a circuit where `load_amps × 1.25` lands exactly on a standard
size (e.g., exactly 20.0A). The result must be 20A, not 25A — "≥" includes equal.

**You'll know it worked when:** the tool output matches your manual calculation on
every circuit, and Claude's explanation cites the NEC article without performing any
arithmetic itself.

---

## What success looks like (Step 10)

You type in Claude Desktop:
> "Run a code compliance check on panel P-1."

Claude calls `check_code_compliance("P-1")`. Python applies NEC 210.20(A) and
240.6(A) to every circuit. Claude receives a structured report — status, required
rating, actual rating, and NEC reference per circuit — and explains what it means in
plain language, identifying which circuits are undersized and what the correct breaker
size would be.

The arithmetic was done by code. The explanation was done by Claude. Each is doing
what it's best at.

---

## Step 11 — Choose one: Clash Detection or Schedule Export

This step is a branch. Read both options below, then pick one. They are approximately
equal in difficulty. The choice should be driven by what you want to *learn* from the
Revit API, not by what's more useful — both are useful.

---

### Option A — Clash Detection

**Goal:** a new MCP tool `detect_clashes(category_a, category_b)` that finds pairs of
elements from two Revit categories whose geometry physically intersects. The typical
electrical use case: check conduit against structural framing to catch routing conflicts
before construction.

**What the agent gains:** instead of you manually running Revit's Interference Check and
reading a report, Claude can ask the model directly — "are there any clashes between
electrical conduit and structural beams?" — get back a list of element ID pairs, look up
each element's name and location, and describe the conflicts in plain language.

---

#### Step 11A.1 — Read, don't build yet (alone, ~45 min)

Two new concepts.

---

**Concept 1 — `Document.CheckInterference()`: the built-in clash engine**

Revit has a built-in interference checker — the same engine that Navisworks uses when
connected to a live model. The Revit API exposes it directly:

```csharp
var options = new InterferenceCheckOptions();
var result  = doc.CheckInterference(elementsA, elementsB, options);
```

`elementsA` and `elementsB` are `ICollection<ElementId>` — you collect each set with
`FilteredElementCollector` first, then pass the ID lists. The result is an
`InterferenceCheckResult` object. You iterate it with `GetInterferenceCheckResultIterator()`;
each item exposes `EntityIdA` and `EntityIdB` — the two elements that clash.

Important: this is a *pairwise* check. Every element in set A is checked against every
element in set B. Checking A against A (e.g., conduit against conduit) requires passing
the same collector twice — Revit won't deduplicate pairs for you.

This lives in `Autodesk.Revit.DB` — no new namespace import beyond what you already use.

---

**Concept 2 — Geometry vs. bounding box: why `CheckInterference` is the right tool**

You might wonder: couldn't I just compare bounding boxes? If two bounding boxes overlap,
the elements might clash. The answer is: bounding boxes are fast but produce many false
positives. A vertical conduit and a horizontal beam might have overlapping bounding boxes
but never actually touch.

`Document.CheckInterference()` uses actual solid geometry — it checks whether the 3D
solids of two elements truly intersect. This is slower (especially on large models) but
accurate. The same reason Navisworks uses it.

The alternative — extracting `Solid` objects manually and calling
`BooleanOperationsUtils.ExecuteBooleanOperation()` — gives you the same accuracy but
requires you to handle geometry extraction yourself (some elements have multiple solids,
some have no solid geometry at all). `CheckInterference` handles all of that for you.

**Known footgun:** the 4096-byte receive buffer in `WebSocketServer.cs` (line 78).
A complex model could return hundreds of clash pairs. This is the step where that
buffer limit will actually bite you. Before testing on a real model with many elements,
increase `buffer` to at least 65536 — or implement chunked reads.

After reading, you should be able to answer:
- Why is `CheckInterference` more accurate than a bounding box comparison?
- What do `EntityIdA` and `EntityIdB` tell you, and what don't they tell you?
  (Hint: you get IDs, not locations or names — what additional API call would you need
  to turn an ID into something a user can act on?)

---

#### Step 11A.2 — Design the tool interface (alone, ~20 min)

Before any code, decide what the tool's parameters should be. This is a design question,
not a code question — and getting it wrong means the tool is awkward to call.

The tool needs to know which two categories of elements to check against each other.
Three possible approaches:

**A — Fixed categories, hardcoded.**
`detect_clashes()` always checks `OST_Conduits` against `OST_StructuralFraming`.
Simple, but useless for any other combination.

**B — String parameters for category names.**
`detect_clashes(category_a: str, category_b: str)` where the caller passes Revit
category names like `"OST_Conduits"` and `"OST_StructuralFraming"`.
Flexible, but requires Claude (or the user) to know exact `BuiltInCategory` enum names.

**C — Curated enum-style strings.**
`detect_clashes(category_a: str, category_b: str)` where the tool description lists
the valid values: `"conduit"`, `"cable_tray"`, `"structural_framing"`, `"duct"`, `"pipe"`.
The C# handler maps these friendly names to `BuiltInCategory` values internally.
Claude can pick from the list; the user doesn't need to know Revit internals.

Approach C is the right one for MCP tools that an LLM calls. The docstring is the
interface contract — it should make the right call obvious and wrong calls impossible.

Write out the docstring for the Python tool before your Claude Code session. The session
goes better when you know exactly what you want the tool to say.

---

#### Step 11A.3 — Build it (Claude Code, teaching mode, ~2 hours)

Four files to touch, same pattern as every other tool:

1. **`ClashDetectionHandler.cs`** — new `IExternalEventHandler`. Reads `CategoryA` and
   `CategoryB` from shared state, runs two `FilteredElementCollector` queries, calls
   `doc.CheckInterference()`, iterates results, returns a JSON array of
   `{element_id_a, name_a, element_id_b, name_b}` pairs. Resolve element names inside
   `Execute()` while still on the UI thread — don't return bare IDs and force the Python
   side to do another round-trip for names.

2. **`App.cs`** — construct handler + `ExternalEvent.Create()` in `OnStartup`.

3. **`WebSocketServer.cs`** — new `HandleClashDetectionAsync()` method, new arm in the
   `command` switch for `"detect_clashes"`.

4. **`main.py`** — new `@mcp.tool() async def detect_clashes(category_a: str, category_b: str)`
   that calls `_send({"command": "detect_clashes", "category_a": ..., "category_b": ...})`.

Start your session with:

> Before writing any code, explain how `Document.CheckInterference()` works in the
> Revit API. What are the inputs, what does the result look like, and how do I iterate
> it? I'm building a handler that takes two element categories, finds clashes, and returns
> JSON. Don't write code yet.

**You'll know it worked when:** you open a model where you know two elements clash (or
place two overlapping elements in a test model), call the tool from Claude Desktop, and
get back a JSON list that includes those element IDs and names.

---

### Option B — Schedule Export

**Goal:** a new MCP tool `export_schedule(schedule_name)` that reads an existing
ViewSchedule from the Revit model and returns its rows as structured JSON. Practical
targets: panel schedules, equipment schedules, lighting fixture schedules.

**What the agent gains:** structured tabular data the model can reason over without
a human reading a PDF. "Summarize the equipment schedule for the electrical room" →
Claude gets a JSON table of panel names, voltages, ampacities, and locations → can
identify missing data, verify ratings match specs, or draft a summary report.

**Important distinction from `check_breaker_compliance`:** that tool fetches circuit
data via WebSocket and applies Python rules. Schedule Export reads a ViewSchedule that
*already exists in the Revit model* — whatever the engineer has built and formatted
as a schedule view. The data is whatever Revit put in that schedule. The rules are not
applied by this tool; the agent reasons over the raw table.

---

#### Step 11B.1 — Read, don't build yet (alone, ~45 min)

Two new concepts.

---

**Concept 1 — ViewSchedule: a View that is a table**

In Revit's data model, a "view" is not just a floor plan or 3D view — schedules are
also views. `ViewSchedule` is a subclass of `View`, which is a subclass of `Element`.
That means `FilteredElementCollector` can find them:

```csharp
new FilteredElementCollector(doc)
    .OfClass(typeof(ViewSchedule))
    .Cast<ViewSchedule>()
    .ToList();
```

Note `OfClass(typeof(ViewSchedule))` instead of `OfCategory(...)`. Use `OfClass` when
you want all instances of a specific .NET type; use `OfCategory` when you want elements
belonging to a Revit category. These are different filters — don't mix them up.

Once you have a `ViewSchedule`, the table data lives in:

```csharp
var tableData    = schedule.GetTableData();
var sectionData  = tableData.GetSectionData(SectionType.Body);
int rowCount     = sectionData.NumberOfRows;
int colCount     = sectionData.NumberOfColumns;

for (int r = 0; r < rowCount; r++)
    for (int c = 0; c < colCount; c++)
        sectionData.GetCellText(r, c); // always returns a string
```

`GetCellText()` always returns a `string` — even if the underlying parameter is a
number. You get formatted text, not raw values. That means `"20 A"` not `20.0`.
This is a deliberate Revit design: the schedule is a presentation view, not a data
export API. Work with it, don't fight it — the agent can parse formatted strings.

---

**Concept 2 — `SectionType`: headers, body, and footers are separate**

A schedule has multiple sections: column headers, the data body, optional group headers,
and optional footers/totals. `SectionType` controls which part you read:

- `SectionType.Header` — the title row(s) at the top (schedule name, column names)
- `SectionType.Body` — the data rows
- `SectionType.Footer` — totals rows at the bottom (if the schedule has them)

You almost always want `SectionType.Body` for data export. But the column names live
in `SectionType.Header` — if you want to return the table with named columns rather
than positional indices, read the header section first to build a column name list,
then read the body.

Practical approach for the MCP tool: read header row 0 (column names) + all body rows,
return `{"columns": [...], "rows": [[...], [...], ...]}`. The agent can then refer to
columns by name when reasoning.

**Known footgun:** `GetCellText()` can throw if the row/column index is out of range —
unlike most collection accesses in .NET, it doesn't return an empty string. Always guard
with the `NumberOfRows` / `NumberOfColumns` bounds.

After reading, you should be able to answer:
- Why do you use `OfClass(typeof(ViewSchedule))` instead of `OfCategory()` to find
  schedules?
- `GetCellText()` always returns a string. If a cell contains a load of "1800 VA", what
  does that mean for downstream code that wants to do arithmetic on it? How would you
  handle this in `nec_rules.py` if you wanted to apply rules to schedule data?

---

#### Step 11B.2 — Design the tool interface (alone, ~15 min)

The tool needs to identify which schedule to export. Two approaches:

**A — By name:** `export_schedule(schedule_name: str)`. Simple. Requires the caller to
know the exact schedule name as it appears in Revit. Add a companion tool
`list_schedules()` (trivial — one `FilteredElementCollector` call, returns name + id
pairs) so the agent can discover schedule names first.

**B — By ID:** `export_schedule(schedule_id: int)`. Caller passes the ElementId.
Precise, but harder for a human to use interactively.

Approach A with a `list_schedules()` companion is the right pattern — same as how
`list_panels()` → `check_breaker_compliance(panel)` works. The discovery step makes
the workflow self-contained.

---

#### Step 11B.3 — Build it (Claude Code, teaching mode, ~2 hours)

Six files to touch (two new tools = two handlers = two WebSocket arms):

1. **`ScheduleListHandler.cs`** — new `IExternalEventHandler` for `"list_schedules"`.
   `OfClass(typeof(ViewSchedule))` collector, return `{id, name}` per schedule.

2. **`ScheduleExportHandler.cs`** — new `IExternalEventHandler` for `"export_schedule"`.
   Reads `ScheduleName` from shared state, finds the matching `ViewSchedule`, reads
   header row (column names) and all body rows via `GetCellText()`, returns
   `{"schedule_name": ..., "columns": [...], "rows": [[...], ...]}`.

3. **`App.cs`** — construct both handlers + events in `OnStartup`.

4. **`WebSocketServer.cs`** — two new `Handle*Async()` methods, two new switch arms
   (`"list_schedules"` and `"export_schedule"`).

5. **`main.py`** — two new `@mcp.tool()` functions:
   `list_schedules()` and `export_schedule(schedule_name: str)`.

Start your session with:

> Before writing any code, explain how ViewSchedule works in the Revit API —
> specifically how to find schedules with FilteredElementCollector, how to read cell
> data via GetTableData and GetSectionData, and what SectionType controls. I want to
> understand the shape before touching code. Don't write code yet.

**You'll know it worked when:** you call `list_schedules()` from Claude Desktop, get
back the names of real schedules in your model, then call `export_schedule("Panel P-1
Schedule")` and get back a JSON table with column names and row data matching what you
see in Revit's schedule view.

---

### Choosing between A and B

| | Clash Detection | Schedule Export |
|---|---|---|
| New Revit API concepts | `CheckInterference`, solid geometry | `ViewSchedule`, `TableData`, `SectionType` |
| New architecture pieces | 1 handler, 1 event, 1 tool | 2 handlers, 2 events, 2 tools |
| Buffer risk | High (many clashes = large response) | Medium (large schedules possible) |
| Extends existing patterns | No — geometry is a new domain | Yes — `OfClass` instead of `OfCategory` |
| What the agent can do with it | Detect routing conflicts, describe clash locations | Reason over tabular data, flag missing fields, draft summaries |
| Electrical relevance | Coordination (conduit vs. structure/HVAC) | Documentation and review |

Pick clash detection if you want to go deeper into Revit's geometry layer.
Pick schedule export if you want to extend the data-extraction pattern into a new
element type and get a tool that's immediately useful for documentation workflows.