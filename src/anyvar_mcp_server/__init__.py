"""MCP Server for AnyVar"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("anyvar_mcp_server")
except PackageNotFoundError:
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError
