"""knowledge_curator MCP server (thin adapter over §5 core).

App/MCP imports are lazy so evidence_runtime can be used without the `mcp` package.
"""

from knowledge_curator.mcp_server.codec import (
    CodecError,
    parse_assertion_set,
    serialize_curation_report,
)
from knowledge_curator.mcp_server.runtime import create_default_runtime

__all__ = [
    "CodecError",
    "HEALTH_TOOL_NAME",
    "PUBLIC_TOOL_NAME",
    "create_default_runtime",
    "create_mcp_server",
    "parse_assertion_set",
    "run_stdio",
    "serialize_curation_report",
]


def __getattr__(name: str):
    # Lazy: only pull in mcp SDK when app symbols are actually needed.
    if name in ("create_mcp_server", "run_stdio", "PUBLIC_TOOL_NAME", "HEALTH_TOOL_NAME"):
        from knowledge_curator.mcp_server import app as _app

        return getattr(_app, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
