# A learning-first workflow
1. Plan before you code. Start each session with /plan mode (or just ask Claude to produce a plan first). For the MCP server, your first plan might be: "Walk me through the architecture of an MCP server end-to-end before we write anything — what are the components, what does the protocol actually look like on the wire, and what's the minimum viable skeleton?" Read the plan, push back on anything that feels handwavy, then let it code.
2. Build in vertical slices, not horizontal layers. Don't have Claude scaffold the whole project. Do one tool end-to-end first — e.g., query_model_elements — through the full stack: MCP handler → Revit API call → response serialization → testing it in Claude Desktop. You'll understand the whole loop before adding breadth. This matches your playbook's May 1 task perfectly.
3. Use the "explain this back to me" pattern. After Claude writes a chunk, before moving on, type: "Don't write code. Explain to me what just happened, what I'd need to change to also support X, and what would break if I removed Y." If you can't follow the explanation, you don't understand the code well enough to defend it in an interview.
4. Rebuild the hard parts yourself. This is the Karpathy pattern your planner already uses (watch → rewatch → rebuild from scratch). Apply it to MCP too: after Claude builds the server scaffold and first tool with you, close the file, open a new one, and rebuild the MCP message handler from a blank slate. Use Claude as a tutor when stuck, not a code generator. This is the difference between "I built a Revit MCP server" and "I can whiteboard the MCP protocol in an interview."
5. Ask for the gnarly version, not the clean version. When Claude finishes something, ask: "What did you simplify or skip? What would a production version of this need that we don't have? What's the most likely failure mode?" This trains your intuition for the eval/observability/failure-mode thinking that the playbook flags as the hardest current AI problem.
6. Keep a learning journal. One markdown file in the repo, Learning_Notes.md, ungitignored. After each session, two-minute writeup: what I built, what I learned, what I didn't understand. This becomes the source material for your blog post in Week 2 and your "tell me about this project" interview answer.
# Step 1 — Environment Setup: Learning Notes

Notes compiled from working through the environment setup for the Revit MCP project. Covers Python tooling, Windows shells, and `uv` package management.

---

## 1. CMD vs PowerShell on Windows

### The short version

- **Command Prompt (`cmd.exe`)** — old Windows shell, dating back to MS-DOS conventions. Kept for backwards compatibility, not actively developed.
- **PowerShell** — modern Windows shell, introduced 2006, continuously developed. Default on Windows 10/11. What Microsoft and modern tutorials assume.

**Use PowerShell.** Strictly more capable; tutorials are written for it.

### Why they're actually different

- **`cmd` passes text around.** Every command's output is a string. To process output, you parse the text. Same model as Unix shells (bash, zsh).
- **PowerShell passes objects around.** Commands return structured objects with properties. Example: `Get-Process` returns process objects with `.Name`, `.CPU`, `.Memory` — no string parsing needed.

This sounds abstract until it bites you. Filtering files by size in `cmd` requires parsing `dir` output; in PowerShell it's `Get-ChildItem | Where-Object { $_.Length -gt 1MB }`.

### Practical command differences

| Task | cmd | PowerShell |
|---|---|---|
| List files | `dir` | `ls` or `Get-ChildItem` |
| Change directory | `cd` | `cd` (same) |
| Show file contents | `type file.txt` | `cat file.txt` or `Get-Content` |
| Copy file | `copy a.txt b.txt` | `cp a.txt b.txt` or `Copy-Item` |
| Delete file | `del file.txt` | `rm file.txt` or `Remove-Item` |
| Print text | `echo hello` | `echo hello` (same) |
| Set env variable | `set FOO=bar` | `$env:FOO = "bar"` |
| Run a script | `script.bat` | `.\script.ps1` |

PowerShell aliases many Unix-style commands (`ls`, `cat`, `rm`, `cp`) — deliberate, to make Unix tutorials work.

### Other key differences

- **Quoting.** PowerShell needs quotes around things with brackets (`"mcp[cli]"`); `cmd` is more tolerant.
- **Line continuation.** `cmd` uses `^`; PowerShell uses backtick `` ` ``.
- **Env variables.** `cmd` uses `%VAR%`; PowerShell uses `$env:VAR`.
- **Script files.** `cmd` runs `.bat`/`.cmd`; PowerShell runs `.ps1`. Not interchangeable.
- **Execution policy.** PowerShell blocks unsigned scripts by default. That's why `uv`'s install command needs `-ExecutionPolicy ByPass`. `cmd` has no equivalent.

### Why this matters for MCP/Python work

1. Modern Python and AI tooling assumes PowerShell or a Unix-like shell.
2. `uv` and similar tools target PowerShell on Windows.
3. Eventually you'll want a Unix-like environment (PowerShell, Git Bash, or WSL). PowerShell is the lowest-friction first step.

### What about WSL?

**WSL (Windows Subsystem for Linux)** = real Ubuntu running inside Windows. Many serious Python devs on Windows use it.

For now, **don't use WSL** because:
- Revit work has to happen on Windows native (Revit doesn't run in Linux).
- Adds another moving part while learning MCP and Revit API.
- PowerShell is good enough for the Python side.

Revisit WSL in 2-3 months once the rest is stable.

### Recommendation

- Use **PowerShell**.
- Install **Windows Terminal** from the Microsoft Store as the host (free, made by Microsoft, much better than the default PowerShell window — tabs, better fonts, copy/paste).
- The shell (PowerShell) and the terminal (the window) are separate things.

---

## 2. Where to install `uv`: anywhere

### Short answer

`uv` is a **system-wide tool**, not a project tool. Installed once into a user-level location (`C:\Users\<you>\.local\bin\uv.exe`), available from anywhere. Run the install command from any directory.

### The mental model that matters

**System-wide / user-level tools** are installed once and available everywhere. Commands you run *on* projects.
- Examples: `uv`, `git`, `python`, `node`, `code` (VS Code launcher).
- Install from anywhere.

**Project-level dependencies** are installed *into* a specific project, only exist there.
- Examples: the `mcp` library, `pydantic`, anything you `uv add`.
- Install from inside the project directory.

### The rule

| When you're... | Where to run it |
|---|---|
| Installing `uv` itself | Anywhere — it's a tool |
| Installing `git` | Anywhere — it's a tool |
| Running `uv init` | Inside your project directory |
| Running `uv add <package>` | Inside your project directory |
| Running `uv run <command>` | Inside your project directory |
| Cloning a repo with `git clone` | Wherever you want the new folder to land |

**Pattern:** commands that *create or modify* a project's state need to be run inside the project. Commands that install or update tools themselves don't care where you are.

### Useful sanity-check commands

- `pwd` — print current directory
- `ls` — show what's in it

---

## 3. Understanding `uv init --python 3.12`

### Anatomy of the command

```
uv init --python 3.12
```

Three parts:
- **`uv`** — the tool.
- **`init`** — a *subcommand* telling `uv` which action to perform.
- **`--python 3.12`** — a *flag* modifying the subcommand's behavior. Long flags start with `--`, short flags with `-`.

General CLI pattern: `<tool> <subcommand> <flags>`. Same structure across tools — `git commit -m "message"`, `npm install --save`, `docker run -it`.

### What `init` actually does

Creates the following files in the current directory:

- **`pyproject.toml`** — project configuration. Modern Python standard (replaced `setup.py` / `requirements.txt`). Declares:
  - Project name and version
  - Python version requirement
  - Dependencies (empty at first; populated by `uv add`)
  - Build settings, dev tools config
- **`.python-version`** — one-line file pinning the Python version (e.g., `3.12`). Tells `uv` which Python to use here. Also recognized by `pyenv`.
- **`README.md`** — empty placeholder if not already present.
- **`hello.py`** — tiny "hello world" file. Safe to delete.
- **`.gitignore`** — adds one with sensible Python defaults (ignores `__pycache__/`, `.venv/`, etc.) if not present.

**`init` does NOT create the virtual environment.** That happens on first `uv add` or `uv sync`. Deliberate — `init` is fast and metadata-only.

### What `--python 3.12` does

Three things:

1. Writes `requires-python = ">=3.12"` into `pyproject.toml`.
2. Writes `3.12` into `.python-version`.
3. **Downloads Python 3.12 if missing.** `uv` keeps managed Pythons separate from system Python — won't touch what's already installed.

### Why 3.12 specifically

- Current stable version (April 2026).
- MCP SDK supports it well.
- Performance and syntax improvements over 3.10/3.11.
- 3.13 also out, but newer = sometimes incompatible with libraries that haven't caught up.
- **3.12 is the safe modern choice.**

### Why pin the Python version explicitly

Without `--python 3.12`, `uv` picks a default — works, but you don't *know* what you're targeting. Reproducibility suffers. Two extra characters saves "works on my machine" debugging.

### Variants you'll see in tutorials

- `uv init --app` — initializes as an "application" (default).
- `uv init --lib` — initializes as a "library." Different file structure. **Don't use for MCP server** — that's an app.
- `uv init --name <name>` — explicitly names the project. Default uses folder name.
- `uv init <path>` — initializes into a subdirectory.

### Mental model

`uv init` is to Python projects what `git init` is to repositories: a one-time command saying "this folder is now a thing of a particular kind." Writes config, no heavy installs. After this, your folder *is* a Python project even with no code in it.

---

## 4. Reading errors literally: `__version__` AttributeError

### The error encountered

```
PS Q:\Revit_Elec_MCP> uv run python -c "import mcp; print(mcp.__version__)"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
AttributeError: module 'mcp' has no attribute '__version__'
```

### What it means

`AttributeError: module 'mcp' has no attribute '__version__'` says exactly the truth: Python imported `mcp` successfully (so the SDK is installed correctly), but the module doesn't define `__version__`.

The error is **not** "module not found." That would mean `mcp` isn't installed. The error is "module found, but the attribute doesn't exist." **The install worked.** The verify command was wrong.

### Why some packages have `__version__` and others don't

Long-standing Python convention: packages expose version as `package.__version__`. Many do (numpy, pandas, requests). But it's a *convention*, not a requirement. Newer packages increasingly skip it because:
- Version lives in `pyproject.toml`.
- Modern tooling reads it from there.

The `mcp` SDK is one that doesn't expose `__version__` directly.

### How to actually verify a package version

**Option 1 — ask `uv` directly (best):**
```powershell
uv pip show mcp
```
Prints metadata: version, location, dependencies.

**Option 2 — Python's importlib (modern, correct way):**
```powershell
uv run python -c "from importlib.metadata import version; print(version('mcp'))"
```
Asks Python's standard library for the installed package version. Reads same metadata `pip` and `uv` use. Works for any installed package whether or not it exposes `__version__`.

**Option 3 — list everything installed:**
```powershell
uv pip list
```

**Option 4 — just confirm import works:**
```powershell
uv run python -c "import mcp; print('mcp imported OK')"
```

### Lessons

**Read errors literally.** "module has no attribute X" and "no module named X" are very different errors with very different fixes.
- First = install worked.
- Second = install didn't work.

**Conventions aren't guarantees.** "Standard" Python idioms (like `__version__`) work for most packages but not all. The authoritative source for "what version is installed" is package metadata, not an attribute on the module — that's what `importlib.metadata.version()` and `uv pip show` read from.

---

## 5. What `uv` actually is, and when to use it

### What it is

`uv` is a Python package and project manager, written in Rust by **Astral** (same team that built `ruff`, the linter that took over Python in ~18 months because it was 10-100x faster than alternatives).

Released early 2024. By 2026, mature, widely adopted, recommended in official Python docs, used in MCP SDK examples.

### What problems it solves

Before `uv`, Python tooling required juggling several tools:

- `python` — but which Python?
- `pyenv` — install/switch Python versions
- `virtualenv` / `venv` — create isolated environments
- `pip` — install packages
- `pip-tools` / `poetry` — manage dependencies and lockfiles
- `pipx` — install command-line tools globally

Each had different syntax, different config files, occasional incompatibilities, slow performance.

**`uv` replaces all of them with one tool.** Same commands, same config (`pyproject.toml` — the official Python standard), one binary. Fast — installs that take 30 seconds with `pip` take 2 seconds with `uv`.

### The seven commands that cover 95% of usage

**`uv init`** — set up a new Python project. Creates `pyproject.toml`, `.python-version`, etc.

**`uv add <package>`** — install a package and record it as a dependency.
```powershell
uv add "mcp[cli]"
uv add pydantic requests
uv add --dev pytest          # development-only dependency
```

**`uv remove <package>`** — uninstall and remove from dependencies.

**`uv sync`** — install everything listed in `pyproject.toml` / `uv.lock`. Run after cloning a repo or pulling changes.

**`uv run <command>`** — run a command inside the project's venv without manually activating.
```powershell
uv run python script.py
uv run python -c "import mcp"
uv run pytest
uv run mcp --help
```
The workhorse. Guarantees you're in the right environment. **No "wait, did I activate the venv?" confusion.**

**`uv lock`** — regenerate the lockfile from `pyproject.toml`. Usually automatic.

**`uv pip <command>`** — compatibility layer mimicking `pip`'s interface.
```powershell
uv pip show mcp
uv pip list
uv pip install <package>
```

### What happens underneath when you `uv add mcp`

1. **Python version check.** Reads `.python-version`, confirms 3.12 available (downloads if not — managed Pythons live in `C:\Users\<you>\AppData\Roaming\uv\python\`).
2. **Virtual environment.** Creates `.venv\` if missing, reuses if present.
3. **Dependency resolution.** Figures out compatible versions. Done in parallel; aggressively cached.
4. **Download.** Downloads wheels from PyPI. Cached in `C:\Users\<you>\AppData\Local\uv\cache\`.
5. **Install.** Unpacks wheels into `.venv\Lib\site-packages\`.
6. **Update `pyproject.toml`.** Adds the new dep.
7. **Update `uv.lock`.** Records exact versions of the package and all transitive deps.

The global cache (step 4) is a killer feature: ten projects using `pydantic` = downloaded once, hardlinked into each project's venv.

### When you might NOT use `uv`

1. **It's young (2024).** Edge cases might not have Stack Overflow answers yet. GitHub issues responsive though.
2. **Some legacy tooling assumes `pip`.** `uv pip` covers most. Won't bite for new projects.
3. **Team standardization.** If a team uses `poetry` or `pip` + `virtualenv`, use what they use. Knowing `uv` doesn't prevent using others — they all read the same `pyproject.toml`.
4. **Anaconda / conda.** Some scientific computing needs conda's C-library handling (some GPU stuff, some bioinformatics). `uv` doesn't fully replace conda. Not relevant to MCP work.
5. **Trivial scripts.** For a one-off `pip install <thing>` is fine. `uv` shines for projects with multiple deps, lockfiles, reproducibility requirements.

### What to internalize vs. look up

**Internalize (daily use):**
- The seven commands above.
- Mental model: `pyproject.toml` (declares deps) vs `uv.lock` (pins exact versions) vs `.venv\` (actual install).
- `uv run` is how you execute things in the project environment.

**Look up when needed:**
- Publishing to PyPI (`uv publish`)
- Building wheels (`uv build`)
- Workspace mode for monorepos
- Tool installation (`uv tool install` — like `pipx`)
- Custom indexes / private package servers

---

## Big-picture mental model (the layered view)

When something breaks, ask which layer:

1. **System Python** — never touch directly.
2. **`uv`** — manages Python versions and virtual environments.
3. **Virtual environment (`.venv\`)** — isolated install scoped to the project.
4. **`pyproject.toml`** — declares what the project needs.
5. **`uv.lock`** — pins exact versions for reproducibility.
6. **`uv run <cmd>`** — runs commands inside the venv without manual activation.

Failure modes, in rough order of frequency: wrong Python version, wrong venv active, missing dependency, version conflict.

---

## Key takeaways

- **Use PowerShell, not cmd.** Modern, object-based, what the ecosystem assumes.
- **`uv` is system-wide; project commands run inside the project.** Don't confuse the two.
- **Pin Python version explicitly with `--python 3.12`.** Reproducibility matters.
- **Read errors literally.** "no attribute" ≠ "no module." Different problems, different fixes.
- **`uv` is the right call by 2026.** Consolidates 15 years of Python tooling pain into one fast tool. Karpathy uses it; the MCP SDK uses it; the ecosystem is converging on it.
- **`uv run` is the daily workhorse.** Guarantees the right environment without manual activation.

The official mcp Python package gives you two levels:                                                             
  - FastMCP — a decorator-driven high-level wrapper. You annotate functions, it handles the
  plumbing. This is what you want 95% of the time.
  - Server — the raw low-level class. You manually register handlers for each JSON-RPC method.
  Useful to understand, rarely what you write directly.

  The initialization handshake

  MCP is JSON-RPC 2.0 over a transport (for local use: stdio — the client writes to your process's   stdin, reads from stdout). The handshake is three steps:

  1. Client → Server: initialize request — sends protocol version and what capabilities the client   supports (tools, resources, prompts, sampling…)
  2. Server → Client: initialize response — server declares its own protocol version and which
  capabilities it exposes
  3. Client → Server: initialized notification — "OK, we're live"

  The SDK handles all of this automatically. You declare what you expose (tools, resources, etc.)
  when you build the server object, and the SDK negotiates the capability exchange for you. You
  write zero handshake code.

  The minimum to expose one tool

  Three things must exist:

  1. A FastMCP instance — this is your server. It holds your name/version and the capability
  registry.
  2. A decorated function — @mcp.tool() on a typed Python function. The SDK reads the function's
  name, docstring, and type annotations to auto-generate the JSON Schema that describes the tool
  to the client. No schema writing by hand.
  3. A run() call — mcp.run(transport="stdio") at the bottom, under if __name__ == "__main__".
  This starts the event loop and blocks, reading JSON-RPC from stdin forever.

  When the client calls your tool, the flow is:
  - Client sends tools/call with {"name": "your_function", "arguments": {...}}
  - SDK validates arguments against the generated schema
  - SDK calls your function with those arguments as kwargs
  - Your function returns a value (string, or explicitly a list of TextContent/ImageContent)
  - SDK wraps it in a tools/call response and writes it to stdout


  05.08 Restart here:
   Recap:

  - FastMCP("revit-elec-mcp") creates the server and registers its name for the handshake —
  there's no separate version param in this SDK version
  - @mcp.tool() does three things at once: registers the tool, derives the name from the function
  name, and builds the JSON Schema from the type annotations
  - The docstring becomes the tool description the LLM sees when deciding whether to call it —
  write it like you're talking to a model, not a human
  - mcp.run(transport="stdio") is the blocking event loop; nothing above it runs after that line
  - A plain str return is all you need — the SDK wraps it in TextContent automatically

  Question you should be able to answer: If you added a second parameter count: int to ping, what
  would change about what the client receives during capability negotiation, and what would happen   if the client passed "three" instead of 3?

---

## Step 7 Decision Point: The Revit Bridge

### The architectural problem

The MCP server (`main.py`) is a separate Python process. Revit's API is only accessible from
inside Revit's own process. They cannot talk directly. A bridge is required.

```
Claude Desktop → stdio → Python MCP server → [BRIDGE] → Revit API (inside Revit process)
```

### What the reference project does (mcp-servers-for-revit on GitHub)

They used: **TypeScript MCP server → WebSocket → C# Revit plugin → Revit API**

Three-tier architecture:
1. TypeScript MCP server — exposes tools to Claude Desktop over stdio
2. C# Revit plugin — loads into Revit at startup, listens on a WebSocket
3. C# command set — implements the actual Revit API calls

The transport between the MCP server and the plugin was WebSocket. Named pipes and local HTTP
are other common choices — same pattern, different wire protocol.

### Our options

**Option A — pyRevit (Python inside Revit)**
- Python scripts that run inside Revit's process, with access to the Revit API
- Stays in Python on both sides — consistent with existing skill set
- Downside: pyRevit has version dependency quirks and some maintenance gaps
- Good for: moving fast, staying in Python, learning the Revit API without C#

**Option B — C# Revit addin**
- A .dll loaded by Revit at startup, written in C#
- Full, first-class access to the Revit API — the officially supported path
- Plugin opens a local socket; MCP server calls it from Python
- Downside: requires learning C#

### Decision for now

**Start with pyRevit** to maintain momentum and keep the bridge in Python.
Learn C# when pyRevit hits a real ceiling — that way C# learning is attached to a concrete
problem, which is the fastest way to absorb a new language.

### Why C# is worth learning eventually

The entire AEC desktop software ecosystem (Revit, Rhino, AutoCAD, Navisworks) exposes its APIs
in C#/.NET. Python bindings exist but are always second-class. If the goal is building tools
that plug into live models — not just processing exported data — C# will eventually be required.
Given a Python background, productive C# is achievable within a few weeks of focused practice.
The syntax is more verbose but the logic transfers directly.

---

## Why you can't call the Revit API from a background thread

### The short answer

Revit's API has no thread safety at all — not "limited" thread safety, but none. It can only
be called from the main UI thread, inside what Revit calls a "valid Revit API context."

### What "valid Revit API context" means

Revit considers the API callable only when *Revit itself* called into your code — via
`OnStartup`, an event handler, a command's `Execute` method, etc. When your code spins up
its own background thread (e.g., a WebSocket server), that thread was never called by Revit.
From Revit's perspective, it doesn't exist.

If you call the API from a background thread anyway, you get one of:
- `InvalidOperationException`: "Cannot execute Revit API outside of Revit API context"
- No exception, but silent data corruption that surfaces later in a confusing way

### Why Revit was designed this way

Revit's object model is built on COM internals from the early 2000s. The element store,
parameter tables, and geometry cache are plain mutable objects — no mutexes, no concurrent
collections, no copy-on-write. Making it thread-safe would require either locking every
property access (slow, deadlock-prone) or rewriting the document model from scratch.
Autodesk chose a simpler rule: all API calls happen on one thread, period.

### ExternalEvent is the solution

`ExternalEvent` is Revit's mechanism for scheduling work from a background thread onto the
UI thread. Think of it as Revit's version of `Dispatcher.Invoke()` in WPF/WinForms.

The flow:
```
Background thread (WebSocket receives request)
  → stores request payload in a shared field
  → calls ExternalEvent.Raise()        ← this IS thread-safe; it just sets a flag
  → blocks on a TaskCompletionSource<string>

Revit UI thread (polling during idle time)
  → sees the flag
  → calls IExternalEventHandler.Execute()   ← full Revit API context here
  → executes the Revit API call safely
  → writes result into the TaskCompletionSource

Background thread unblocks
  → sends JSON response over WebSocket
```

`ExternalEvent.Raise()` does not execute anything. It only sets a flag. Revit checks that
flag on the UI thread during idle time. Only then does your `Execute()` run — on the UI
thread, in a valid context, where Revit API calls work.

### The WPF/WinForms analogy

If you've seen `Dispatcher.Invoke()` or `Control.Invoke()` in desktop UI work, this is the
same idea: you can't update a UI control from a background thread, so you marshal the work
back to the UI thread. `ExternalEvent` is Revit's version of that marshal.

### Key implication for the architecture

This is why the C# add-in has two moving parts that might otherwise seem redundant:

1. **WebSocket server** — runs on a background thread, handles network I/O
2. **IExternalEventHandler** — runs on the UI thread, handles Revit API calls

They're not interchangeable. The WebSocket thread handles all the async networking; the
handler handles all the Revit work. `ExternalEvent` is the handoff point between them.

---

## ExternalEvent: The Four Pieces (detailed breakdown)

### The four objects you work with

**1. `IExternalEventHandler`**
An interface with a single method: `Execute(UIApplication app)`. This is where your Revit API
calls live. It runs on the UI thread — the only place Revit allows API calls.

**2. `ExternalEvent`**
A wrapper Revit gives you around your handler. Created once at startup with
`ExternalEvent.Create(yourHandler)`. Hold onto this object for the lifetime of the add-in.

**3. `Raise()`**
Called from your background thread to ask Revit to run your handler. Does **not** block —
it just queues the request. Revit calls `Execute()` on its own schedule (typically within
milliseconds, unless Revit is in a modal dialog or mid-transaction).

**4. Shared state**
`Execute()` runs on the UI thread. Your WebSocket handler runs on a background thread.
They communicate through fields on the handler object itself. The standard pattern is
`TaskCompletionSource<T>`:

- Background thread creates a `TaskCompletionSource<string>`, stores it on the handler
- Background thread calls `Raise()`, then `await`s the `Task` — this suspends the background thread
- `Execute()` runs, gets the Revit data, calls `tcs.SetResult(data)` — this unblocks the awaiter
- Background thread wakes up with the result and sends it over the WebSocket

### The full request/response flow

```
Background thread (WebSocket)              UI thread (Revit)
─────────────────────────────              ─────────────────
Message arrives
↓
Write request data into handler fields
Create TaskCompletionSource, store it
↓
Call externalEvent.Raise()
↓                                          ... Revit event loop fires ...
await tcs.Task  (suspends)                 ↓
                                           Execute() runs
                                           ↓
                                           Reads request from handler fields
                                           ↓
                                           Calls Revit API
                                           ↓
                                           Calls tcs.SetResult(data)
↓
Background thread unblocks with result
↓
Send reply over WebSocket
```

### Why a mutex wouldn't solve this

You might wonder: could a background thread just lock a mutex around the Revit API call
and call it directly? No — and the reason is important.

The problem is not *concurrent* access. A mutex prevents two threads from running the same
code at the same time. But Revit's constraint is different: **the background thread is never
in a valid state to call the Revit API**, no matter how much you serialize access.

Revit's API requires being on the UI thread because:
- The element store, parameter tables, and geometry cache are plain mutable objects
  with no locking mechanisms at all (COM internals from the early 2000s)
- The UI thread owns the document context — transactions, selection, view state
- A background thread doesn't have that context, even if nothing else is running

`ExternalEvent` works not because it serializes access, but because it changes *who* is
making the call. You're not calling Revit from your thread — you're asking *Revit* to call
*you* back from its own thread, at a moment Revit has chosen as safe.

The mental model: **you're a guest, and `Raise()` is how you knock on the door instead of
barging in.**

---

## For the first pulgin:
Read them in the order Revit itself processes them:
                                                                  
  1. RevitElecMcp.addin — start here. This is the only file Revit reads directly.  Everything else flows from it. Understand what each XML tag does before moving on.
  2. RevitElecMcp.csproj — read this second. It answers "how does the DLL get built and how   does it end up in the Addins folder?" Focus on the ExcludeAssets="runtime" comment and
  the CopyToRevitAddins build target at the bottom.

  3. App.cs — read last. By this point you already know Revit found the manifest, loaded
  the DLL, and is looking for the class named in FullClassName. Now you're just reading
  what that class actually does.

  The mental thread connecting all three: manifest tells Revit where to find the code →
  .csproj controls how the code is built and deployed → App.cs is what runs.

## Websocket server and External Event
What we're building

  Three files, each with one job:
  ElementQueryHandler.cs — implements IExternalEventHandler. This is the only place Revit API calls
  happen. It reads a request from shared state, runs FilteredElementCollector, serializes the result to
  JSON, then signals the waiting background thread via TaskCompletionSource.

  WebSocketServer.cs — a background listener on localhost:8765. When a message arrives, it stores a
  TaskCompletionSource on the handler, calls ExternalEvent.Raise(), then awaits the result. When the UI
  thread signals it, it sends the JSON back over the socket.

  App.cs (updated) — creates the handler and event once at startup, hands them to the server, starts the
  server on a background thread. Stops it cleanly on shutdown.

  ---
  Key design choices, and why

  Built-in WebSocket (System.Net.HttpListener) over a NuGet library (Fleck, etc.) — .NET 8 has WebSocket
  support built in. No extra package, and you can see exactly what the handshake does. Slightly more
  verbose, but nothing hidden.

  System.Text.Json over Newtonsoft — also built into .NET 8. Newtonsoft is legacy at this point for new
  .NET code.

  One connection at a time — the Python MCP server sends one request and waits for the reply. No need for
  concurrent connection handling. Keeping it single-connection makes the state management obvious.

  What data the handler returns — just id and name from OST_ElectricalFixtures for now. The goal of this
  step is proving the threading model works end-to-end. Once a Python one-liner gets back a real element
  list, adding more fields (voltage, panel, etc.) is a straight-line exercise.

  ---
  One footgun to know about

  ExternalEvent.Raise() returns a ExternalEventRequest enum, not a bool. If Revit is busy (inside a modal
  dialog, saving, etc.) it returns Pending instead of Accepted. In that state, your background thread is
  already awaiting the TCS — and Execute() will still run eventually, so it'll unblock correctly. But if
  Revit returns Denied (add-in not registered properly), the TCS will never complete and the WebSocket
  call will hang forever. We'll add a timeout guard for that.

  ---
  The shape before code

  App.OnStartup()
    new ElementQueryHandler → handler
    ExternalEvent.Create(handler) → externalEvent
    new WebSocketServer(handler, externalEvent).Start()

  WebSocketServer (background thread)
    listen on localhost:8765
    receive {"command": "get_elements"}
    handler.Tcs = new TaskCompletionSource<string>()
    externalEvent.Raise()
    result = await handler.Tcs.Task (with timeout)
    send result over socket

  ElementQueryHandler.Execute() (UI thread)
    FilteredElementCollector → OST_ElectricalFixtures
    serialize to JSON
    handler.Tcs.SetResult(json)

  App.OnShutdown()
    WebSocketServer.Stop()

## Decisions and alternatives
  Why these specific choices over alternatives

  Choice: System.Net.HttpListener for WebSocket
  Alternative skipped: Fleck, WebSocketSharp
  Why: Built into .NET 8 — no NuGet dep, you can see every handshake step
  ────────────────────────────────────────
  Choice: System.Text.Json
  Alternative skipped: Newtonsoft.Json
  Why: Also built-in to .NET 8; Newtonsoft is legacy for new code
  ────────────────────────────────────────
  Choice: TCS as handoff
  Alternative skipped: ManualResetEvent + shared string field
  Why: TCS integrates naturally with async/await; the background thread suspends
    cleanly without spin-waiting
  ────────────────────────────────────────
  Choice: One connection at a time
  Alternative skipped: Multi-client server
  Why: The MCP server is synchronous — over-engineering this adds state management
    complexity with no benefit right now

  ---
  What was just built — 5 bullets:

  - ElementQueryHandler.cs — the only file that touches the Revit API. Execute()
  runs on the UI thread, calls FilteredElementCollector for OST_ElectricalFixtures,   serializes the result to JSON, then calls tcs.SetResult() to unblock whoever is
  waiting.
  - WebSocketServer.cs — runs on a background thread. Accepts one connection,
  receives any message, creates a fresh TaskCompletionSource, stores it on the
  handler, calls externalEvent.Raise(), then suspends with await tcs.Task.
  - App.cs — wires the two together at Revit startup: creates the handler + event
  on the UI thread (the only valid moment for ExternalEvent.Create), then fires the   server loop on a background thread with Task.Run.
  - Timeout guard — Task.WhenAny(tcs.Task, Task.Delay(5000)) means a Pending or
  Denied raise never hangs the WebSocket connection indefinitely.
  - No new NuGet packages — HttpListener, System.Net.WebSockets, and
  System.Text.Json are all built into .NET 8.
  # Question you should be able to answer: If Revit is showing a modal dialog when a
  WebSocket message arrives and Raise() returns Pending (not Denied), what happens
  to the background thread — and why does it eventually unblock correctly without
  any extra code on our part?
  Answer: Pending means Revit accepted the request but is busy right now (modal dialog,  save in progress, etc.). It will call Execute() once the dialog closes. So:
  - Background thread suspends on await tcs.Task ✓
  - User closes the modal → Revit goes idle → Execute() fires → tcs.SetResult() →
  background thread unblocks → reply sent
  - Timeout never triggers — Pending always resolves eventually

  Denied is the case the timeout guards against. That means the raise was outright
  rejected — Execute() will never fire, the TCS will never complete, and without
  the timeout the WebSocket connection hangs until the client disconnects.

  So the code handles both cases correctly, but for different reasons:

  var status = _externalEvent.Raise();
  if (status == ExternalEventRequest.Denied)   // ← "never happening" — exit
  immediately
  {
      await SendAsync(ws, ...error...);
      return;
  }

  // Pending or Accepted both fall through to here.
  // Pending: waits a bit longer, but Execute() fires eventually — timeout doesn't
  trigger.
  // Denied already returned above, so the only way timeout fires is an unexpected
  hang.
  var winner = await Task.WhenAny(tcs.Task, Task.Delay(5000));

  The mental model: Raise() is a question, not a command. Accepted = "I'll do it
  now." Pending = "I'll do it when I'm free." Denied = "I don't know who you are."

  Clean build. Here's what was written and why:

  CircuitQueryHandler.cs─(new)─────────────────────────────────────────────────────  - Same IExternalEventHandler pattern as ElementQueryHandler — no new concepts
  here  - Queries OST_ElectricalCircuit, casts each to ElectricalSystem with as + null
  filter  - PanelName = null means return all circuits; set it to filter to one panel
  - The using Autodesk.Revit.DB.Electrical was the one thing I got wrong initially
  — ElectricalSystem lives in that sub-namespace, not the parent Autodesk.Revit.DB

  WebSocketServer.cs (rewritten)
  - Two changes worth noting: the received.Count fix (previously the whole
  4096-byte buffer was passed to GetString, including trailing zeros — now we pass
  only the actual bytes received), and RaiseAndWaitAsync extracted as a shared
  helper so the Denied/timeout logic doesn't repeat in every command arm

  App.cs — creates both handlers + events at startup, passes both to
  WebSocketServer

  main.py — _send() helper extracted so both tools share the connect/send/recv
  pattern rather than duplicating it; the check_breaker_sizing docstring includes
  the NEC 210.20(A) formula because that's what Claude reads when deciding how to
  reason about the data

  Question you should be able to answer: HandleConnectionAsync has a try/catch
  around the routing block, and each handler's Execute() also has its own
  try/catch. Why do we need both — what does each one catch that the other can't?
  Two different failure locations, two different catchers.

  HandleConnectionAsync try/catch catches failures that happen before Revit is ever   involved — malformed JSON from Python, a missing "command" property, a missing
  "panel" property. At that point we're still on the background thread, no  ExternalEvent has been raised, and Revit hasn't been touched. If we didn't catch
  here, the exception would bubble up and crash the WebSocket loop.

  Execute() try/catch catches failures that happen inside Revit — the document is
  in a bad state, the FilteredElementCollector throws, a parameter read fails. At
  that point we're on the UI thread, and there's no way for an exception to travel
  back to the background thread naturally. If Execute() throws uncaught, Revit
  itself absorbs it silently — and the TaskCompletionSource never gets SetResult()
  called, so the background thread hangs until the 5-second timeout fires and
  returns a generic "timed out" error instead of the real error message.

  The Execute() catch exists to convert Revit-side exceptions into a JSON error
  string that can actually reach the caller.

  The short version: one catch is for bad input before Revit, the other is for
  Revit failures that would otherwise disappear silently.
---

What a Transaction actually is

  Think of Revit's document as a database. While the model is open, it lives
  entirely in memory — the .rvt file on disk isn't touched until the user clicks
  Save. A Transaction is Revit's write-lock on that in-memory database. Without one,   Revit refuses all modifications and throws immediately. With one open, Revit
  tracks every change you make so it can either finalize or discard them as a unit.
  ---
  The three operations

  Start() — opens the write lock and begins tracking. From this moment, Revit
  journals every change: parameter sets, element creations, deletions. The model is
  now in a "modified" state. Nothing is visible to the user yet — the panel schedule   in Revit still shows the old breaker rating.

  Commit() — finalizes everything since Start(). Two things happen: the changes
  become visible in the model (the panel schedule now shows the new rating), and one   entry is added to Revit's undo stack using the name you passed to the
  constructor. The write lock is released. Importantly, this does NOT save to disk —   that still requires the user to Ctrl+S.

  RollBack() — discards everything since Start(). The model snaps back to exactly
  the state it was in before Start() was called. Nothing goes to the undo stack — as   far as the user is concerned, nothing happened. The write lock is released.

  Both Commit() and RollBack() return a TransactionStatus enum. Commit() can fail —
  for example, if the model is a cloud model that someone else has checked out, or
  if Revit's regeneration step detects an invalid model state. You should check the
  return value rather than assuming success.

  ---
  Where it lives relative to ExternalEvent

  This is the key structural question, and the answer flows directly from the
  threading model you already know:

  - Transactions are Revit API calls.
  - All Revit API calls must be on the UI thread.
  - Execute() is the only method Revit calls on the UI thread.

  Therefore: the Transaction opens and closes entirely inside Execute(). Not in the
  WebSocket handler, not in main.py, not in any background thread. The background
  WebSocket thread's job is only to set shared state (circuit_id, new_rating) and
  raise the ExternalEvent. By the time the Transaction opens, the background thread
  is already blocked, waiting on the TaskCompletionSource.

  The sequence looks like this:

  Background thread:  set circuit_id, new_rating → Raise() → await TCS
                                                                ↓
  UI thread (Execute()):                              open Transaction → set
  parameter → Commit() → SetResult()

                    ↓
  Background thread:
         unblocked → send response over WebSocket

  The Transaction is invisible to Python and to the MCP layer entirely. It's a C#
  concern, inside one method, on the UI thread.

  ---
  One defensive detail worth knowing

  Transaction implements IDisposable. If Execute() throws an unhandled exception and   the Transaction was never committed or rolled back, Revit disposes it
  automatically and treats it as an abandoned transaction — same effect as
  RollBack(). This is Revit being defensive: it will never leave a dangling write
  lock. That said, you don't want to rely on this — you want to call RollBack()
  explicitly in your catch block so you can also call Tcs.SetResult() with a real
  error message rather than leaving the background thread to time out.

  ---
  Say go when you're ready to write BreakerFixHandler.cs and the fix_breaker_size
  tool.