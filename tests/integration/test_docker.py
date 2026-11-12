"""Test the built container over stdio with a local HTTP server.

Set ANYVAR_MCP_TEST_IMAGE to opt in after building the image.
"""

import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import unquote

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

IMAGE = os.environ.get("ANYVAR_MCP_TEST_IMAGE")
pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not IMAGE, reason="Set ANYVAR_MCP_TEST_IMAGE to test Docker"),
]


def test_container_discovery_and_registration_disabled() -> None:
    """List the required tools and reject writes by default without API access."""
    transport = StdioTransport(
        command="docker",
        args=[
            "run",
            "--rm",
            "-i",
            "--network=none",
            IMAGE,
        ],
        keep_alive=False,
    )

    async def check_server() -> None:
        """Check tool discovery and that registration is disabled by default."""
        async with asyncio.timeout(60), Client(transport) as client:
            tool_names = {tool.name for tool in await client.list_tools()}
            assert {
                "register_variant",
                "get_variant",
                "search_variants",
                "get_variant_mappings",
            } <= tool_names

            result = await client.call_tool(
                "register_variant", {"definition": "NC_1:g.1A>T"}, raise_on_error=False
            )
            assert result.is_error
            assert "Variant registration is disabled" in result.content[0].text

    asyncio.run(check_server())


def test_container_reads_and_registers_with_configured_api() -> None:
    """Read and register through the configured API with registration enabled."""
    payload = {"data": {"id": "ga4gh:VA.example", "type": "Allele"}, "messages": []}
    definition = "NC_000010.11:g.87894077C>T"
    registration = {
        "input_variation": {"definition": definition, "assembly_name": "GRCh38"},
        "object": payload["data"],
        "object_id": "ga4gh:VA.example",
        "messages": [],
    }
    requests = []

    class Handler(BaseHTTPRequestHandler):
        """Serve reads and record registration requests from the container."""

        def do_GET(self) -> None:
            """Return the object only at the configured API path."""
            # The /api prefix catches URL joins that discard the base path.
            if unquote(self.path) != "/api/object/ga4gh:VA.example":
                self.send_error(404)
                return

            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_PUT(self) -> None:
            """Record the request and return a successful registration response."""
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, request))
            body = json.dumps(registration).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    # Container traffic needs a non-loopback listener; port 0 avoids port conflicts.
    with ThreadingHTTPServer(("0.0.0.0", 0), Handler) as httpd:  # noqa: S104
        worker = Thread(target=httpd.serve_forever, daemon=True)
        worker.start()
        transport = StdioTransport(
            command="docker",
            args=[
                "run",
                "--rm",
                "-i",
                # Linux Docker Engine needs an explicit mapping to the host.
                "--add-host=host.docker.internal:host-gateway",
                "-e",
                f"ANYVAR_API_URL=http://host.docker.internal:{httpd.server_port}/api",
                "-e",
                "ANYVAR_ENABLE_REGISTRATION=true",
                "-e",
                "NO_PROXY=host.docker.internal",
                IMAGE,
            ],
            keep_alive=False,
        )

        async def retrieve() -> None:
            """Read an object and register a variant with registration enabled."""
            async with asyncio.timeout(60), Client(transport) as client:
                result = await client.call_tool(
                    "get_variant", {"vrs_id": "ga4gh:VA.example"}
                )
                assert result.structured_content == payload

                result = await client.call_tool(
                    "register_variant", {"definition": definition}
                )
                assert result.structured_content == registration
                assert requests == [
                    (
                        "/api/variation",
                        {"definition": definition, "assembly_name": "GRCh38"},
                    )
                ]

        try:
            asyncio.run(retrieve())
        finally:
            httpd.shutdown()
            worker.join(timeout=5)
