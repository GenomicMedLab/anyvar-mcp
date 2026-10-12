"""Expose AnyVar capabilities through the MCP."""

from fastmcp import FastMCP

from anyvar_mcp import __version__
from anyvar_mcp.config import SERVER_INSTRUCTIONS, SERVER_NAME

mcp = FastMCP(
    name=SERVER_NAME,
    version=__version__,
    instructions=SERVER_INSTRUCTIONS,
)


def main() -> None:
    """Run the MCP server over standard input and output."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
