# Contributing

This page explains how to set up the project for development, run tests, and
update the documentation.

## Prerequisites

You will need:

- Python 3.13 or newer
- Git
- A terminal or command prompt

## Set up a virtual environment

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

## Install the development dependencies

Install the package in editable mode with development, test, and documentation
dependencies. Editable mode makes changes in `src/` available without reinstalling:

```shell
python3 -m pip install -e '.[dev,tests,docs]'
```

## Install the pre-commit hooks

Install the hooks after installing the development dependencies:

```shell
prek install
```

## Style checks

Check style with `ruff`:

```shell
python3 -m ruff check --fix .
python3 -m ruff format .
```

## Tests

Run unit and integration tests:

```shell
python3 -m pytest
```

Mark tests that require a running AnyVar service or external resources
with `@pytest.mark.live`.

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
