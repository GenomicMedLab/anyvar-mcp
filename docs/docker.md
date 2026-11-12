# Docker setup

!!! note "Published image"

    This page uses the published AnyVar MCP image. To build and test local source
    changes, follow [Docker development](contributing.md#docker-development).

Choose how your agent connects to AnyVar MCP:

- [Docker MCP Toolkit](#docker-mcp-toolkit): Manage your MCP servers in Docker
  and connect your agent to all of them through one connection. Docker starts
  their containers.
- [Direct Docker](#run-directly-with-docker): Configure AnyVar MCP in your agent,
  which starts its container with `docker run`. Manage each MCP server separately.

Both routes use the same container image and support Claude Desktop and Codex CLI.

The container uses stdio and needs no published ports or host filesystem mounts.
See the [configuration reference](configuration.md) for settings and defaults.

## Prerequisites

- A running [AnyVar HTTP API](anyvar-service-setup.md) reachable from the MCP container.
- Claude Desktop or Codex CLI installed.
- Docker installed and running:
  - **MCP Toolkit:** Docker Desktop **4.62 or later**, with MCP Toolkit enabled
    and `docker mcp profile` commands available.
  - **Direct Docker:** Docker Desktop or Docker Engine.

## Get the image

```shell
docker pull ghcr.io/genomicmedlab/anyvar-mcp:latest
```

`latest` tracks stable releases. For a fixed version, replace `latest` with the
release version.

## Choose the AnyVar URL

Set `ANYVAR_API_URL` to your AnyVar API URL.

| AnyVar location | Example URL |
| --- | --- |
| Published on Docker Desktop host port 8000 | `http://host.docker.internal:8000` |
| Remote HTTP service | `https://anyvar.example.org` |
| Service named `anyvar`, sharing a Docker network with the MCP container | `http://anyvar:8000` |

## Docker MCP Toolkit

See Docker's [Toolkit documentation](https://docs.docker.com/ai/mcp-catalog-and-toolkit/toolkit/)
and [CLI guide](https://docs.docker.com/ai/mcp-catalog-and-toolkit/cli/).

### Configure the server

Clone the repository if you have not already:

```shell
git clone https://github.com/GenomicMedLab/anyvar-mcp.git
```

From the repository root (`anyvar-mcp/`), copy the server definition into Docker's
required trusted catalogs directory:

```shell
mkdir -p "$HOME/.docker/mcp/catalogs"
cp docker/anyvar-mcp.yaml "$HOME/.docker/mcp/catalogs/anyvar-mcp.yaml"
```

Toolkit servers do not inherit your host's environment variables. To override
settings, edit the `env` list in `~/.docker/mcp/catalogs/anyvar-mcp.yaml` before
importing it. For example:

```yaml
env:
  - name: ANYVAR_API_URL
    value: "{{anyvar-mcp.api_url}}"
  - name: ANYVAR_ENABLE_REGISTRATION
    value: "true"
```

!!! tip "Allow registration"

    Setting `ANYVAR_ENABLE_REGISTRATION` to `"true"`, as shown above, lets agents
    write to AnyVar.

### Create a Toolkit profile

Create a profile, import the server definition, and set your API URL:

```shell
docker mcp profile create --id anyvar-mcp-docker --name anyvar-mcp-docker
docker mcp profile server add anyvar-mcp-docker --server "file://$HOME/.docker/mcp/catalogs/anyvar-mcp.yaml"
docker mcp profile config anyvar-mcp-docker --set anyvar-mcp.api_url=http://host.docker.internal:8000
```

### Connect your AI agent

Each client starts the gateway when it connects.

#### Codex CLI

Register the Docker gateway as an MCP connection in Codex, using the
`anyvar-mcp-docker` profile. Then check the saved connection settings:

```shell
codex mcp add anyvar-mcp-docker -- docker mcp gateway run --profile anyvar-mcp-docker
codex mcp get anyvar-mcp-docker
```

See the [Codex MCP documentation](https://developers.openai.com/codex/mcp/).

#### Claude Desktop

Configure Claude Desktop to start the Docker gateway with the
`anyvar-mcp-docker` profile when it connects to AnyVar MCP.

Open **Settings → Developer → Edit Config**. Add this entry to
`claude_desktop_config.json`, keeping existing entries under `mcpServers`:

```json
{
  "mcpServers": {
    "anyvar-mcp-docker": {
      "command": "docker",
      "args": ["mcp", "gateway", "run", "--profile", "anyvar-mcp-docker"]
    }
  }
}
```

Save the file, fully quit Claude Desktop, and reopen it.

### Check the Toolkit connection

- **Codex CLI:** Start a new session, enter `/mcp`, and check that
  `anyvar-mcp-docker` is connected.
- **Claude Desktop:** In a new chat, open **Add files, connectors, and more →
  Connectors → Manage connectors** and select `anyvar-mcp-docker`.

Follow [Use the tools with your AI agent](quickstart.md#use-the-tools-with-your-ai-agent)
in the Quickstart to try the AnyVar tools.

### Change Toolkit settings

Profiles store a snapshot of the imported server definition. For example, to
disable writes after enabling registration above, edit
`~/.docker/mcp/catalogs/anyvar-mcp.yaml` and change:

```yaml
  - name: ANYVAR_ENABLE_REGISTRATION
    value: "true"
```

to:

```yaml
  - name: ANYVAR_ENABLE_REGISTRATION
    value: "false"
```

After changing the image or any `env` entries, import the definition again:

```shell
docker mcp profile server remove anyvar-mcp-docker --name anyvar-mcp
docker mcp profile server add anyvar-mcp-docker --server "file://$HOME/.docker/mcp/catalogs/anyvar-mcp.yaml"
docker mcp profile config anyvar-mcp-docker --set anyvar-mcp.api_url=http://host.docker.internal:8000
```

Fully quit and reopen Claude Desktop, or exit and start a new Codex session, so the
gateway loads the updated definition.

## Run directly with Docker

Configure your AI agent to run the published image with `docker run`. The agent starts a
new container each time it connects to AnyVar MCP.

### Configure the container

Use `-i` so your agent can communicate with the container over stdin. Pass
[configuration settings](configuration.md) with `-e` or `--env-file`.

For AnyVar running on your Docker Desktop host:

```shell
docker run --rm -i \
  -e ANYVAR_API_URL=http://host.docker.internal:8000 \
  ghcr.io/genomicmedlab/anyvar-mcp:latest
```

!!! note "Linux Docker Engine"

    If AnyVar runs on your Linux host, add `--add-host` so the container can reach
    it at `host.docker.internal`:

    ```shell
    docker run --rm -i \
      --add-host=host.docker.internal:host-gateway \
      -e ANYVAR_API_URL=http://host.docker.internal:8000 \
      ghcr.io/genomicmedlab/anyvar-mcp:latest
    ```

    Include this option in your agent's Docker arguments below as well.

### Connect your AI agent

#### Codex CLI

```shell
codex mcp add anyvar-mcp-docker -- docker run --rm -i \
  -e ANYVAR_API_URL=http://host.docker.internal:8000 \
  ghcr.io/genomicmedlab/anyvar-mcp:latest
codex mcp get anyvar-mcp-docker
```

!!! tip "Allow registration"

    To let agents write to AnyVar, use:

    ```shell
    codex mcp add anyvar-mcp-docker -- docker run --rm -i \
      -e ANYVAR_API_URL=http://host.docker.internal:8000 \
      -e ANYVAR_ENABLE_REGISTRATION=true \
      ghcr.io/genomicmedlab/anyvar-mcp:latest
    ```

#### Claude Desktop

Open **Settings → Developer → Edit Config** and add this entry to
`claude_desktop_config.json`, keeping existing `mcpServers` entries:

```json
{
  "mcpServers": {
    "anyvar-mcp-docker": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "ANYVAR_API_URL=http://host.docker.internal:8000",
        "ghcr.io/genomicmedlab/anyvar-mcp:latest"
      ]
    }
  }
}
```

Save the file, fully quit Claude Desktop, and reopen it.

!!! tip "Allow registration"

    To let agents write to AnyVar, use:

    ```json
    {
      "mcpServers": {
        "anyvar-mcp-docker": {
          "command": "docker",
          "args": [
            "run", "--rm", "-i",
            "-e", "ANYVAR_API_URL=http://host.docker.internal:8000",
            "-e", "ANYVAR_ENABLE_REGISTRATION=true",
            "ghcr.io/genomicmedlab/anyvar-mcp:latest"
          ]
        }
      }
    }
    ```

### Check the direct Docker connection

- **Codex CLI:** Start a new session, enter `/mcp`, and check that
  `anyvar-mcp-docker` is connected.
- **Claude Desktop:** In a new chat, open **Add files, connectors, and more →
  Connectors → Manage connectors** and select `anyvar-mcp-docker`.

Follow [Use the tools with your AI agent](quickstart.md#use-the-tools-with-your-ai-agent)
in the Quickstart to try the AnyVar tools.

## Troubleshooting

- **Agent cannot find Docker:** Use the full path printed by `command -v docker`
  as its server command.

- **Tools are listed but calls fail:** Check the URL from the container's network,
  the AnyVar port mapping, and the service logs. Tool discovery does not contact
  AnyVar, so it can succeed even when the API is unavailable.
