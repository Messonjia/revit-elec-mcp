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