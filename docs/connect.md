# Connect your AI agent

## Prerequisites

First, install the AI client you want to use: [Claude Desktop](https://support.claude.com/en/articles/10065433-install-claude-desktop) or [Codex CLI](https://learn.chatgpt.com/docs/codex/cli#getting-started).

Then [install `anyvar-mcp`](quickstart.md#install-the-mcp-server) and start the
[AnyVar HTTP API](dependencies.md). Keep the API running while you use the tools.
The client starts `anyvar-mcp` using the command you configure below.

Set the environment variables in the examples to your values if you want to
override the defaults. See the [configuration guide](configuration.md).

## Claude Desktop

1. Open **Settings → Developer → Edit Config** to find
   `claude_desktop_config.json`.
2. Add this entry to `mcpServers`, keeping any existing server entries:

   ```json
   {
     "mcpServers": {
       "anyvar-mcp": {
         "command": "anyvar-mcp",
         "env": {
           "ANYVAR_API_URL": "http://localhost:8000",
           "ANYVAR_ENABLE_REGISTRATION": "true"
         }
       }
     }
   }
   ```

3. Save the file, fully quit Claude Desktop, and reopen it.

See the [Claude Desktop MCP documentation](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
for more setup options and troubleshooting.

### Verify the connection

Open a new chat. The server's tools should be available through
**Add files, connectors, and more → Connectors**.

If you're having issues, see [Troubleshooting](#troubleshooting).

## Codex CLI

In a terminal, add the MCP server with `ANYVAR_API_URL` set to
`http://localhost:8000` and `ANYVAR_ENABLE_REGISTRATION` set to `true`:

```shell
codex mcp add anyvar-mcp --env ANYVAR_API_URL=http://localhost:8000 --env ANYVAR_ENABLE_REGISTRATION=true -- anyvar-mcp
```

Confirm that the saved server list includes `anyvar-mcp`:

```shell
codex mcp list
```

See the [Codex MCP documentation](https://developers.openai.com/codex/mcp/)
and [CLI reference](https://developers.openai.com/codex/cli/reference/)
for more configuration options and commands.

### Verify the connection

Start Codex from a terminal:

```shell
codex
```

In Codex, enter `/mcp`. You should see `anyvar-mcp: connected (4 tools)`.

If you're having issues, see [Troubleshooting](#troubleshooting).

### Change saved settings

#### Config file

Edit the server's environment variables in `~/.codex/config.toml`:

```toml
[mcp_servers.anyvar-mcp.env]
ANYVAR_API_URL = "http://localhost:8000"
ANYVAR_ENABLE_REGISTRATION = "true"
```

#### CLI

In a terminal, inspect the current entry, remove it, and add it again with
all settings you want to keep. For example, to change the API URL and disable
registration:

```shell
codex mcp get anyvar-mcp
codex mcp remove anyvar-mcp
codex mcp add anyvar-mcp --env ANYVAR_API_URL=http://localhost:9000 --env ANYVAR_ENABLE_REGISTRATION=false -- anyvar-mcp
```

## Check tools from the terminal

With Node.js and `npx` installed, you can use the
[MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) to list
tools independently of your agent:

```shell
npx @modelcontextprotocol/inspector --cli anyvar-mcp --method tools/list
```

Once connected, [try the tools](quickstart.md#use-the-tools-with-your-ai-agent).

## Troubleshooting

### AnyVar HTTP API is unavailable

Make sure the [AnyVar HTTP API](dependencies.md#start-the-anyvar-http-api) is
running and keep it running while you use the tools. In your agent's MCP
configuration, set `ANYVAR_API_URL` to that instance's base URL, including the
correct host and port. For example, `http://localhost:8000` works only if the API
is running there and your MCP server can reach it.

After changing `ANYVAR_API_URL`, restart your agent so it uses the updated value.

### Agent cannot find `anyvar-mcp`

If `anyvar-mcp` fails to start, its tools may be missing in Claude Desktop,
or Codex CLI may show it as failed with 0 tools. Your agent may be unable to
find the executable because its `PATH` differs from your terminal's, especially
if you installed `anyvar-mcp` in a virtual environment.

Find the executable in the terminal where you installed it:

```shell
command -v anyvar-mcp
```

If nothing prints, activate the virtual environment where you installed the
server and try again. In the examples below, replace
`/home/git/anyvar-mcp/.venv/bin/anyvar-mcp` with the full path printed by
`command -v anyvar-mcp`. Restart your agent after saving the change.

#### Claude Desktop

Replace the `command` value for `anyvar-mcp` in `claude_desktop_config.json`:

```json
"command": "/home/git/anyvar-mcp/.venv/bin/anyvar-mcp"
```

#### Codex CLI

In `~/.codex/config.toml`, replace the `command` value under
`[mcp_servers.anyvar-mcp]`:

```toml
[mcp_servers.anyvar-mcp]
command = "/home/git/anyvar-mcp/.venv/bin/anyvar-mcp"
```

Or run this in a terminal to add the server with the full executable path:

```shell
codex mcp add anyvar-mcp --env ANYVAR_API_URL=http://localhost:8000 --env ANYVAR_ENABLE_REGISTRATION=true -- "/home/git/anyvar-mcp/.venv/bin/anyvar-mcp"
```

### Still having trouble?

Please [open an issue](https://github.com/genomicmedlab/anyvar-mcp/issues/new)
with exact steps to reproduce the problem, the expected result, and the full
error message or status. Include your operating system, agent name and version,
`anyvar-mcp` version, and relevant MCP configuration.
Remove credentials and other sensitive information before posting.
