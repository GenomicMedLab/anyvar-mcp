"""Test MCP discovery, invocation, and stdio startup without external services."""

import asyncio
import json
import sys
from importlib.metadata import distribution, version
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from fastmcp import Client, FastMCP
from fastmcp.client.transports import StdioTransport

from anyvar_mcp import server
from anyvar_mcp.server import SERVER_INSTRUCTIONS, main, mcp

TOOL_NAMES = {
    "register_variant",
    "get_variant",
    "search_variants",
    "get_variant_mappings",
}


@pytest.fixture(autouse=True)
def reset_request_budget(
    monkeypatch: pytest.MonkeyPatch,
    isolated_config: None,  # noqa: ARG001
) -> None:
    """Give each server test a fresh budget and isolated configuration."""
    monkeypatch.setattr(server, "_request_budget", server._RequestBudget())  # noqa: SLF001


def mock_response(payload: dict[str, object]) -> MagicMock:
    """Provide a requests response supporting JSON access and cleanup."""
    response = MagicMock(spec=requests.Response)
    response.__enter__.return_value = response
    response.is_redirect = False
    response.iter_content.return_value = [json.dumps(payload).encode()]
    return response


def test_server_metadata_and_discovery() -> None:
    """Advertise documented schemas and distinguish reads from registration."""
    assert isinstance(mcp, FastMCP)

    async def connect_and_discover() -> None:
        """Discover documented tools without connecting to AnyVar."""
        async with Client(mcp) as client:
            assert client.server_info is not None
            assert client.server_info.name == "anyvar-mcp"
            assert client.server_info.version == version("anyvar-mcp")
            assert client.instructions == SERVER_INSTRUCTIONS
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert set(tools) == TOOL_NAMES
            for name, tool in tools.items():
                assert tool.description
                assert tool.input_schema["type"] == "object"
                assert tool.output_schema is not None
                assert tool.output_schema["type"] == "object"
                assert tool.annotations is not None
                assert tool.annotations.read_only_hint == (name != "register_variant")

            assert tools["register_variant"].annotations.destructive_hint is False
            page_schema = tools["search_variants"].input_schema["properties"][
                "page_size"
            ]
            assert page_schema["anyOf"][0]["maximum"] == 10_000
            assert page_schema["default"] is None
            assert "transcribe_to" in json.dumps(
                tools["get_variant_mappings"].input_schema
            )
            assert await client.list_resources() == []
            assert await client.list_prompts() == []

    asyncio.run(connect_and_discover())


@pytest.mark.parametrize("entry_point", ["module", "console"])
def test_server_starts_without_application_services(
    tmp_path: "Path", entry_point: str
) -> None:
    """Start each installed entry point and exchange MCP requests."""
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
            tools = await client.list_tools()
            resources = await client.list_resources()
            prompts = await client.list_prompts()

            assert client.server_info is not None
            assert client.server_info.name == "anyvar-mcp"
            assert {tool.name for tool in tools} == TOOL_NAMES
            assert resources == []
            assert prompts == []

    asyncio.run(check_server())


def test_invalid_startup_configuration_allows_discovery(tmp_path: "Path") -> None:
    """Report invalid startup settings when a tool runs, after discovery."""
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "anyvar_mcp.server"],
        cwd=str(tmp_path),
        env={"ANYVAR_API_TIMEOUT": "invalid"},
        keep_alive=False,
    )

    async def check_server() -> None:
        """Discover tools and inspect the configuration error over stdio."""
        async with asyncio.timeout(15), Client(transport) as client:
            assert {tool.name for tool in await client.list_tools()} == TOOL_NAMES

            result = await client.call_tool(
                "get_variant", {"vrs_id": "ga4gh:VA.example"}, raise_on_error=False
            )
            assert result.is_error
            assert "ANYVAR_API_TIMEOUT" in result.content[0].text

    asyncio.run(check_server())


def test_variant_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register, follow a mapping, retrieve its destination, and search via MCP."""
    monkeypatch.setenv("ANYVAR_API_URL", "https://anyvar.example/api")
    monkeypatch.setenv("ANYVAR_ENABLE_REGISTRATION", "true")
    source_id = "ga4gh:VA.source"
    dest_id = "ga4gh:VA.dest"
    registration = {
        "input_variation": {
            "definition": "NC_000010.11:g.87894077C>T",
            "assembly_name": "GRCh38",
        },
        "object": {"id": source_id, "type": "Allele"},
        "object_id": source_id,
        "messages": ["Some projections unavailable"],
    }
    mappings = {
        "mappings": [
            {
                "source_id": source_id,
                "dest_id": dest_id,
                "mapping_type": "transcribe_to",
            }
        ]
    }
    destination = {"data": {"id": dest_id, "type": "Allele"}, "messages": []}
    search = {"variations": [registration["object"]], "next_cursor": "opaque+/="}
    responses = [
        mock_response(payload)
        for payload in (registration, mappings, destination, search)
    ]

    async def call_workflow() -> None:
        """Invoke each tool and check structured output through MCP."""
        async with Client(mcp) as client:
            registered = await client.call_tool(
                "register_variant", registration["input_variation"]
            )
            assert registered.structured_content == registration

            related = await client.call_tool(
                "get_variant_mappings",
                {
                    "vrs_id": source_id,
                    "mapping_type": "transcribe_to",
                    "as_source": True,
                },
            )
            assert related.structured_content == mappings

            retrieved = await client.call_tool(
                "get_variant",
                {"vrs_id": related.structured_content["mappings"][0]["dest_id"]},
            )
            assert retrieved.structured_content == destination

            found = await client.call_tool(
                "search_variants",
                {
                    "accession": "GRCh38:chr10",
                    "start": 87894070,
                    "end": 87894080,
                    "page_size": 1,
                    "cursor": "previous",
                },
            )
            assert found.structured_content == search

    with patch(
        "anyvar_mcp.clients.anyvar.requests.request", side_effect=responses
    ) as request:
        asyncio.run(call_workflow())

    assert [urlsplit(call.kwargs["url"]).path for call in request.call_args_list] == [
        "/api/variation",
        "/api/object/ga4gh%3AVA.source/mappings",
        "/api/object/ga4gh%3AVA.dest",
        "/api/variations",
    ]
    assert request.call_args_list[0].kwargs["json"] == registration["input_variation"]
    assert parse_qs(urlsplit(request.call_args_list[1].kwargs["url"]).query) == {
        "as_source": ["true"],
        "mapping_type": ["transcribe_to"],
    }
    assert parse_qs(urlsplit(request.call_args_list[3].kwargs["url"]).query) == {
        "accession": ["GRCh38:chr10"],
        "start": ["87894070"],
        "end": ["87894080"],
        "page_size": ["1"],
        "cursor": ["previous"],
    }


def test_unresolved_registration_through_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return unresolved registration as structured data with failure messages."""
    payload = {
        "input_variation": {"definition": "unsupported"},
        "messages": ["Unable to translate unsupported"],
    }
    monkeypatch.setenv("ANYVAR_ENABLE_REGISTRATION", "true")

    async def register() -> None:
        """Submit an unsupported definition and inspect its structured result."""
        async with Client(mcp) as client:
            result = await client.call_tool(
                "register_variant", {"definition": "unsupported"}
            )

        assert result.structured_content == {
            "object": None,
            "object_id": None,
            **payload,
        }
        assert result.is_error is False

    with patch(
        "anyvar_mcp.clients.anyvar.requests.request",
        return_value=mock_response(payload),
    ):
        asyncio.run(register())


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("register_variant", {"definition": "variant"}),
        ("get_variant", {"vrs_id": "ga4gh:VA.example"}),
        ("search_variants", {"accession": "NC_1", "start": 0, "end": 1}),
        ("get_variant_mappings", {"vrs_id": "ga4gh:VA.example"}),
    ],
)
def test_http_errors_through_mcp(
    monkeypatch: pytest.MonkeyPatch, tool: str, arguments: dict[str, object]
) -> None:
    """Surface client failures as MCP errors with useful status messages."""
    response = mock_response({})
    monkeypatch.setenv("ANYVAR_ENABLE_REGISTRATION", "true")
    response.status_code = 503
    response.raise_for_status.side_effect = requests.HTTPError(response=response)

    async def call_failed_tool() -> None:
        """Inspect the MCP error result instead of raising on the client."""
        async with Client(mcp) as client:
            result = await client.call_tool(tool, arguments, raise_on_error=False)

        assert result.is_error
        assert (
            f"AnyVar request {tool} failed with HTTP status 503"
            in result.content[0].text
        )

    with patch("anyvar_mcp.clients.anyvar.requests.request", return_value=response):
        asyncio.run(call_failed_tool())


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("register_variant", {"definition": " "}),
        ("search_variants", {"accession": "NC_1", "start": True, "end": 1}),
    ],
    ids=["client-validation", "schema-validation"],
)
def test_validation_errors_through_mcp(
    monkeypatch: pytest.MonkeyPatch, tool: str, arguments: dict[str, object]
) -> None:
    """Reject invalid tool inputs without requesting AnyVar."""

    monkeypatch.setenv("ANYVAR_ENABLE_REGISTRATION", "true")

    async def call_invalid_tool() -> None:
        """Call with invalid inputs and inspect the MCP error."""
        async with Client(mcp) as client:
            result = await client.call_tool(tool, arguments, raise_on_error=False)

        assert result.is_error

    with patch("anyvar_mcp.clients.anyvar.requests.request") as request:
        asyncio.run(call_invalid_tool())

    request.assert_not_called()


def test_registration_disabled_by_default() -> None:
    """Reject registration before it reaches the upstream service."""

    async def call_disabled_tool() -> None:
        """Call registration through MCP with the default settings."""
        async with Client(mcp) as client:
            result = await client.call_tool(
                "register_variant",
                {"definition": "NC_1:g.1A>T"},
                raise_on_error=False,
            )

        assert result.is_error
        assert "ANYVAR_ENABLE_REGISTRATION=true" in result.content[0].text

    with patch("anyvar_mcp.clients.anyvar.requests.request") as request:
        asyncio.run(call_disabled_tool())

    request.assert_not_called()


@pytest.mark.parametrize(
    ("setting", "other_setting"),
    [
        ("ANYVAR_MAX_CALLS_PER_MINUTE", "ANYVAR_MAX_CALLS_PER_HOUR"),
        ("ANYVAR_MAX_CALLS_PER_HOUR", "ANYVAR_MAX_CALLS_PER_MINUTE"),
    ],
)
def test_request_budget_rejects_excess_calls(
    monkeypatch: pytest.MonkeyPatch, setting: str, other_setting: str
) -> None:
    """Reject a second call when either rolling budget is exhausted."""

    monkeypatch.setenv(setting, "1")
    monkeypatch.setenv(other_setting, "10")

    async def call_twice() -> None:
        """Check both call results through the MCP client."""
        async with Client(mcp) as client:
            first = await client.call_tool("get_variant", {"vrs_id": "id"})
            second = await client.call_tool(
                "get_variant", {"vrs_id": "id"}, raise_on_error=False
            )

        assert first.is_error is False
        assert second.is_error
        assert "tool call limit reached" in second.content[0].text

    with patch(
        "anyvar_mcp.clients.anyvar.requests.request",
        return_value=mock_response({"data": {"id": "id"}, "messages": []}),
    ) as request:
        asyncio.run(call_twice())

    request.assert_called_once()


def test_request_budget_recovers_as_windows_expire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restore minute capacity while retaining the rolling hourly limit."""
    monkeypatch.setenv("ANYVAR_MAX_CALLS_PER_MINUTE", "1")
    monkeypatch.setenv("ANYVAR_MAX_CALLS_PER_HOUR", "2")

    async def call_across_windows() -> None:
        """Check admission at the minute and hour expiration boundaries."""
        async with Client(mcp) as client:
            # The first call fills the minute budget, blocking another call.
            clock.monotonic.return_value = 10_000
            first = await client.call_tool("get_variant", {"vrs_id": "id"})
            blocked_minute = await client.call_tool(
                "get_variant", {"vrs_id": "id"}, raise_on_error=False
            )
            assert not first.is_error
            assert blocked_minute.is_error
            assert request.call_count == 1

            # After exactly 60 seconds, minute capacity returns for a second call.
            clock.monotonic.return_value = 10_060
            second = await client.call_tool("get_variant", {"vrs_id": "id"})
            assert not second.is_error

            # The minute has cleared again, but both calls still count this hour.
            clock.monotonic.return_value = 10_120
            blocked_hour = await client.call_tool(
                "get_variant", {"vrs_id": "id"}, raise_on_error=False
            )
            assert blocked_hour.is_error
            assert request.call_count == 2

            # After exactly an hour, the first call expires and frees one slot.
            clock.monotonic.return_value = 13_600
            recovered = await client.call_tool("get_variant", {"vrs_id": "id"})
            assert not recovered.is_error
            assert request.call_count == 3

    # Mock HTTP responses and the server's clock without changing asyncio's clock.
    with (
        patch("anyvar_mcp.server.time") as clock,
        patch(
            "anyvar_mcp.clients.anyvar.requests.request",
            return_value=mock_response({"data": {"id": "id"}, "messages": []}),
        ) as request,
    ):
        asyncio.run(call_across_windows())


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("register_variant", {"definition": " "}),
        ("get_variant", {"vrs_id": " "}),
        ("get_variant_mappings", {"vrs_id": " "}),
        ("search_variants", {"accession": " ", "start": 0, "end": 1}),
        ("search_variants", {"accession": "chr10", "start": 0, "end": 1}),
        ("search_variants", {"accession": "NC_1", "start": 0, "end": 1_000_000}),
        (
            "search_variants",
            {"accession": "NC_1", "start": 0, "end": 1, "cursor": " "},
        ),
    ],
    ids=[
        "blank-definition",
        "blank-object-id",
        "blank-mapping-id",
        "blank-accession",
        "missing-assembly",
        "excessive-span",
        "blank-cursor",
    ],
)
def test_local_validation_preserves_request_budget(
    monkeypatch: pytest.MonkeyPatch, tool: str, arguments: dict[str, object]
) -> None:
    """Allow a valid HTTP request after locally rejecting an invalid tool input."""
    monkeypatch.setenv("ANYVAR_ENABLE_REGISTRATION", "true")
    monkeypatch.setenv("ANYVAR_MAX_CALLS_PER_MINUTE", "1")
    monkeypatch.setenv("ANYVAR_MAX_CALLS_PER_HOUR", "1")
    payload = {"data": {"id": "ga4gh:VA.example"}, "messages": []}

    async def reject_then_retrieve() -> None:
        """Reject invalid input without spending the only available request."""
        async with Client(mcp) as client:
            invalid = await client.call_tool(tool, arguments, raise_on_error=False)
            assert invalid.is_error
            request.assert_not_called()

            valid = await client.call_tool(
                "get_variant", {"vrs_id": "ga4gh:VA.example"}
            )

        assert not valid.is_error
        assert valid.structured_content == payload

    with patch(
        "anyvar_mcp.clients.anyvar.requests.request",
        return_value=mock_response(payload),
    ) as request:
        asyncio.run(reject_then_retrieve())

    request.assert_called_once()


def test_oversized_identifier_is_rejected() -> None:
    """Reject identifiers that exceed the tool schema limit."""

    async def call_with_large_id() -> None:
        """Call the read tool with an oversized identifier."""
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_variant", {"vrs_id": "x" * 513}, raise_on_error=False
            )

        assert result.is_error

    with patch("anyvar_mcp.clients.anyvar.requests.request") as request:
        asyncio.run(call_with_large_id())

    request.assert_not_called()


def test_invalid_timeout_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Surface invalid configuration on invocation while allowing discovery."""
    monkeypatch.setenv("ANYVAR_API_TIMEOUT", "invalid")

    async def call_with_invalid_config() -> None:
        """Discover tools, then inspect the configuration error on invocation."""
        async with Client(mcp) as client:
            assert {tool.name for tool in await client.list_tools()} == TOOL_NAMES
            result = await client.call_tool(
                "get_variant", {"vrs_id": "id"}, raise_on_error=False
            )

        assert result.is_error

    with patch("anyvar_mcp.clients.anyvar.requests.request") as request:
        asyncio.run(call_with_invalid_config())

    request.assert_not_called()


@pytest.mark.parametrize(
    ("configured_size", "pagination", "expected_size"),
    [
        (7, {}, 7),
        (250, {"page_size": None}, 250),
        (7, {"page_size": 3, "cursor": "next-page"}, 3),
    ],
    ids=["configured-default", "configured-large-page", "explicit-override"],
)
def test_search_page_size_through_mcp(
    monkeypatch: pytest.MonkeyPatch,
    configured_size: int,
    pagination: dict[str, str | int | None],
    expected_size: int,
) -> None:
    """Resolve omitted and null page sizes from settings and preserve overrides."""
    monkeypatch.setenv("ANYVAR_SEARCH_PAGE_SIZE", str(configured_size))

    async def search() -> None:
        """Invoke a search with the selected pagination arguments."""
        async with Client(mcp) as client:
            result = await client.call_tool(
                "search_variants",
                {"accession": "NC_1", "start": 0, "end": 1, **pagination},
            )

        assert result.structured_content == {"variations": [], "next_cursor": None}

    with patch(
        "anyvar_mcp.clients.anyvar.requests.request",
        return_value=mock_response({"variations": []}),
    ) as request:
        asyncio.run(search())

    parameters = parse_qs(urlsplit(request.call_args.kwargs["url"]).query)
    assert parameters["page_size"] == [str(expected_size)]
    if "cursor" in pagination:
        assert parameters["cursor"] == [pagination["cursor"]]


def test_console_entry_point() -> None:
    """Check that installation exposes the server's main function."""
    entry_points = distribution("anyvar_mcp").entry_points
    entry_point = next(
        entry
        for entry in entry_points
        if entry.group == "console_scripts" and entry.name == "anyvar-mcp"
    )

    assert entry_point.load() is main
