# Step 7 — Building the pyRevit Bridge

This is the plan for connecting your MCP server to a live Revit model using pyRevit.
Do not start until you have a working `query_elements` tool returning fake data (Step 6 done).

---

## Where to learn pyRevit before coding

Do these in order, alone, before any Claude Code sessions:

1. **pyRevit official docs** — https://pyrevitlabs.notion.site/
   Read the "Getting Started" and "Anatomy of a pyRevit extension" sections.
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

**Decided: geometric clashes, electrical-vs-electrical included.**

Not just MEP vs. structure — conduit running into conduit is a real daily problem.
Revit's built-in interference check supports same-category clashes; we'll use that.

Relevant API: `ElementIntersectsElementFilter` lets you take one element and find
everything in the model that geometrically intersects it. Run it across all conduit,
cable tray, and electrical equipment — not just cross-category.

Start a session with: "Before writing code, explain how ElementIntersectsElementFilter
works, what its performance characteristics are on a large model, and whether Revit's
built-in InterferenceCheckingService is a better entry point than rolling our own
collector loop." Then decide.

---

## What success looks like

You type in Claude Desktop:
> "Show me all HVAC loads on panel MP-1"

Claude calls `query_elements`, your MCP server calls pyRevit Routes, pyRevit runs a
`FilteredElementCollector` against the live model, and Claude gets back real element
data from the open `.rvt` file.

That's the full stack working end-to-end with real data.
