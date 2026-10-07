# AnyVar MCP Server

[![image](https://img.shields.io/pypi/v/anyvar_mcp_server.svg)](https://pypi.python.org/pypi/anyvar_mcp_server)
[![image](https://img.shields.io/pypi/l/anyvar_mcp_server.svg)](https://pypi.python.org/pypi/anyvar_mcp_server)
[![image](https://img.shields.io/pypi/pyversions/anyvar_mcp_server.svg)](https://pypi.python.org/pypi/anyvar_mcp_server)
[![Actions status](https://github.com/genomicmedlab/anyvar_mcp_server/actions/workflows/checks.yaml/badge.svg)](https://github.com/genomicmedlab/anyvar_mcp_server/actions/checks.yaml)

<!-- description -->
MCP Server for AnyVar
<!-- /description -->



---

## Installation

Install from [PyPI](https://pypi.org/project/anyvar_mcp_server/):

```shell
python3 -m pip install anyvar_mcp_server
```

---

## Development

Clone the repo and create a virtual environment:

```shell
git clone https://github.com/genomicmedlab/anyvar-mcp-server
cd anyvar-mcp-server
python3 -m virtualenv venv
source venv/bin/activate
```

Install development dependencies and `prek`:

```shell
python3 -m pip install -e '.[dev,tests]'
prek install
```

Check style with `ruff`:

```shell
python3 -m ruff format . && python3 -m ruff check --fix .
```

Run tests with `pytest`:

```shell
pytest
```
