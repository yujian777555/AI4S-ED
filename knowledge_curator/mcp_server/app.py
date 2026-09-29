"""MCP application: official MCPServer exposing curation + evidence tools.

Thin adapter over existing KnowledgeCurator core and Phase 4.3 evidence
services. No 搂5 logic duplication. No scientific prose answers.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from knowledge_curator.mcp_server.codec import parse_assertion_set, serialize_curation_report
from knowledge_curator.mcp_server.evidence_codec import (
    EvidenceCodecError,
    parse_evidence_request,
    parse_proposed_claims,
    serialize_bundle,
    serialize_claim_result,
)
from knowledge_curator.mcp_server.evidence_runtime import (
    EvidenceRuntime,
    create_unavailable_evidence_runtime,
)
from knowledge_curator.mcp_server.runtime import CuratorRuntime, create_default_runtime, run_curate
from knowledge_curator.retrieval.evidence_service import EvidenceRequest

PUBLIC_TOOL_NAME = "curate_assertion_set"
HEALTH_TOOL_NAME = "knowledge_curator_health"
RETRIEVE_EVIDENCE_TOOL = "retrieve_evidence"
VALIDATE_CLAIMS_TOOL = "validate_retrieved_claims"


def create_mcp_server(
    runtime: CuratorRuntime | None = None,
    *,
    evidence_runtime: EvidenceRuntime | None = None,
) -> MCPServer:
    """Build the knowledge_curator MCP server around optional runtimes."""
    rt = runtime or create_default_runtime()
    ert = evidence_runtime or create_unavailable_evidence_runtime()
    server = MCPServer(
        name="knowledge_curator",
        version="0.2.0",
        instructions=(
            "Deterministic knowledge curation and evidence-retrieval tools for AI4S-ED. "
            "Business logic lives in KnowledgeCurator core and frozen retrieval/guard services. "
            "Do not generate final scientific answers from these tools."
        ),
    )

    @server.tool(
        name=PUBLIC_TOOL_NAME,
        description=(
            "Curate one AssertionSet through KnowledgeCurator 搂5.1鈥撀?.3 "
            "(completeness, conflict, quality, decision) and return a CurationReport."
        ),
    )
    async def curate_assertion_set(assertion_set: dict[str, Any]) -> dict[str, Any]:
        try:
            parsed = parse_assertion_set(assertion_set)
        except Exception as exc:
            raise ToolError(f"invalid assertion_set: {exc}") from exc
        report = await run_curate(rt, parsed)
        return {
            "ok": True,
            "report": serialize_curation_report(report),
        }

    @server.tool(
        name=HEALTH_TOOL_NAME,
        description="Integration diagnostic only 鈥?not a scientific business API.",
    )
    async def knowledge_curator_health() -> dict[str, Any]:
        return {
            "ok": True,
            "role": "integration-diagnostic",
            "core": "KnowledgeCurator",
            "adapters": rt.adapter_note,
            "public_business_tool": PUBLIC_TOOL_NAME,
            "evidence_tools": [RETRIEVE_EVIDENCE_TOOL, VALIDATE_CLAIMS_TOOL],
            "evidence_adapters": ert.adapter_note,
            "retrieval_available": ert.retrieval_available,
            "unavailability_reason": ert.unavailability_reason,
        }

    @server.tool(
        name=RETRIEVE_EVIDENCE_TOOL,
        description=(
            "Retrieve evidence for a query/subqueries and return a structured "
            "EvidenceBundle with provenance, coverage and Abstain state. "
            "Does NOT generate a scientific answer."
        ),
    )
    async def retrieve_evidence(request: dict[str, Any]) -> dict[str, Any]:
        if not ert.retrieval_available or ert.retrieval is None:
            return {
                "ok": False,
                "error": "retrieval_unavailable",
                "detail": ert.unavailability_reason or "retrieval_unavailable: not_configured",
                "evidence_bundle": None,
            }
        try:
            req: EvidenceRequest = parse_evidence_request(
                request, integration_fixture=ert.integration_fixture
            )
        except EvidenceCodecError as exc:
            raise ToolError(f"invalid request: {exc}") from exc
        try:
            bundle = ert.retrieval.retrieve(req)
        except Exception as exc:
            raise ToolError(f"retrieval failed: {type(exc).__name__}: {exc}") from exc
        return {
            "ok": True,
            "integration_fixture": ert.integration_fixture,
            "evidence_bundle": serialize_bundle(bundle),
        }

    @server.tool(
        name=VALIDATE_CLAIMS_TOOL,
        description=(
            "Re-run deterministic retrieval for the original query/subqueries and "
            "validate proposed claims (anchor_chunk_ids) against THAT fresh retrieval "
            "set. Stateless. Returns policy/Abstain/H1-H3. No scientific prose."
        ),
    )
    async def validate_retrieved_claims(payload: dict[str, Any]) -> dict[str, Any]:
        if not ert.retrieval_available or ert.retrieval is None:
            return {
                "ok": False,
                "error": "retrieval_unavailable",
                "detail": ert.unavailability_reason or "retrieval_unavailable: not_configured",
            }
        try:
            data = payload if isinstance(payload, dict) else {}
            req_raw = data.get("request") or {
                k: data.get(k)
                for k in (
                    "query",
                    "subqueries",
                    "top_k",
                    "allowed_ref_ids",
                    "coverage_keys",
                    "required_coverage_keys",
                    "private_data_unauthorized",
                    "calibrated_support",
                )
                if data.get(k) is not None
            }
            req = parse_evidence_request(
                req_raw, integration_fixture=ert.integration_fixture
            )
            claims = parse_proposed_claims(data.get("claims"))
        except EvidenceCodecError as exc:
            raise ToolError(f"invalid payload: {exc}") from exc

        try:
            # Stateless: re-run deterministic retrieval, never trust client bundle.
            bundle = ert.retrieval.retrieve(req)
            results = ert.guard.validate_claims(bundle, claims)
        except Exception as exc:
            raise ToolError(f"validation failed: {type(exc).__name__}: {exc}") from exc

        return {
            "ok": True,
            "integration_fixture": ert.integration_fixture,
            "evidence_bundle_id": bundle.bundle_id,
            "evidence_bundle": serialize_bundle(bundle),
            "claim_results": [serialize_claim_result(r) for r in results],
        }

    return server


def run_stdio() -> None:
    """Entry for `python -m knowledge_curator.mcp_server` (official stdio transport)."""
    server = create_mcp_server()
    import anyio

    anyio.run(server.run_stdio_async)
