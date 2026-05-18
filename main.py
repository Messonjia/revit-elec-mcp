import json
import websockets
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("revit-elec-mcp")

REVIT_WS_URL = "ws://localhost:8765"


async def _send(payload: dict) -> str:
    """Send a command dict to the Revit add-in over WebSocket and return the response."""
    try:
        async with websockets.connect(REVIT_WS_URL) as ws:
            await ws.send(json.dumps(payload))
            return await ws.recv()
    except OSError:
        return json.dumps({"error": "Could not connect to Revit. Is Revit open with the RevitElecMcp add-in loaded?"})


@mcp.tool()
def ping(message: str) -> str:
    """Echo a message back. Use this to verify the server is reachable."""
    return f"pong: {message}"


@mcp.tool()
async def query_elements() -> str:
    """Return all electrical fixtures from the live Revit model as a JSON list.
    Each element has an 'id' (integer) and 'name' (string).
    Requires Revit to be open with a model loaded and the RevitElecMcp add-in active."""
    return await _send({"command": "get_elements"})


@mcp.tool()
async def check_breaker_sizing(panel: str) -> str:
    """Return all circuits connected to a named panel with their electrical load data
    and current breaker rating. Use this to check whether each breaker is correctly sized.

    Each circuit in the returned list has:
      id                  — element ID (integer); pass this to fix_breaker_size
      circuit_number      — string, e.g. "3"
      panel               — panel name
      apparent_load_va    — total load in volt-amperes (VA)
      voltage             — circuit voltage in volts
      poles               — 1 (single-phase) or 3 (three-phase)
      breaker_rating      — current breaker size in amperes
      load_classification — Revit load type string, e.g. "Lighting", "Power", "Motor", "HVAC"

    Apply NEC rules based on load_classification:

    For Lighting, Power, General, and other non-motor loads — NEC 210.20(A):
      load_amps       = apparent_load_va / voltage                        (single-phase)
      load_amps       = apparent_load_va / (voltage * 1.732)              (three-phase)
      required_rating = next standard size >= load_amps * 1.25
      Standard sizes: 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150...
      Flag if breaker_rating < required_rating (undersized — dangerous).
      Flag if breaker_rating > next standard size above required (oversized — protection defeated).

    For Motor or HVAC loads — NEC 430 / NEC 440:
      Do NOT apply the 125% rule. Motor breakers are intentionally oversized to handle
      starting inrush current (NEC 430.52 allows up to 250% of motor FLC).
      Report the circuit data as-is and tell the user:
      "Motor/HVAC load — NEC 430/440 sizing rules not yet implemented. Manual review required."

    Requires Revit to be open with a model loaded and the RevitElecMcp add-in active."""
    return await _send({"command": "get_circuits", "panel": panel})


@mcp.tool()
async def fix_breaker_size(circuit_id: int, new_rating: int) -> str:
    """WRITES TO THE REVIT MODEL. Set the breaker rating for a single circuit.

    circuit_id — the integer element ID returned by check_breaker_sizing
    new_rating — new breaker size in amperes; must be a standard size:
                 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200

    IMPORTANT: This immediately modifies the live Revit model. Only call this tool
    after explaining the proposed change to the user and receiving explicit confirmation.
    The change appears in Revit's undo history as "Fix breaker size" and can be undone
    with Ctrl+Z.

    Requires Revit to be open with the model loaded and the RevitElecMcp add-in active."""
    return await _send({"command": "fix_breaker", "circuit_id": circuit_id, "new_rating": new_rating})


@mcp.tool()
async def list_panels() -> str:
    """Return all electrical panels (distribution equipment) in the live Revit model.
    Each entry has an 'id' (integer) and 'name' (string).
    Call this before check_breaker_sizing to discover panel names.
    Requires Revit to be open with a model loaded and the RevitElecMcp add-in active."""
    return await _send({"command": "list_panels"})


if __name__ == "__main__":
    mcp.run(transport="stdio")
