import json
import websockets
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("revit-elec-mcp")

REVIT_WS_URL = "ws://localhost:8765"


@mcp.tool()
def ping(message: str) -> str:
    """Echo a message back. Use this to verify the server is reachable."""
    return f"pong: {message}"


@mcp.tool()
async def query_elements() -> str:
    """Return all electrical fixtures from the live Revit model as a JSON list.
    Each element has an 'id' (integer) and 'name' (string).
    Requires Revit to be open with a model loaded and the RevitElecMcp add-in active."""
    try:
        async with websockets.connect(REVIT_WS_URL) as ws:
            await ws.send('{"command": "get_elements"}')
            return await ws.recv()
    except OSError:
        # Revit isn't running, or the add-in didn't start the WebSocket server.
        return json.dumps({"error": "Could not connect to Revit. Is Revit open with the RevitElecMcp add-in loaded?"})


if __name__ == "__main__":
    mcp.run(transport="stdio")
