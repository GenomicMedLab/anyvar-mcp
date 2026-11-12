# Configuration reference

These settings apply to Python and Docker installations. Follow
[Quickstart](quickstart.md) for setup.

Omitted settings use the defaults below.

## AnyVar HTTP Service connection

Choose the AnyVar service to contact and limit how long HTTP connections and
response reads can wait.

| Setting | Default | Description |
| --- | --- | --- |
| `ANYVAR_API_URL` | `http://localhost:8000` | Base URL of your AnyVar service. |
| `ANYVAR_API_TIMEOUT` | `10` seconds | Timeout for the HTTP connection and each response read. |

## Registration

Control whether agents can write to AnyVar.

| Setting | Default | Description |
| --- | --- | --- |
| `ANYVAR_ENABLE_REGISTRATION` | `false` | Allow registration to write objects to AnyVar. |

## Search and response limits

Limit the cost of broad searches and the amount of data returned to agents.
The response size limit applies to all tools.

| Setting | Default | Description |
| --- | --- | --- |
| `ANYVAR_SEARCH_PAGE_SIZE` | `100` results | Search page size when `page_size` is omitted or null, from 1 to 10,000. |
| `ANYVAR_MAX_SEARCH_SPAN` | `1000000` positions | Maximum width of a search interval, including both bounds. |
| `ANYVAR_MAX_RESPONSE_BYTES` | `1048576` bytes (1 MiB) | Maximum response size accepted from AnyVar. Larger responses return an error. |

If a search page exceeds the response limit, lower the page size before starting
a new search. Keep the effective page size unchanged when following continuation
cursors. Raise the response size limit if larger objects or pages are needed.

## Request budgets

Guard against accidental agent loops and request bursts. Each server process
has its own budget, so these limits do not enforce a shared AnyVar service quota.

| Setting | Default | Description |
| --- | --- | --- |
| `ANYVAR_MAX_CALLS_PER_MINUTE` | `30` | Maximum AnyVar calls per server process in a rolling minute. |
| `ANYVAR_MAX_CALLS_PER_HOUR` | `500` | Maximum AnyVar calls per server process in a rolling hour. |

A request must fit within both rolling windows.

## Set configuration values

Set values through environment variables or a `.env` file. Environment variables
take precedence.

Choose the instructions for your setup:

- [Python](python-setup.md): Set environment variables in your agent's MCP configuration.
- [Direct Docker](docker.md#configure-the-container): Pass `-e` arguments or an
  `--env-file` to `docker run`.
- [MCP Toolkit](docker.md#configure-the-server): Set `env` entries in the server
  definition, then [import changes](docker.md#change-toolkit-settings).

Restart the client connection after changing settings.

### Example settings

Use these values in a `.env` file or set them as environment variables.

```dotenv
ANYVAR_API_URL=http://localhost:8000
ANYVAR_API_TIMEOUT=10
ANYVAR_ENABLE_REGISTRATION=true
```
