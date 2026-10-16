# Dependencies

## Start the AnyVar HTTP API

The MCP server uses AnyVar's HTTP API to register and retrieve variants. Follow
[AnyVar's setup instructions](https://anyvar.readthedocs.io/en/latest/getting_started/index.html)
to start the HTTP API. Keep it running while you use the MCP tools.

### AnyVar compatibility

This MCP server targets AnyVar commit
[`ec3c765`](https://github.com/biocommons/anyvar/commit/ec3c7651b45ac52be3ee3b5809d63d0692904e44).
Other versions may return different responses or lack required endpoints. Check
your service's version at `/service-info` before using the examples.

### Check the AnyVar HTTP API

Follow these steps to check that the AnyVar HTTP API is running correctly and
can register a variant.

Set `ANYVAR_API_URL` to your service's base URL. Run these commands in the same
terminal:

```shell
export ANYVAR_API_URL="http://localhost:8000"
```

Request [service information](https://anyvar.readthedocs.io/en/latest/usage/rest_api.html#get-service-info):

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
dependency information. Check the version against the [supported AnyVar
commit](#anyvar-compatibility).

!!! tip "Ensure AnyVar service is running"

    If the request fails, check the URL and that the service is running. Open the
    service's base URL in a browser to view its API documentation.

#### Register a variant

[Register a sample variant](https://anyvar.readthedocs.io/en/latest/usage/rest_api.html#basic-variant-operations)
to check processing and storage:

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

Return to the [quickstart](quickstart.md) to install and connect the MCP server.
