"""Run the AnyVar MCP server."""

import time
from collections import deque
from functools import partial
from threading import Lock
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from anyvar_mcp import __version__
from anyvar_mcp.clients.anyvar import (
    AnyVarAPIError,
    AnyVarClient,
    Assembly,
    MappingResponse,
    MappingType,
    ObjectResponse,
    RegistrationResponse,
    SearchResponse,
)
from anyvar_mcp.config import Settings

SERVER_NAME = "anyvar-mcp"
SERVER_INSTRUCTIONS = (
    "Use AnyVar results as source data and preserve upstream messages and "
    "warnings. Preserve VRS start/end values exactly as returned and label their "
    "coordinate system as 'inter-residue', never 'zero-based'. Answer only questions "
    "supported by the MCP server's tools. If unsupported, explicitly state that the "
    "server cannot answer. If supported but context is insufficient, ask a focused "
    "clarifying question instead of guessing."
)
MCP_SEARCH_MAX_PAGE_SIZE = 10_000
MAX_DEFINITION_LENGTH = 4096
MAX_IDENTIFIER_LENGTH = 512
MAX_CURSOR_LENGTH = 2048


class _RequestBudget:
    """Limit AnyVar traffic from this server process in rolling time windows.

    This guardrail caps aggregate tool traffic to help prevent accidental or
    automated call bursts from overloading AnyVar or consuming its resources.

    The minute and hour limits are configurable through ``ANYVAR_MAX_CALLS_PER_MINUTE``
    and ``ANYVAR_MAX_CALLS_PER_HOUR``.
    """

    def __init__(self) -> None:
        """Initialize the call history and its lock."""
        self._calls: deque[float] = (
            deque()
        )  # Elapsed-time timestamps of reserved calls.
        self._lock = Lock()  # Protects call history during concurrent tool requests.

    def reserve(self, settings: Settings) -> None:
        """Reserve one call before requesting AnyVar.

        :param settings: Rolling minute and hour call limits.
        :raises ToolError: If either call limit has been reached.
        """
        with self._lock:
            now = time.monotonic()
            while self._calls and self._calls[0] <= now - 3600:
                self._calls.popleft()

            hour_count = len(self._calls)
            minute_count = sum(call > now - 60 for call in self._calls)

            if (
                minute_count >= settings.anyvar_max_calls_per_minute
                or hour_count >= settings.anyvar_max_calls_per_hour
            ):
                error_message = "AnyVar tool call limit reached. Try again later."
                raise ToolError(error_message)

            self._calls.append(now)


_request_budget = _RequestBudget()

mcp = FastMCP(
    name=SERVER_NAME,
    version=__version__,
    instructions=SERVER_INSTRUCTIONS,
)


def _get_client(settings: Settings | None = None) -> AnyVarClient:
    """Create a lightweight client for each tool call.

    Load settings at call time so configuration errors surface through the tool.

    Clients hold no persistent HTTP session; all share the process request budget.

    :param settings: Validated settings, loaded from the environment if omitted.
    :return: Client using the configured AnyVar service and resource limits.
    :raises ValueError: If client configuration is invalid.
    """
    settings = settings or Settings()
    return AnyVarClient(
        settings=settings, request_guard=partial(_request_budget.reserve, settings)
    )


# Tool schemas expose constraints to MCP callers and reject invalid arguments
# before HTTP requests. The client retains blank-string checks because min_length
# accepts whitespace-only strings. AnyVar handles API request validation.
@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": True,
    },
)
def register_variant(
    definition: Annotated[str, Field(min_length=1, max_length=MAX_DEFINITION_LENGTH)],
    assembly_name: Assembly = Assembly.GRCH38,
) -> RegistrationResponse:
    """Normalize supported HGVS, SPDI, or gnomAD nomenclature and write to AnyVar.

    Registration is disabled unless ``ANYVAR_ENABLE_REGISTRATION`` is true.

    Registration may also create liftover/projection objects and mappings.

    HTTP connection and read timeouts still apply.

    Ask for clarification when the expression, reference accession, or assembly
    is ambiguous. Do not invent an accession or infer a unique genomic variant
    from a protein-only change.

    Missing object/object_id means unresolved input, even when the HTTP request
    succeeded. Report messages, including partial-result warnings.

    :param definition: Supported variant expression.
    :param assembly_name: Reference assembly used for gnomAD expressions.
    :return: Input, normalized VRS object and ID when resolved, and messages.
    :raises ToolError: If configuration, validation, or the HTTP request fails.
    """
    try:
        settings = Settings()
        if not settings.anyvar_enable_registration:
            error_message = (
                "Variant registration is disabled. Set ANYVAR_ENABLE_REGISTRATION=true "
                "in the server environment to enable it."
            )
            raise ToolError(error_message)

        return _get_client(settings).register_variant(definition, assembly_name)
    except (ValueError, AnyVarAPIError) as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def get_variant(
    vrs_id: Annotated[str, Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)],
) -> ObjectResponse:
    """Retrieve a registered VRS object, including objects referenced by mappings.

    Report any VRS ``start`` and ``end`` values as inter-residue coordinates,
    preserving the returned values.

    :param vrs_id: VRS identifier of the registered object.
    :return: VRS object and upstream messages.
    :raises ToolError: If configuration, validation, or retrieval fails.
    """
    try:
        return _get_client().get_variant(vrs_id)
    except (ValueError, AnyVarAPIError) as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def search_variants(
    accession: Annotated[str, Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)],
    start: Annotated[int, Field(strict=True, ge=0)],
    end: Annotated[int, Field(strict=True, ge=0)],
    page_size: Annotated[int, Field(strict=True, ge=1, le=MCP_SEARCH_MAX_PAGE_SIZE)]
    | None = None,
    cursor: Annotated[str, Field(min_length=1, max_length=MAX_CURSOR_LENGTH)]
    | None = None,
) -> SearchResponse:
    """Search registered variants using inclusive inter-residue bounds.

    The returned VRS objects use inter-residue ``start`` and ``end`` values;
    preserve them when reporting results.

    This queries the registry; it does not resolve a variant expression.

    Only variants already registered with AnyVar can be returned. An empty result
    does not establish that no variant exists in the interval.

    Use an assembly stated or clearly established in the conversation. If none
    is available, ask whether the user means GRCh37 or GRCh38, then pass an
    alias such as GRCh38:chr10 as accession.

    :param accession: Assembly-qualified chromosome alias or sequence accession
        recognized by AnyVar.
    :param start: Nonnegative inclusive start coordinate.
    :param end: Inclusive end coordinate, at least start.
    :param page_size: Maximum results per page, from 1 to 10000. Omit or pass
        None to use ANYVAR_SEARCH_PAGE_SIZE. Keep the effective page size
        unchanged when following continuation cursors.
    :param cursor: Opaque next_cursor from the preceding page.
    :return: Variation objects and an optional continuation cursor; the next page
        may be empty.
    :raises ToolError: If configuration, validation, or search fails.
    """
    try:
        return _get_client().search_variants(accession, start, end, page_size, cursor)
    except (ValueError, AnyVarAPIError) as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
def get_variant_mappings(
    vrs_id: Annotated[str, Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)],
    mapping_type: MappingType | None = None,
    as_source: Annotated[bool, Field(strict=True)] = True,
) -> MappingResponse:
    """Read stored liftover, transcription, or translation mappings for a VRS object.

    Mappings are directed. For outgoing mappings, vrs_id is the source_id and
    dest_id identifies the mapped object. For incoming mappings, vrs_id is the
    dest_id and source_id identifies the mapped object. Name both roles when
    reporting a mapping. Use get_variant on source_id to retrieve the source
    VRS object, or on dest_id to retrieve the destination VRS object.

    Availability depends on stored mappings and AnyVar's configured capabilities.
    Empty mappings do not rule out biological relations or guarantee complete
    genomic, transcript, protein, or MANE context.

    :param vrs_id: VRS identifier of the registered object.
    :param mapping_type: Optional liftover_to, transcribe_to, or translate_to filter.
    :param as_source: True when vrs_id is the source; false when it is the destination.
    :return: Directed mappings with source IDs, destination IDs, and types.
    :raises ToolError: If configuration, validation, or mapping retrieval fails.
    """
    try:
        return _get_client().get_variant_mappings(
            vrs_id, mapping_type, as_source=as_source
        )
    except (ValueError, AnyVarAPIError) as exc:
        raise ToolError(str(exc)) from exc


def main() -> None:
    """Run the MCP server over standard input and output."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
