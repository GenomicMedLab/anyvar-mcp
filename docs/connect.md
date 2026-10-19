# Connect your AI agent

## Prerequisites

First, install the AI client you want to use: [Claude Desktop](https://support.claude.com/en/articles/10065433-install-claude-desktop) or [Codex CLI](https://learn.chatgpt.com/docs/codex/cli#getting-started).

Then [install `anyvar-mcp`](quickstart.md#install-the-mcp-server) and start the
[AnyVar HTTP API](dependencies.md). Keep the API running while you use the tools.
The client starts `anyvar-mcp` using the command you configure below.

Set the environment variables in the examples to your values if you want to
override the defaults. See the [configuration guide](configuration.md).

## Find the server command

Find the executable:

```shell
command -v anyvar-mcp
```

If nothing prints, activate the virtual environment where you installed the
server and try again. Save the printed path. Use it as the command if your
agent cannot find `anyvar-mcp`. For a virtual environment, it might look like:

```text
/home/git/anyvar-mcp/.venv/bin/anyvar-mcp
```

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

   If Claude Desktop cannot find the command, replace the `command` value with
   the full executable path.

3. Save the file, fully quit Claude Desktop, and reopen it.
4. In a new chat, open **Add files, connectors, and more → Connectors → Manage
   connectors** and select `anyvar-mcp` to check its tools.

See the [Claude Desktop MCP documentation](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
for more setup options and troubleshooting.

## Codex CLI

For example, add the MCP server with `ANYVAR_API_URL` set to
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

### Change saved settings

#### Config file

Edit the server's environment variables in `~/.codex/config.toml`:

```toml
[mcp_servers.anyvar-mcp.env]
ANYVAR_API_URL = "http://localhost:8000"
ANYVAR_ENABLE_REGISTRATION = "true"
```

#### CLI

Inspect the current entry, remove it, and add it again with
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
