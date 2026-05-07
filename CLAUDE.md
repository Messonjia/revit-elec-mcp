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