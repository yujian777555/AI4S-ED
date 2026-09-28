"""knowledge_curator MCP server (thin adapter over §5 core)."""

from knowledge_curator.mcp_server.app import (
    HEALTH_TOOL_NAME,
    PUBLIC_TOOL_NAME,
    create_mcp_server,
    run_stdio,
)
from knowledge_curator.mcp_server.codec import CodecError, parse_assertion_set, serialize_curation_report
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
