"""Test installed server entry points and MCP discovery over stdio."""

import asyncio
import sys
from importlib.metadata import version
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from anyvar_mcp.config import SERVER_INSTRUCTIONS


@pytest.mark.parametrize("entry_point", ["module", "console"])
def test_server_startup_and_discovery(tmp_path: Path, entry_point: str) -> None:
    """Run both entry points outside the repository and exchange MCP requests."""
    command = sys.executable
    args = ["-m", "anyvar_mcp.server"]
    if entry_point == "console":
        command = str(Path(sys.executable).with_name("anyvar-mcp"))
        args = []

    transport = StdioTransport(
        command=command,
        args=args,
        cwd=str(tmp_path),
        env={},
        keep_alive=False,
    )

    async def check_server() -> None:
        """Connect and discover server capabilities within a bounded time."""
        async with asyncio.timeout(15), Client(transport) as client:
            await client.list_tools()
            await client.list_resources()
            await client.list_prompts()

            assert client.server_info is not None
            assert client.server_info.name == "AnyVar"
            assert client.server_info.version == version("anyvar-mcp")
            assert client.instructions == SERVER_INSTRUCTIONS

    asyncio.run(check_server())
