from mcp.server.fastmcp import FastMCP
from typing import Optional
import json

# FastMCP is the server object AND the capability registry.
# The name and version are sent to the client during the initialize handshake
# so the client knows what it's talking to.
mcp = FastMCP("revit-elec-mcp")


@mcp.tool()
def ping(message: str) -> str:
    """Echo a message back. Use this to verify the server is reachable."""
    # FastMCP reads the function name → tool name ("ping")
    # reads the docstring → tool description shown to the LLM
    # reads the type annotations → JSON Schema for input validation
    # A plain `str` return is automatically wrapped in TextContent for you.
    return f"pong: {message}"


# Hardcoded fake Revit elements — stand-ins for what the Revit API would return.
# Each dict mirrors the schema we designed: element-level fields (classification,
# voltage, ampere) plus connection-level fields (panel, circuit, description).
FAKE_ELEMENTS = [
    {
        "id": "001",
        "name": "Exhaust Fan EF-1",
        "voltage": 120,
        "ampere": 20,
        "location": "Floor 1",
        "load_classification": "HVAC",
        "load_description": "Exhaust Fan (E)",  # (E) baked in because is_existing=True
        "is_existing": True,
        "panel": "LP-1A",
        "circuit_number": "3",
    },
    {
        "id": "002",
        "name": "Dishwasher DW-1",
        "voltage": 120,
        "ampere": 20,
        "location": "Floor 1",
        "load_classification": "Kitchen",
        "load_description": "Dishwasher",
        "is_existing": False,
        "panel": "LP-1A",
        "circuit_number": "5",
    },
    {
        "id": "003",
        "name": "RTU-2 Condenser",
        "voltage": 208,
        "ampere": 30,
        "location": "Roof",
        "load_classification": "HVAC",
        "load_description": "RTU-2 Condenser",
        "is_existing": False,
        "panel": "MP-1",
        "circuit_number": "12",
    },
    {
        "id": "004",
        "name": "Receptacle REC-14",
        "voltage": 120,
        "ampere": 20,
        "location": "Floor 2",
        "load_classification": "Misc",
        "load_description": "General Receptacle",
        "is_existing": False,
        # Not yet circuited — will be connected to a panel later
        "panel": None,
        "circuit_number": None,
    },
    {
        "id": "005",
        "name": "AHU-1 Motor",
        "voltage": 208,
        "ampere": 30,
        "location": "Floor 2",
        "load_classification": "HVAC",
        "load_description": "AHU-1 Motor (E)",
        "is_existing": True,
        "panel": "MP-1",
        "circuit_number": "8",
    },
]


@mcp.tool()
def query_elements(
    voltage: Optional[int] = None,
    ampere: Optional[int] = None,
    location: Optional[str] = None,
    load_classification: Optional[str] = None,
) -> str:
    """Query Revit electrical elements, optionally filtered by voltage, ampere,
    location, or load classification. Returns a JSON list of matching elements.
    Each element includes its panel and circuit number (None if not yet circuited),
    load description, and whether it is an existing-to-remain item."""

    results = FAKE_ELEMENTS

    # Each filter is applied only if the caller provided a value.
    # Optional means the agent can query broadly or narrow down as needed.
    if voltage is not None:
        results = [e for e in results if e["voltage"] == voltage]
    if ampere is not None:
        results = [e for e in results if e["ampere"] == ampere]
    if location is not None:
        # Case-insensitive so the agent doesn't have to match exact casing
        results = [e for e in results if e["location"].lower() == location.lower()]
    if load_classification is not None:
        results = [e for e in results if e["load_classification"].lower() == load_classification.lower()]

    # Return JSON string — FastMCP wraps it in TextContent automatically.
    # The agent can parse this or reason over it directly as text.
    return json.dumps(results, indent=2)


if __name__ == "__main__":
    # transport="stdio" means: read JSON-RPC from stdin, write to stdout.
    # This is what Claude Desktop (and most local MCP clients) expect.
    # The call blocks forever — the server lives as long as the process does.
    mcp.run(transport="stdio")
