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