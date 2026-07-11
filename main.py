import json
import websockets
from mcp.server.fastmcp import FastMCP
from nec_rules import check_circuit

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
      is_spare            — true when the circuit has no connected elements; NEC sizing not applicable
      hp                  — motor horsepower (null unless a Motor/HVAC circuit with HP on connected equipment)

    Apply NEC rules based on load_classification:

    For Lighting, Power, General, and other non-motor loads — NEC 210.20(A):
      load_amps       = apparent_load_va / voltage                        (single-phase)
      load_amps       = apparent_load_va / (voltage * 1.732)              (three-phase)
      required_rating = next standard size >= load_amps * 1.25
      Standard sizes: 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150...
      Flag if breaker_rating < required_rating (undersized — dangerous).
      Flag if breaker_rating > next standard size above required (oversized — protection defeated).

    For Motor or HVAC loads — NEC 430.52:
      Do NOT apply the 125% rule. Motor breakers are intentionally oversized to handle
      starting inrush current; NEC 430.52 instead CAPS an inverse-time breaker at 250% of
      the motor's full-load current (FLC) from NEC Table 430.248 (single-phase) or
      430.250 (three-phase). Flag if breaker_rating exceeds that cap.
      Prefer check_breaker_compliance for motor circuits — it encodes the FLC tables and
      applies the cap deterministically. If hp is null, HP is unknown: manual review required.

    Requires Revit to be open with a model loaded and the RevitElecMcp add-in active."""
    return await _send({"command": "get_circuits", "panel": panel})


@mcp.tool()
async def fix_breaker_size(circuit_id: int, new_rating: int) -> str:
    """WRITES TO THE REVIT MODEL. Set the breaker rating for a single circuit.

    circuit_id — the integer element ID returned by check_breaker_sizing
    new_rating — new breaker size in amperes; must be a standard size per NEC 240.6(A):
                 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150, 175, 200,
                 225, 250, 300, 350, 400, 450, 500, 600, 700, 800, 1000, 1200, 1600, 2000,
                 2500, 3000, 4000, 5000, 6000

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


@mcp.tool()
async def check_breaker_compliance(panel: str) -> str:
    """Return a circuit-by-circuit NEC compliance report for a named panel.

    Rules are applied by Python code (not by Claude), so results are deterministic:
    the same load always produces the same required breaker rating.

    Rules applied by load_classification:
      Lighting/Power/General  — NEC 210.20(A): breaker must be >= 125% of load current
      Motor/HVAC with HP data — NEC 430.52: breaker must be <= 250% of motor FLC
                                (FLC from NEC Table 430.248/430.250); exceeding the cap is a fail
      Motor/HVAC without HP   — status "manual_review": HP is required to size per 430.52

    Each entry in the returned 'circuits' list has:
      status              — "pass", "fail", "spare", or "manual_review"
      circuit_number      — string, e.g. "3"
      panel               — panel name
      load_classification — e.g. "Lighting", "Power", "Motor", "HVAC"
      load_amps           — load current in amperes (null for spare/motor)
      hp                  — motor horsepower used for the FLC lookup (null for non-motor)
      flc_amps            — full-load current from NEC Table 430.248/430.250 (null for non-motor)
      required_amps       — 125% of load_amps for 210.20(A); 250% of flc_amps for 430.52
      required_rating     — standard breaker size: a MINIMUM for 210.20(A), a MAXIMUM for 430.52
      actual_rating       — current breaker rating in the Revit model
      is_oversized        — 210.20(A) only: true if actual > required (still a pass, just larger
                            than needed); always false for motors — too large is already a fail
      is_non_standard     — true if actual_rating is not a standard size per NEC 240.6(A)
      is_zero_load        — true if apparent_load_va is 0 on a non-spare circuit; breaker sizing
                            cannot be verified — flag this to the user as a model data issue
      nec_ref             — article cited, e.g. "NEC 210.20(A)" or "NEC 430.52"
      reason              — one-sentence plain-English explanation of the result

    The 'summary' object gives counts so you can lead with the headline before detailing failures.

    Call list_panels first to discover panel names.
    Requires Revit to be open with a model loaded and the RevitElecMcp add-in active."""

    raw = await _send({"command": "get_circuits", "panel": panel})

    # _send returns a JSON string. If the add-in returned an error object, surface it
    # directly rather than trying to apply NEC rules to an error message.
    data = json.loads(raw)
    if isinstance(data, dict) and "error" in data:
        return raw

    results = [check_circuit(c) for c in data]

    # Count each status so Claude can open with "3 circuits fail, 1 needs manual review"
    # without having to scan the full list itself.
    summary = {
        "total":              len(results),
        "pass":               sum(1 for r in results if r["status"] == "pass"),
        "fail":               sum(1 for r in results if r["status"] == "fail"),
        "manual_review":      sum(1 for r in results if r["status"] == "manual_review"),
        "spare":              sum(1 for r in results if r["status"] == "spare"),
        "zero_load_warning":  sum(1 for r in results if r.get("is_zero_load", False)),
    }

    return json.dumps({"panel": panel, "summary": summary, "circuits": results})


@mcp.tool()
async def list_schedules() -> str:
    """Return all schedules in the live Revit model as a JSON list.
    Each entry has an 'id' (integer) and 'name' (string).
    Call this before export_schedule to discover schedule names.
    Requires Revit to be open with a model loaded and the RevitElecMcp add-in active."""
    # No extra parameters needed — the C# handler finds all ViewSchedules on its own.
    return await _send({"command": "list_schedules"})


@mcp.tool()
async def export_schedule(schedule_name: str) -> str:
    """Export a Revit schedule as a JSON table.

    schedule_name — exact name as it appears in the Revit project browser (case-sensitive).
                    Call list_schedules first to get the correct name.

    Returns:
      schedule_name — the schedule name
      columns       — list of column header strings (e.g. ["Circuit Number", "Load Name", "Breaker"])
      rows          — list of rows; each row is a list of strings matching the column order.
                      All values are pre-formatted strings as Revit displays them (e.g. "20 A", not 20).

    Requires Revit to be open with a model loaded and the RevitElecMcp add-in active."""
    # schedule_name is passed through to C# where it is matched against ViewSchedule.Name.
    # The match is exact and case-sensitive — use the name returned by list_schedules.
    return await _send({"command": "export_schedule", "schedule_name": schedule_name})


if __name__ == "__main__":
    mcp.run(transport="stdio")
