"""Test AnyVar client requests and response handling with mocked HTTP service."""

from collections.abc import Iterator
from functools import partial
from http import HTTPMethod
from traceback import format_exception
from unittest.mock import MagicMock, patch

import pytest
import requests

from anyvar_mcp.clients.anyvar import AnyVarAPIError, AnyVarClient, AnyVarOperation


@pytest.fixture
def mock_http_response() -> MagicMock:
    """Provide a successful response whose JSON body each test can set."""
    response = MagicMock(spec=requests.Response)
    # _request_json uses `with requests.request(...) as response`.
    # Return this mock from __enter__ so response.json() uses the test's payload.
    response.__enter__.return_value = response
    return response


@pytest.fixture
def mock_http_request(mock_http_response: MagicMock) -> Iterator[MagicMock]:
    """Capture requests and return the mocked response."""
    with patch(
        "anyvar_mcp.clients.anyvar.requests.request", return_value=mock_http_response
    ) as request:
        yield request


def test_get_service_info(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    payload = {
        "name": "AnyVar",
        "version": "1.0.0",
        "spec_metadata": {"vrs_version": "2.0.1"},
        "id": "org.example.anyvar",
    }
    mock_http_response.json.return_value = payload
    client = AnyVarClient("https://anyvar.example/api/", timeout=3)

    result = client.get_service_info()

    # A trailing slash must not create a double slash in the endpoint URL.
    mock_http_request.assert_called_once_with(
        method=HTTPMethod.GET,
        url="https://anyvar.example/api/service-info",
        headers={"Accept": "application/json"},
        json=None,
        timeout=3,
        stream=True,
    )
    # Preserve metadata fields that the client does not define.
    assert result.model_dump() == payload
    mock_http_response.__exit__.assert_called_once()


def test_register_variant(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    definition = "NP_004324.2:p.Val600Glu"
    mock_http_response.json.return_value = {
        "input_variation": {"definition": definition, "assembly_name": "GRCh37"},
        "object": {"id": "ga4gh:VA.example"},
        "object_id": "ga4gh:VA.example",
        "messages": ["Projection unavailable"],
    }

    result = AnyVarClient().register_variant(definition, "GRCh37")

    request = mock_http_request.call_args.kwargs
    assert request["method"] == HTTPMethod.PUT
    assert request["url"].endswith("/variation")
    assert request["json"] == {"definition": definition, "assembly_name": "GRCh37"}
    assert result.object_id == "ga4gh:VA.example"
    assert result.object == {"id": "ga4gh:VA.example"}
    assert result.messages == ["Projection unavailable"]


def test_unresolved_registration(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    # AnyVar can return a translation warning with no registered object.
    mock_http_response.json.return_value = {
        "input_variation": {"definition": "unsupported"},
        "messages": ["Unable to translate unsupported"],
    }

    result = AnyVarClient().register_variant("unsupported")

    assert result.object is None
    assert result.object_id is None
    assert result.messages == ["Unable to translate unsupported"]
    assert mock_http_request.call_args.kwargs["json"]["assembly_name"] == "GRCh38"


def test_get_variant_encodes_identifier(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    # Reserved URL characters must stay inside the identifier.
    vrs_id = "ga4gh:VA.example/a?b#c"
    mock_http_response.json.return_value = {"data": {"id": vrs_id}, "messages": []}

    result = AnyVarClient("https://anyvar.example").get_variant(vrs_id)

    assert mock_http_request.call_args.kwargs["url"] == (
        "https://anyvar.example/object/ga4gh%3AVA.example%2Fa%3Fb%23c"
    )
    assert result.data == {"id": vrs_id}


def test_get_variant_mappings(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    mapping = {
        "source_id": "ga4gh:VA.source",
        "dest_id": "ga4gh:VA.dest",
        "mapping_type": "liftover_to",
    }
    mock_http_response.json.return_value = {"mappings": [mapping]}

    result = AnyVarClient("https://anyvar.example").get_variant_mappings(
        "ga4gh:VA.dest", "liftover_to", as_source=False
    )

    # as_source=False requests incoming mappings.
    assert mock_http_request.call_args.kwargs["url"] == (
        "https://anyvar.example/object/ga4gh%3AVA.dest/mappings"
        "?as_source=false&mapping_type=liftover_to"
    )
    assert result.mappings[0].model_dump() == mapping


def test_get_variant_mappings_without_filter(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    mock_http_response.json.return_value = {"mappings": []}

    result = AnyVarClient("https://anyvar.example").get_variant_mappings("id")

    assert mock_http_request.call_args.kwargs["url"] == (
        "https://anyvar.example/object/id/mappings?as_source=true"
    )
    assert result.mappings == []


def test_search_variants(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    mock_http_response.json.return_value = {
        "variations": [{"id": "ga4gh:VA.example"}],
        "next_cursor": "next-page",
    }

    # Equal endpoints are a valid point search. '&' must stay inside accession.
    result = AnyVarClient("https://anyvar.example").search_variants("NC_1&x=1", 0, 0)

    assert mock_http_request.call_args.kwargs["url"] == (
        "https://anyvar.example/variations"
        "?accession=NC_1%26x%3D1&start=0&end=0&page_size=1000"
    )
    assert result.variations == [{"id": "ga4gh:VA.example"}]
    assert result.next_cursor == "next-page"


def test_search_with_cursor(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    mock_http_response.json.return_value = {"variations": [], "next_cursor": None}

    # Forward the cursor unchanged, including reserved URL characters.
    result = AnyVarClient("https://anyvar.example").search_variants(
        "NC_1", 0, 10, page_size=5, cursor="next+/="
    )

    assert mock_http_request.call_args.kwargs["url"] == (
        "https://anyvar.example/variations"
        "?accession=NC_1&start=0&end=10&page_size=5&cursor=next%2B%2F%3D"
    )
    assert result.variations == []
    assert result.next_cursor is None


def test_blank_registration_definition(mock_http_request: MagicMock) -> None:
    """Reject whitespace-only definitions before requesting AnyVar."""
    with pytest.raises(ValueError, match="definition"):
        AnyVarClient().register_variant(" ")

    mock_http_request.assert_not_called()


def test_blank_variant_identifier(mock_http_request: MagicMock) -> None:
    with pytest.raises(ValueError, match="identifier"):
        AnyVarClient().get_variant(" ")  # Whitespace is not an identifier.

    mock_http_request.assert_not_called()


@pytest.mark.parametrize("vrs_id", ["", " \t\n"])
def test_blank_mapping_identifier(mock_http_request: MagicMock, vrs_id: str) -> None:
    """Reject blank mapping identifiers through the shared path builder."""
    with pytest.raises(ValueError, match="identifier"):
        AnyVarClient().get_variant_mappings(vrs_id)

    mock_http_request.assert_not_called()


@pytest.mark.parametrize(
    ("accession", "start", "end", "page_size", "cursor", "error_message"),
    [
        (" ", 0, 10, 1000, None, "accession"),  # An accession cannot be blank.
        ("NC_1", 0, 10, 1000, " ", "Cursor"),  # Use None when there is no cursor.
    ],
    ids=[
        "blank-accession",
        "blank-cursor",
    ],
)
def test_invalid_search_inputs(
    mock_http_request: MagicMock,
    accession: str,
    start: int,
    end: int,
    page_size: int,
    cursor: str | None,
    error_message: str,
) -> None:
    """Reject blank accessions and cursors before requesting AnyVar."""
    with pytest.raises(ValueError, match=error_message):
        AnyVarClient().search_variants(
            accession, start, end, page_size=page_size, cursor=cursor
        )

    mock_http_request.assert_not_called()


@pytest.mark.parametrize(
    "operation",
    [
        AnyVarOperation.REGISTER_VARIANT,
        AnyVarOperation.GET_VARIANT_MAPPINGS,
        AnyVarOperation.SEARCH_VARIANTS,
    ],
)
def test_request_validation_delegated_to_anyvar(
    mock_http_request: MagicMock,
    mock_http_response: MagicMock,
    operation: AnyVarOperation,
) -> None:
    """Surface upstream validation failures for values the client forwards."""
    mock_http_response.status_code = 422
    mock_http_response.raise_for_status.side_effect = requests.HTTPError(
        response=mock_http_response
    )
    client = AnyVarClient()
    request = {
        AnyVarOperation.REGISTER_VARIANT: partial(
            client.register_variant, "variant", "GRCh36"
        ),
        AnyVarOperation.GET_VARIANT_MAPPINGS: partial(
            client.get_variant_mappings, "id", "unknown"
        ),
        AnyVarOperation.SEARCH_VARIANTS: partial(
            client.search_variants, "NC_1", 10, -1, page_size=10001
        ),
    }[operation]

    with pytest.raises(AnyVarAPIError) as caught:
        request()

    assert caught.value.operation is operation
    assert caught.value.status_code == 422
    mock_http_request.assert_called_once()


def test_http_error(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    mock_http_response.status_code = 404
    mock_http_response.raise_for_status.side_effect = requests.HTTPError(
        "secret-upstream-detail", response=mock_http_response
    )

    with pytest.raises(AnyVarAPIError) as caught:
        AnyVarClient().get_variant("missing-id")

    assert caught.value.operation is AnyVarOperation.GET_VARIANT
    assert caught.value.status_code == 404
    # Upstream errors may contain credentials or private data.
    assert "secret-upstream-detail" not in "".join(format_exception(caught.value))
    mock_http_response.__exit__.assert_called_once()
    mock_http_request.assert_called_once()


@pytest.mark.parametrize("error_type", [requests.ConnectionError, requests.Timeout])
def test_connection_failure(
    mock_http_request: MagicMock, error_type: type[Exception]
) -> None:
    mock_http_request.side_effect = error_type("connection failed")

    with pytest.raises(AnyVarAPIError) as caught:
        AnyVarClient().get_service_info()

    assert caught.value.operation is AnyVarOperation.SERVICE_INFO
    assert caught.value.status_code is None


def test_response_read_timeout(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    # A connection can succeed and then time out while reading the body.
    mock_http_response.json.side_effect = requests.ReadTimeout("read timed out")

    with pytest.raises(AnyVarAPIError):
        AnyVarClient().get_service_info()

    mock_http_response.__exit__.assert_called_once()
    mock_http_request.assert_called_once()


def test_invalid_json(
    mock_http_request: MagicMock, mock_http_response: MagicMock
) -> None:
    mock_http_response.json.side_effect = requests.exceptions.JSONDecodeError(
        "Invalid JSON", "not JSON", 0
    )

    with pytest.raises(AnyVarAPIError, match="invalid JSON"):
        AnyVarClient().get_service_info()

    mock_http_response.__exit__.assert_called_once()
    mock_http_request.assert_called_once()


@pytest.mark.parametrize(
    ("operation", "payload"),
    [
        (AnyVarOperation.SEARCH_VARIANTS, []),  # The response must be a JSON object.
        (AnyVarOperation.SEARCH_VARIANTS, {}),  # The variations field is required.
        # Each variation must be an object. Keep private data out of validation errors.
        (
            AnyVarOperation.SEARCH_VARIANTS,
            {"variations": [1], "private_note": "secret-upstream-payload"},
        ),
        (AnyVarOperation.REGISTER_VARIANT, {"messages": []}),  # Input is required.
        (AnyVarOperation.GET_VARIANT, {"data": None, "messages": []}),  # No object.
        (
            AnyVarOperation.GET_VARIANT_MAPPINGS,
            {"mappings": [{"mapping_type": "liftover_to"}]},  # Missing related IDs.
        ),
    ],
    ids=[
        "not-an-object",
        "missing-variations",
        "invalid-variation",
        "missing-registration-input",
        "null-object",
        "missing-mapping-ids",
    ],
)
def test_invalid_response(
    mock_http_request: MagicMock,
    mock_http_response: MagicMock,
    operation: AnyVarOperation,
    payload: object,
) -> None:
    mock_http_response.json.return_value = payload
    client = AnyVarClient()
    # Bind the operation and its arguments so pytest.raises contains only one call.
    request = {
        AnyVarOperation.REGISTER_VARIANT: partial(
            client.register_variant, "NC_000010.11:g.87894077C>T"
        ),
        AnyVarOperation.GET_VARIANT: partial(client.get_variant, "ga4gh:VA.example"),
        AnyVarOperation.GET_VARIANT_MAPPINGS: partial(
            client.get_variant_mappings, "ga4gh:VA.example"
        ),
        AnyVarOperation.SEARCH_VARIANTS: partial(client.search_variants, "NC_1", 0, 10),
    }[operation]

    with pytest.raises(AnyVarAPIError) as caught:
        request()

    assert caught.value.operation is operation
    assert caught.value.status_code is None
    assert "secret-upstream-payload" not in "".join(format_exception(caught.value))
    mock_http_response.__exit__.assert_called_once()
    mock_http_request.assert_called_once()


@pytest.mark.parametrize(
    "base_url",
    [
        "localhost:8000",  # The service URL requires an HTTP or HTTPS scheme.
        "https://",  # A scheme alone does not identify a host.
        "https://user:pass@host",  # Credentials cannot be embedded in the URL.
        "https://host/?q=1",  # A base URL cannot contain endpoint query parameters.
    ],
    ids=["missing-scheme", "missing-host", "credentials", "query-string"],
)
def test_invalid_url(base_url: str) -> None:
    with pytest.raises(ValueError, match="URL"):
        AnyVarClient(base_url)


@pytest.mark.parametrize(
    "timeout",
    [
        0,  # The timeout must be positive.
        float("inf"),  # A finite timeout prevents requests from waiting indefinitely.
    ],
)
def test_invalid_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        AnyVarClient(timeout=timeout)
