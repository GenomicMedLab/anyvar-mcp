"""Access the AnyVar HTTP API.

Local client and response models avoid AnyVar's server dependencies.
AnyVar validates request values; the client enforces local search policies
and rejects blank strings.
See https://github.com/GenomicMedLab/anyvar-mcp/discussions/10.
"""

import json
import math
import re
from collections.abc import Mapping
from enum import StrEnum
from http import HTTPMethod
from types import MappingProxyType
from urllib.parse import quote, urlencode, urlsplit

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from anyvar_mcp.config import Settings

ANYVAR_SEARCH_PAGE_SIZE = 1000
RESPONSE_CHUNK_SIZE = 65_536  # 64 KiB


class Assembly(StrEnum):
    """Reference assemblies supported for registration."""

    GRCH37 = "GRCh37"
    GRCH38 = "GRCh38"


class MappingType(StrEnum):
    """Supported mapping filters.

    * ``LIFTOVER_TO``: Genomic-to-genomic coordinate transformation. Use when mapping
      a variation between two reference sequences of the same molecule type, typically
      genomic DNA.
    * ``TRANSCRIBE_TO``: Genomic-to-transcript (RNA/cDNA) projection. Use when projecting
      a genomic DNA object onto a transcript sequence (RNA or cDNA). This accounts for
      splicing, transcript strand orientation, and transcript-specific exon structure.
    * ``TRANSLATE_TO``: Transcript-to-protein projection. This entails codon interpretation,
      amino acid substitution/insertion/deletion/extension, and protein coordinate changes.
    """

    LIFTOVER_TO = "liftover_to"
    TRANSCRIBE_TO = "transcribe_to"
    TRANSLATE_TO = "translate_to"


class AnyVarEndpoint(StrEnum):
    """Supported AnyVar API endpoints."""

    SERVICE_INFO = "/service-info"
    VARIATION = "/variation"
    OBJECT = "/object/{vrs_id}"
    MAPPINGS = "/object/{vrs_id}/mappings"
    VARIATIONS = "/variations"


class AnyVarOperation(StrEnum):
    """Supported AnyVar client operations."""

    SERVICE_INFO = "get_service_info"
    REGISTER_VARIANT = "register_variant"
    GET_VARIANT = "get_variant"
    GET_VARIANT_MAPPINGS = "get_variant_mappings"
    SEARCH_VARIANTS = "search_variants"


ENDPOINT_TO_OPERATION = MappingProxyType(
    {
        AnyVarEndpoint.SERVICE_INFO: AnyVarOperation.SERVICE_INFO,
        AnyVarEndpoint.VARIATION: AnyVarOperation.REGISTER_VARIANT,
        AnyVarEndpoint.OBJECT: AnyVarOperation.GET_VARIANT,
        AnyVarEndpoint.MAPPINGS: AnyVarOperation.GET_VARIANT_MAPPINGS,
        AnyVarEndpoint.VARIATIONS: AnyVarOperation.SEARCH_VARIANTS,
    }
)


type JSONObject = dict[str, object]
type JSONValue = (
    str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]
)


def _is_nonempty_string(value: object, error_message: str) -> None:
    """Require a nonempty string.

    :param value: Value that must be a nonempty string.
    :param error_message: Error message for invalid input.
    :raise ValueError: If the input is not a string or contains only whitespace.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(error_message)


class AnyVarResponse(BaseModel):
    """Validate AnyVar response types while preserving additional upstream fields."""

    model_config = ConfigDict(strict=True, extra="allow")


class ServiceInfoResponse(AnyVarResponse):
    """Describe the AnyVar service and its supported data standards."""

    name: str
    version: str
    spec_metadata: dict[str, object] = Field(default_factory=dict)


class RegistrationResponse(AnyVarResponse):
    """Describe AnyVar registration, including unresolved inputs."""

    input_variation: JSONObject
    messages: list[str]
    object: JSONObject | None = None
    object_id: str | None = None


class ObjectResponse(AnyVarResponse):
    """Describe a retrieved VRS object and upstream messages."""

    data: dict[str, object]
    messages: list[str]


class VariationMapping(AnyVarResponse):
    """Describe a directed relationship between registered variations."""

    source_id: str
    dest_id: str
    mapping_type: str


class MappingResponse(AnyVarResponse):
    """Describe available directed mappings for a VRS object."""

    mappings: list[VariationMapping]


class SearchResponse(AnyVarResponse):
    """Describe a page of registered variants and its continuation cursor."""

    variations: list[dict[str, object]]
    next_cursor: str | None = None


class AnyVarAPIError(Exception):
    """An AnyVar request failed or returned an invalid response."""

    def __init__(
        self,
        message: str,
        *,
        operation: AnyVarOperation,
        status_code: int | None = None,
    ) -> None:
        """Describe an upstream failure and retain its request context.

        :param message: Human-readable failure description.
        :param operation: Client operation that failed.
        :param status_code: HTTP error status, or None for other failures.
        """
        super().__init__(message)
        self.operation = operation
        self.status_code = status_code


class AnyVarClient:
    """Make requests to an AnyVar HTTP service."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        *,
        max_search_span: int | None = None,
        max_response_bytes: int | None = None,
    ) -> None:
        """Configure the service URL and request timeout.

        :param base_url: HTTP or HTTPS AnyVar service URL, optionally with a path prefix.
        :param timeout: Positive, finite connect and read timeout in seconds.
        :param max_search_span: Maximum inclusive search interval width.
        :param max_response_bytes: Maximum upstream response body size in bytes.
        :raise ValueError: If the URL or timeout is invalid.
        """
        if any(
            value is None
            for value in (base_url, timeout, max_search_span, max_response_bytes)
        ):
            settings = Settings()
            if base_url is None:
                base_url = settings.anyvar_api_url
            if timeout is None:
                timeout = settings.anyvar_api_timeout
            if max_search_span is None:
                max_search_span = settings.anyvar_max_search_span
            if max_response_bytes is None:
                max_response_bytes = settings.anyvar_max_response_bytes

        url_error_message = (
            "AnyVar API URL must be HTTP(S) without credentials, query, or fragment."
        )
        try:
            parsed_url = urlsplit(base_url)
        except ValueError:
            raise ValueError(url_error_message) from None

        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
            or parsed_url.query
            or parsed_url.fragment
            or parsed_url.username is not None
            or parsed_url.password is not None
        ):
            raise ValueError(url_error_message)

        if not math.isfinite(timeout) or timeout <= 0:
            error_message = "AnyVar API timeout must be positive and finite."
            raise ValueError(error_message)
        if type(max_search_span) is not int or max_search_span <= 0:
            error_message = "Maximum search span must be a positive integer."
            raise ValueError(error_message)
        if type(max_response_bytes) is not int or max_response_bytes <= 0:
            error_message = "Maximum response bytes must be a positive integer."
            raise ValueError(error_message)

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_search_span = max_search_span
        self.max_response_bytes = max_response_bytes

    def _request_json[ResponseT: AnyVarResponse](
        self,
        endpoint: AnyVarEndpoint,
        response_model: type[ResponseT],
        *,
        vrs_id: str | None = None,
        query_parameters: Mapping[str, str | int] | None = None,
        http_method: HTTPMethod = HTTPMethod.GET,
        json_body: dict[str, JSONValue] | None = None,
    ) -> ResponseT:
        """Request JSON from the HTTP service and validate the response model.

        :param endpoint: API endpoint and key for operation error context.
        :param response_model: Expected response model.
        :param vrs_id: Object identifier for object and mapping endpoints.
        :param query_parameters: Optional query parameters to encode.
        :param http_method: HTTP request method.
        :param json_body: Optional JSON request body.
        :return: Validated response model.
        :raise ValueError: If an object or mapping endpoint identifier is invalid.
        :raise AnyVarAPIError: If the request fails or response does not match the
            expected schema.
        """
        operation = ENDPOINT_TO_OPERATION[endpoint]
        path = (
            self._build_object_path(endpoint, vrs_id)
            if endpoint in {AnyVarEndpoint.OBJECT, AnyVarEndpoint.MAPPINGS}
            else endpoint.value
        )
        if query_parameters:
            path = f"{path}?{urlencode(query_parameters)}"

        try:
            with requests.request(
                method=http_method,
                url=f"{self.base_url}{path}",
                headers={"Accept": "application/json"},
                json=json_body,
                timeout=self.timeout,
                stream=True,
                allow_redirects=False,
            ) as response:
                if response.is_redirect:
                    error_message = f"AnyVar request {operation} was redirected."
                    raise AnyVarAPIError(error_message, operation=operation)
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_content(RESPONSE_CHUNK_SIZE):
                    body.extend(chunk)
                    if len(body) > self.max_response_bytes:
                        error_message = (
                            f"AnyVar request {operation} response exceeds the "
                            f"{self.max_response_bytes}-byte limit."
                        )
                        raise AnyVarAPIError(error_message, operation=operation)
                payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeError):
            error_message = f"AnyVar request {operation} returned invalid JSON."
            raise AnyVarAPIError(error_message, operation=operation) from None
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            error_message = (
                f"AnyVar request {operation} failed with HTTP status {status_code}."
            )
            raise AnyVarAPIError(
                error_message, operation=operation, status_code=status_code
            ) from None
        except requests.RequestException:
            error_message = f"Unable to complete the AnyVar request {operation}."
            raise AnyVarAPIError(error_message, operation=operation) from None

        if not isinstance(payload, dict):
            error_message = (
                f"AnyVar request {operation} response must be a JSON object."
            )
            raise AnyVarAPIError(error_message, operation=operation)

        try:
            return response_model.model_validate(payload)
        except ValidationError:
            error_message = f"AnyVar request {operation} response does not match the expected schema."
            raise AnyVarAPIError(error_message, operation=operation) from None

    @staticmethod
    def _build_object_path(endpoint: AnyVarEndpoint, vrs_id: str | None) -> str:
        """Build an object endpoint path with an encoded identifier.

        :param endpoint: Object or mapping endpoint.
        :param vrs_id: Registered VRS object identifier.
        :return: Encoded object endpoint path.
        :raise ValueError: If the identifier is not a nonempty string.
        """
        if not isinstance(vrs_id, str) or not vrs_id.strip():
            error_message = "A nonempty VRS identifier is required."
            raise ValueError(error_message)
        return endpoint.format(vrs_id=quote(vrs_id, safe=""))

    def get_service_info(self) -> ServiceInfoResponse:
        """Retrieve service metadata.

        :return: Service name, version, data standards, and additional metadata.
        :raise AnyVarAPIError: If the request fails or response does not match the
            expected schema.
        """
        return self._request_json(AnyVarEndpoint.SERVICE_INFO, ServiceInfoResponse)

    def register_variant(
        self, definition: str, assembly_name: Assembly | str = Assembly.GRCH38
    ) -> RegistrationResponse:
        """Normalize supported nomenclature and register the resulting variant.

        Registration can also create liftover and projection mappings. If the
        response lacks an object or identifier, check its messages for unresolved
        input.

        :param definition: Supported HGVS, SPDI, or gnomAD expression.
        :param assembly_name: Reference assembly, used for gnomAD expressions.
        :return: Input, VRS object and identifier when resolved, and messages.
        :raises ValueError: If the definition is blank.
        :raise AnyVarAPIError: If the request fails or response does not match the
            expected schema.
        """
        _is_nonempty_string(definition, "A nonempty variant definition is required.")

        return self._request_json(
            AnyVarEndpoint.VARIATION,
            RegistrationResponse,
            http_method=HTTPMethod.PUT,
            json_body={"definition": definition, "assembly_name": assembly_name},
        )

    def get_variant(self, vrs_id: str) -> ObjectResponse:
        """Retrieve a registered VRS object by identifier.

        :param vrs_id: Registered VRS object identifier.
        :return: VRS object and upstream messages.
        :raise ValueError: If the identifier is invalid.
        :raise AnyVarAPIError: If the request fails or response does not match the
            expected schema.
        """
        return self._request_json(AnyVarEndpoint.OBJECT, ObjectResponse, vrs_id=vrs_id)

    def get_variant_mappings(
        self,
        vrs_id: str,
        mapping_type: MappingType | str | None = None,
        *,
        as_source: bool = True,
    ) -> MappingResponse:
        """Retrieve directed mappings associated with a registered VRS object.

        :param vrs_id: Registered VRS object identifier.
        :param mapping_type: Optional relationship type to filter.
        :param as_source: Retrieve outgoing mappings if true, incoming otherwise.
        :return: Available mappings, including an empty list when none are stored.
        :raises ValueError: If the identifier is blank.
        :raise AnyVarAPIError: If the request fails or response does not match the
            expected schema.
        """
        query_parameters = {"as_source": str(as_source).lower()}
        if mapping_type is not None:
            query_parameters["mapping_type"] = mapping_type

        return self._request_json(
            AnyVarEndpoint.MAPPINGS,
            MappingResponse,
            vrs_id=vrs_id,
            query_parameters=query_parameters,
        )

    def search_variants(
        self,
        accession: str,
        start: int,
        end: int,
        page_size: int = ANYVAR_SEARCH_PAGE_SIZE,
        cursor: str | None = None,
    ) -> SearchResponse:
        """Fetch one page of variants overlapping a closed reference interval.

        :param accession: Assembly-qualified chromosome alias or sequence accession
            recognized by AnyVar.
        :param start: Nonnegative, inclusive inter-residue start coordinate.
        :param end: Inclusive inter-residue end coordinate, at least start.
        :param page_size: Maximum results per page, from 1 to 10000. Keep this
            unchanged when following cursors for the same search.
        :param cursor: Opaque ``next_cursor`` from the preceding response.
        :return: AnyVar response with ``variations`` and an optional ``next_cursor``.
        :raises ValueError: If the accession or supplied cursor is blank, the
            chromosome lacks an assembly, or the interval exceeds the span limit.
        :raise AnyVarAPIError: If the request fails or the response does not match the
            expected schema.
        """
        _is_nonempty_string(accession, "A nonempty sequence accession is required.")
        # AnyVar resolves accessions upstream. This MCP policy requires callers
        # to specify an assembly for bare chromosome names before searching.
        if re.fullmatch(
            r"(?i)(?:chromosome\s*|chr)?(?:[1-9]|1[0-9]|2[0-2]|X|Y|MT)",
            accession.strip(),
        ):
            error_message = (
                "Chromosome searches require GRCh37 or GRCh38. Use an "
                "assembly-qualified accession such as GRCh38:chr10."
            )
            raise ValueError(error_message)

        # AnyVar caps page size but has no interval-width limit. This configurable
        # MCP limit restricts broad queries; pagination alone does not bound query cost.
        if end - start + 1 > self.max_search_span:
            error_message = (
                f"Search interval exceeds the {self.max_search_span}-position limit."
            )
            raise ValueError(error_message)

        if cursor is not None:
            _is_nonempty_string(cursor, "Cursor must be a nonempty string or None.")

        query_parameters: dict[str, str | int] = {
            "accession": accession,
            "start": start,
            "end": end,
            "page_size": page_size,
        }
        if cursor is not None:
            query_parameters["cursor"] = cursor

        return self._request_json(
            AnyVarEndpoint.VARIATIONS,
            SearchResponse,
            query_parameters=query_parameters,
        )
