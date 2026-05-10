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
Step 7 — Only now, start the Revit bridge. This is where the C# / pyRevit decision lives, and it deserves its own session. Don't blur it into MCP work. 

## Where to learn pyRevit before coding

Do these in order, alone, before any Claude Code sessions:

1. **pyRevit official docs** — https://docs.pyrevitlabs.io/
   The Notion site (pyrevitlabs.notion.site) is outdated — use the new docs site.
   Read these two pages:
   - Architecture overview: https://docs.pyrevitlabs.io/architecture/
   - Extension anatomy (bundles, tabs, panels): https://pyrevit1.readthedocs.io/en/latest/creatingexts.html
     (older version but clearest explanation of the `.pushbutton` bundle structure)
   You need to understand: what an extension is, what a script button is, and how
   pyRevit loads Python scripts into Revit's process.

2. **Learn Revit API (Python)** — https://www.youtube.com/@LearnRevitAPI
   Erik Frits's YouTube channel. Watch the pyRevit playlist first. He explains
   `FilteredElementCollector` — the primary way to query elements — better than the docs.

3. **Revit API docs** — https://www.revitapidocs.com/
   Reference only, not for reading linearly. Use it to look up specific classes
   (e.g., `ElectricalSystem`, `FamilyInstance`, `BuiltInParameter`) as you need them.

4. **pyRevit GitHub** — https://github.com/pyrevitlabs/pyRevit
   When something doesn't work, read the source. The `pyrevit.routes` module
   (what we'll use for the HTTP bridge) is in `pyrevitlib/pyrevit/routes/`.

---

## The concrete steps, in order

### Step 7.1 — Install pyRevit (alone, ~30 min)

Download and install from https://github.com/pyrevitlabs/pyRevit/releases.
Open Revit. You should see a pyRevit tab in the ribbon.
Verify by running any built-in pyRevit tool (e.g., the "Select Similar" button).

---

### Step 7.2 — Write your first pyRevit script (alone, ~1 hour)

Before building the bridge, you need to know how pyRevit scripts work.

Create a minimal pyRevit extension that runs a script inside Revit and prints something
to the pyRevit output window. No bridge yet — just confirm that:
- Your Python code runs inside Revit's process
- You can access `doc` (the current open document)
- You can print element counts from a `FilteredElementCollector`

Use the pyRevit docs + Erik's videos. Do not use Claude Code for this step.
The goal: you should be able to write a script that prints how many electrical
fixtures are in the open model.

---

### Step 7.3 — Understand pyRevit Routes (Claude Code, teaching mode)

This is the key concept for the bridge. pyRevit has a built-in HTTP server called
**Routes** that lets you define URL endpoints inside a pyRevit script. Your MCP server
calls `localhost:PORT/your-endpoint`, pyRevit handles the request using the Revit API,
and returns JSON.

Start your session with:

> Before writing any code, explain how pyRevit Routes works. What is it, how do I
> define an endpoint, what port does it run on, and what are the limitations?
> Don't write code yet.

Read the explanation. Then say go and build a minimal Routes endpoint that returns
a hardcoded JSON string — no real Revit data yet, just proving the HTTP round-trip works.

---

### Step 7.4 — Connect the MCP server to pyRevit Routes (Claude Code)

Replace the `FAKE_ELEMENTS` list in `main.py` with an HTTP call to your pyRevit endpoint.
`query_elements` should now:
1. Build a query URL with the filter parameters
2. Call `localhost:PORT/elements?voltage=120&...`
3. Return whatever pyRevit sends back

The fake data lives in pyRevit temporarily — the MCP server just passes through.
Test it end-to-end: ask Claude Desktop a question, watch it call your tool, watch the
HTTP request hit pyRevit, see real (or still fake) data come back.

---

### Step 7.5 — Replace fake data with real Revit API calls (Claude Code)

Now swap the hardcoded list in your pyRevit script for a real `FilteredElementCollector`
query. For electrical elements, you'll be looking at:
- `BuiltInCategory.OST_ElectricalFixtures`
- `BuiltInCategory.OST_ElectricalEquipment`
- `ElectricalSystem` for circuit/panel relationships
- `BuiltInParameter` for voltage, load classification, etc.

Start with: return all electrical fixtures in the model, with their name and element ID.
Add parameters one at a time. Verify each against what you can see in Revit manually.

---

### Step 7.6 — Clash detection (separate session, after 7.5 is solid)

Decide what "clash detection" means for your use case before writing any code.
Two likely options:

**Option A — Geometric clashes** (conduit/cable tray intersecting structure)
Uses `FilteredElementCollector` + `ElementIntersectsSolidFilter` or
`ElementIntersectsElementFilter`. More complex, requires understanding of Revit's
geometric API.

**Option B — Electrical rule violations** (overcrowded panels, missing circuits,
load imbalance)
Uses parameter reads and logic — much simpler, more immediately useful for electrical
coordination work.

Start a session with: "Before writing code, explain the tradeoff between geometric
clash detection and electrical rule checking in Revit. What API classes are involved
in each?" Then decide.

---

## What success looks like

You type in Claude Desktop:
> "Show me all HVAC loads on panel MP-1"

Claude calls `query_elements`, your MCP server calls pyRevit Routes, pyRevit runs a
`FilteredElementCollector` against the live model, and Claude gets back real element
data from the open `.rvt` file.

That's the full stack working end-to-end with real data.