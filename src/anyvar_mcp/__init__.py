"""MCP Server for AnyVar"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("anyvar_mcp")
except PackageNotFoundError:
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError
