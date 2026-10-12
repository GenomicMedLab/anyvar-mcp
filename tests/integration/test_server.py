"""Test server metadata and discovery through an in-memory FastMCP client."""

import asyncio
from importlib.metadata import version

import pytest
from fastmcp import Client, FastMCP

from anyvar_mcp.server import mcp


@pytest.mark.ci_ok
def test_server_metadata_and_discovery() -> None:
    assert isinstance(mcp, FastMCP)

    async def connect_and_discover() -> None:
        async with Client(mcp) as client:
            assert client.server_info is not None
            assert client.server_info.name == "AnyVar"
            assert client.server_info.version == version("anyvar-mcp")
            assert client.instructions == "MCP server for AnyVar."
            assert await client.list_tools() == []
            assert await client.list_resources() == []
            assert await client.list_prompts() == []

    asyncio.run(connect_and_discover())
