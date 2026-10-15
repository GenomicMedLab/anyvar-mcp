# Getting started

## Installation

Install from [PyPI](https://pypi.org/project/anyvar_mcp/):

```shell
python3 -m pip install anyvar_mcp
```

## AnyVar setup

This MCP server registers and retrieves variants through AnyVar's HTTP API.
Follow [AnyVar's setup instructions](https://anyvar.readthedocs.io/en/latest/getting_started/index.html)
to start the required HTTP service, then use its URL to configure the MCP server.

### Verifying the AnyVar service

Check your AnyVar service before connecting the MCP server. Set `ANYVAR_API_URL`
to your service's base URL; the example uses the local default. Run the remaining
commands in the same terminal.

```shell
export ANYVAR_API_URL="http://localhost:8000"
```

#### Service info

First, request [service information](https://anyvar.readthedocs.io/en/latest/usage/rest_api.html#get-service-info)
to check that the service responds:

```shell
curl --fail-with-body "${ANYVAR_API_URL%/}/service-info" \
  | python3 -m json.tool --indent 2
```

Expected response excerpt:

```json
{
  "id": "org.biocommons.anyvar",
  "name": "AnyVar",
  "type": {
    "group": "org.biocommons",
    "artifact": "anyvar",
    "version": "1.0.1.dev196+gec3c7651b"
  }
}
```

The full response also includes service metadata, supported data standards, and
dependency information.

!!! warning "AnyVar version compatibility"

    This MCP server targets AnyVar commit
    [`ec3c765`](https://github.com/biocommons/anyvar/commit/ec3c7651b45ac52be3ee3b5809d63d0692904e44).
    Published releases and other commits may return different responses or lack
    endpoints used by this client, so the examples and client operations may fail
    or produce different results. Check your service's version in `/service-info`
    and use the linked commit for the behavior shown in this guide.

!!! tip "Ensure AnyVar service is running"

    If the request fails, check the URL and that the service is running. Open the
    service's base URL in a browser to view its API documentation.

#### Variant registration

[Register a sample variant](https://anyvar.readthedocs.io/en/latest/usage/rest_api.html#basic-variant-operations)
to check processing and storage, and provide a record for the search below:

```shell
curl --fail-with-body --request PUT "${ANYVAR_API_URL%/}/variation" \
  --header 'Content-Type: application/json' \
  --data '{"definition": "NC_000010.11:g.87894077C>T"}' \
  | python3 -m json.tool --indent 2
```

Expected registration response:

```json
{
  "input_variation": {
    "definition": "NC_000010.11:g.87894077C>T",
    "assembly_name": "GRCh38"
  },
  "messages": [],
  "object": {
    "id": "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU",
    "type": "Allele",
    "digest": "K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU",
    "location": {
      "id": "ga4gh:SL.01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy",
      "type": "SequenceLocation",
      "digest": "01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy",
      "sequenceReference": {
        "type": "SequenceReference",
        "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB"
      },
      "start": 87894076,
      "end": 87894077
    },
    "state": {
      "type": "LiteralSequenceExpression",
      "sequence": "T"
    }
  },
  "object_id": "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU"
}
```

#### Variant search

[Search the same interval](https://anyvar.readthedocs.io/en/latest/usage/rest_api.html#searching-variants)
to check that the registered variant can be retrieved:

```shell
curl --fail-with-body --get "${ANYVAR_API_URL%/}/variations" \
  --data-urlencode 'accession=ga4gh:SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB' \
  --data-urlencode 'start=87894070' \
  --data-urlencode 'end=87894080' \
  | python3 -m json.tool --indent 2
```

Expected search response (your database may contain additional matches):

```json
{
  "variations": [
    {
      "id": "ga4gh:VA.K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU",
      "type": "Allele",
      "digest": "K7akyz9PHB0wg8wBNVlWAAdvMbJUJJfU",
      "location": {
        "id": "ga4gh:SL.01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy",
        "type": "SequenceLocation",
        "digest": "01EH5o6V6VEyNUq68gpeTwKE7xOo-WAy",
        "sequenceReference": {
          "type": "SequenceReference",
          "refgetAccession": "SQ.ss8r_wB0-b9r44TQTMmVTI92884QvBiB"
        },
        "start": 87894076,
        "end": 87894077
      },
      "state": {
        "type": "LiteralSequenceExpression",
        "sequence": "T"
      }
    }
  ],
  "next_cursor": "eyJzdGFydCI6ODc4OTQwNzYsImlkIjoiZ2E0Z2g6VkEuSzdha3l6OVBIQjB3Zzh3Qk5WbFdBQWR2TWJKVUpKZlUifQ=="
}
```

The registered allele appears in `variations`.

## MCP server configuration

Set the AnyVar service URL, request timeout, and resource limits through environment
variables or a `.env` file.

Configuration values are resolved in the following order of precedence (highest to lowest):

  1. Environment variables
  2. `.env` file
  3. Defaults

      - `ANYVAR_API_URL`: `http://localhost:8000`
      - `ANYVAR_API_TIMEOUT`: `10` seconds
      - `ANYVAR_SEARCH_PAGE_SIZE`: `100` results (allowed range: 1–10,000)
      - `ANYVAR_MAX_SEARCH_SPAN`: `1000000` positions
      - `ANYVAR_MAX_RESPONSE_BYTES`: `1048576` bytes (1 MiB)

Searches default to at most 100 variants per page to keep results manageable in
conversations. Set `ANYVAR_SEARCH_PAGE_SIZE` in the server's environment or `.env`
file to change this default.

The separate 1 MiB response limit allows room for larger variants
and explicitly requested larger pages while bounding how much data the client reads.

If a page exceeds the limit, lower `ANYVAR_SEARCH_PAGE_SIZE` and restart the server
before starting a new search. Keep the page size unchanged when following
continuation cursors.
Operators can raise
`ANYVAR_MAX_RESPONSE_BYTES` when larger responses are needed.

To configure values using a `.env` file, create one in the directory where you launch
the MCP server:

```dotenv
ANYVAR_API_URL=http://localhost:8000
ANYVAR_API_TIMEOUT=10
ANYVAR_SEARCH_PAGE_SIZE=100
```

To override a value for a single invocation, set the environment variable when launching
the server. For example, to use a 15-second timeout:

```shell
ANYVAR_API_TIMEOUT=15 anyvar-mcp
```
