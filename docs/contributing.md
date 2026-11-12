# Contributing

To use a published image, follow [Docker setup](docker.md).

## Prerequisites

You will need:

- Python 3.13 or newer
- Git
- A terminal or command prompt

## Python development

### Set up a virtual environment

If you are not a repository maintainer, first [fork the repository on
GitHub](https://github.com/genomicmedlab/anyvar-mcp/fork). Then clone your fork
(or the main repository if you have access), enter its directory, and create a
virtual environment:

Replace `OWNER` with your GitHub username for a fork, or `genomicmedlab` for the main
repository.

```shell
git clone https://github.com/OWNER/anyvar-mcp.git
cd anyvar-mcp
python3 -m venv .venv
source .venv/bin/activate
```

### Install the development dependencies

Install the package in editable mode with development, test, and documentation
dependencies. Editable mode makes changes in `src/` available without reinstalling:

```shell
python3 -m pip install -e '.[dev,tests,docs]'
```

### Install the pre-commit hooks

Install the hooks after installing the development dependencies:

```shell
prek install
```

### Style checks

Check style with `ruff`:

```shell
python3 -m ruff check --fix .
python3 -m ruff format .
```

### Tests

Run unit and integration tests:

```shell
python3 -m pytest
```

Mark tests that require a running AnyVar service or external resources
with `@pytest.mark.live`.

## Docker development

Install and start Docker, then build from the repository root:

```shell
docker build --pull --tag anyvar-mcp:local .
```

### Test the image

With the test dependencies installed in your development environment:

```shell
ANYVAR_MCP_TEST_IMAGE=anyvar-mcp:local python3 -m pytest tests/integration/test_docker.py --no-cov
```

### Develop with direct Docker

Run the local image with your AnyVar API URL. This example uses AnyVar running on
your Docker Desktop host:

```shell
docker run --rm -i \
  -e ANYVAR_API_URL=http://host.docker.internal:8000 \
  anyvar-mcp:local
```

!!! note "Linux Docker Engine"

    If AnyVar runs on your Linux host, add `--add-host` so the container can reach
    it at `host.docker.internal`:

    ```shell
    docker run --rm -i \
      --add-host=host.docker.internal:host-gateway \
      -e ANYVAR_API_URL=http://host.docker.internal:8000 \
      anyvar-mcp:local
    ```

#### Codex CLI

```shell
codex mcp add anyvar-mcp-docker-dev -- docker run --rm -i \
  -e ANYVAR_API_URL=http://host.docker.internal:8000 \
  anyvar-mcp:local
```

#### Claude Desktop

Open **Settings → Developer → Edit Config** and add this entry to
`claude_desktop_config.json`, keeping existing `mcpServers` entries:

```json
{
  "mcpServers": {
    "anyvar-mcp-docker-dev": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "ANYVAR_API_URL=http://host.docker.internal:8000",
        "anyvar-mcp:local"
      ]
    }
  }
}
```

Save the file, fully quit Claude Desktop, and reopen it.

#### Try source changes

After source changes, rebuild the image:

```shell
docker build --pull --tag anyvar-mcp:local .
```

Fully quit and reopen Claude Desktop, or exit and start a new Codex session, to
start a container with the rebuilt image. Try the affected tools against your
development AnyVar service.

### Develop with MCP Toolkit

Create a server definition that uses your local image:

```shell
mkdir -p "$HOME/.docker/mcp/catalogs"
sed 's|^image: .*|image: anyvar-mcp:local|' docker/anyvar-mcp.yaml > "$HOME/.docker/mcp/catalogs/anyvar-mcp-local.yaml"
```

Create a development profile and set your AnyVar URL:

```shell
docker mcp profile create --id anyvar-mcp-docker-dev --name anyvar-mcp-docker-dev
docker mcp profile server add anyvar-mcp-docker-dev --server "file://$HOME/.docker/mcp/catalogs/anyvar-mcp-local.yaml"
docker mcp profile config anyvar-mcp-docker-dev --set anyvar-mcp.api_url=http://host.docker.internal:8000
```

!!! tip "AnyVar URL"

    This example uses `http://host.docker.internal:8000`. Replace it with your
    AnyVar API URL, which must be [reachable from the container](docker.md#choose-the-anyvar-url).

#### Codex CLI

Connect to the development profile:

```shell
codex mcp add anyvar-mcp-docker-dev -- docker mcp gateway run --profile anyvar-mcp-docker-dev
```

#### Claude Desktop

Follow the [Toolkit client setup](docker.md#claude-desktop),
using `anyvar-mcp-docker-dev` as the entry and profile name.

#### Try source changes

After source changes, rebuild the image:

```shell
docker build --pull --tag anyvar-mcp:local .
```

Restart the gateway by fully quitting and reopening Claude Desktop, or exiting
and starting a new Codex session. Try the affected tools against your development
AnyVar service.

If you change the server definition, [import it again](docker.md#change-toolkit-settings)
using profile `anyvar-mcp-docker-dev` and file `~/.docker/mcp/catalogs/anyvar-mcp-local.yaml`.

## Documentation

Edit the Markdown files in `docs/`. Preview the site locally:

```shell
zensical serve
```

Open `http://127.0.0.1:8001`.

Build the site with the same strict checks used in CI:

```shell
zensical build --clean --strict
```

## Open a pull request

Run the checks relevant to your changes, review the generated documentation, and
open a pull request on GitHub. Include a short summary of the change and any
relevant testing or documentation notes.

If the pull request resolves an issue, say so with a closing keyword such as
`Closes #123`, where `123` is the issue number. GitHub will close the issue
automatically when the pull request merges. If the pull request is related to an
issue but does not resolve it, use a non-closing reference such as `Refs #123`,
where `123` is again the issue number, or link the issue through the pull
request's GitHub interface instead.

## Container release publishing

GitHub Actions automatically builds and publishes container images to
`ghcr.io/genomicmedlab/anyvar-mcp` when a GitHub release is published. See the
[`docker-publish.yaml` workflow](https://github.com/GenomicMedLab/anyvar-mcp/blob/main/.github/workflows/docker-publish.yaml)
for details.
