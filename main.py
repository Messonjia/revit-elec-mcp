from mcp.server.fastmcp import FastMCP

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


if __name__ == "__main__":
    # transport="stdio" means: read JSON-RPC from stdin, write to stdout.
    # This is what Claude Desktop (and most local MCP clients) expect.
    # The call blocks forever — the server lives as long as the process does.
    mcp.run(transport="stdio")
