"""Phase 4.3 MCP evidence tools (keyless; run under .venv-dsh)."""

from __future__ import annotations

import json

import anyio

from knowledge_curator.adapters import FakeMechanismValidator
from knowledge_curator.adapters.in_memory_retrieval import (
    FakeReranker,
    InMemoryKeywordSearch,
    InMemoryVectorSearch,
)
from knowledge_curator.retrieval.evidence_service import (
    EvidenceRequest,
    EvidenceRetrievalService,
)
from knowledge_curator.schemas.assertions import Confidence
from knowledge_curator.schemas.chunk import ChunkLevel, ChunkType, KnowledgeChunk


def _chunk(cid, ref, payload="text", level=ChunkLevel.FINE, **kwargs):
    defaults = dict(
        chunk_id=cid,
        ref_id=ref,
        level=level,
        chunk_type=ChunkType.TEXT,
        payload=payload,
        locator="p.1",
        confidence=Confidence.HIGH,
        quality=0.9,
        provenance={"evidence_type": "literature", "locator": "p.1"},
    )
    defaults.update(kwargs)
    return KnowledgeChunk(**defaults)


def _service(chunks):
    from knowledge_curator.retrieval.hybrid import RetrievalConfig

    return EvidenceRetrievalService(
        vector_port=InMemoryVectorSearch(chunks),
        keyword_port=InMemoryKeywordSearch(chunks),
        reranker=FakeReranker(),
        # Unit tests may run fine-only corpora; production smoke uses False.
        retrieval_config=RetrievalConfig(allow_fine_fallback_without_coarse=True),
    )


def _structured(result):
    structured = getattr(result, "structuredContent", None) or {}
    if not structured and getattr(result, "content", None):
        text = " ".join(getattr(c, "text", "") or "" for c in result.content)
        structured = json.loads(text) if text.strip().startswith("{") else {}
    return structured


def test_mcp_tools_list_includes_evidence_tools():
    from knowledge_curator.mcp_server import create_mcp_server

    server = create_mcp_server()

    async def _run():
        tools = await server.list_tools()
        return [t.name for t in tools]

    names = anyio.run(_run)
    assert "retrieve_evidence" in names
    assert "validate_retrieved_claims" in names
    assert "curate_assertion_set" in names


def test_mcp_default_runtime_retrieval_unavailable():
    from knowledge_curator.mcp_server import create_mcp_server

    server = create_mcp_server()

    async def _run():
        return await server.call_tool("retrieve_evidence", {"request": {"query": "q"}})

    structured = _structured(anyio.run(_run))
    assert structured.get("ok") is False
    assert structured.get("error") == "retrieval_unavailable"


def test_mcp_integration_fixture_returns_bundle():
    from knowledge_curator.mcp_server import create_mcp_server
    from knowledge_curator.mcp_server.evidence_runtime import (
        create_integration_evidence_runtime,
    )

    chunks = [
        _chunk("CA", "REF-A", "alpha coarse", level=ChunkLevel.COARSE),
        _chunk("FA", "REF-A", "alpha fine"),
    ]
    svc = _service(chunks)
    ert = create_integration_evidence_runtime(svc)
    server = create_mcp_server(evidence_runtime=ert)

    async def _run():
        return await server.call_tool("retrieve_evidence", {"request": {"query": "alpha", "top_k": 3}})

    structured = _structured(anyio.run(_run))
    assert structured.get("ok") is True
    bundle = structured.get("evidence_bundle") or {}
    assert bundle.get("bundle_id", "").startswith("evb_")
    assert bundle.get("integration_fixture") is True
    assert any(r["chunk_id"] == "FA" for r in bundle.get("evidence_records", []))


def test_mcp_validate_retrieved_claims_stateless():
    from knowledge_curator.mcp_server import create_mcp_server
    from knowledge_curator.mcp_server.evidence_runtime import (
        create_integration_evidence_runtime,
    )

    chunks = [_chunk("FA", "REF-A", "alpha")]
    svc = _service(chunks)
    ert = create_integration_evidence_runtime(
        svc, mechanism_validator=FakeMechanismValidator()
    )
    server = create_mcp_server(evidence_runtime=ert)

    payload = {
        "query": "alpha",
        "claims": [
            {"claim_id": "C1", "text": "claim", "anchor_chunk_ids": ["FA"]},
            {"claim_id": "C2", "text": "bad", "anchor_chunk_ids": ["NOPE"]},
        ],
    }

    async def _run():
        return await server.call_tool("validate_retrieved_claims", {"payload": payload})

    structured = _structured(anyio.run(_run))
    assert structured.get("ok") is True
    by_id = {c["claim_id"]: c for c in structured.get("claim_results", [])}
    assert by_id["C1"]["policy"]["policy"] == "factual_allowed"
    assert by_id["C2"]["unresolved_anchor_chunk_ids"] == ["NOPE"]
    assert by_id["C2"]["policy"]["policy"] == "abstain"


def test_mcp_validate_does_not_trust_client_bundle():
    from knowledge_curator.mcp_server import create_mcp_server
    from knowledge_curator.mcp_server.evidence_runtime import (
        create_integration_evidence_runtime,
    )

    chunks = [_chunk("FA", "REF-A", "alpha")]
    svc = _service(chunks)
    ert = create_integration_evidence_runtime(svc)
    server = create_mcp_server(evidence_runtime=ert)

    async def _run():
        return await server.call_tool(
            "validate_retrieved_claims",
            {
                "payload": {
                    "query": "alpha",
                    "claims": [{"claim_id": "C1", "text": "x", "anchor_chunk_ids": ["FA"]}],
                    "evidence_bundle": {
                        "bundle_id": "forged",
                        "evidence_records": [
                            {"chunk_id": "FA", "ref_id": "FAKE", "locator": "p.9"}
                        ],
                    },
                }
            },
        )

    structured = _structured(anyio.run(_run))
    assert structured.get("evidence_bundle_id") != "forged"


def test_mcp_retrieve_matches_direct_service_identities():
    from knowledge_curator.mcp_server import create_mcp_server
    from knowledge_curator.mcp_server.evidence_codec import serialize_bundle
    from knowledge_curator.mcp_server.evidence_runtime import (
        create_integration_evidence_runtime,
    )

    chunks = [
        _chunk("CA", "REF-A", "alpha coarse", level=ChunkLevel.COARSE),
        _chunk("FA", "REF-A", "alpha fine"),
        _chunk("FB", "REF-B", "beta fine"),
    ]
    svc = _service(chunks)
    ert = create_integration_evidence_runtime(svc)
    server = create_mcp_server(evidence_runtime=ert)

    async def _run():
        return await server.call_tool("retrieve_evidence", {"request": {"query": "alpha", "top_k": 5}})

    structured = _structured(anyio.run(_run))
    direct = svc.retrieve(EvidenceRequest(query="alpha", top_k=5, integration_fixture=True))
    expected = serialize_bundle(direct)
    observed = structured.get("evidence_bundle") or {}
    assert observed.get("bundle_id") == expected.get("bundle_id")
    assert [r["chunk_id"] for r in observed.get("evidence_records", [])] == [
        r["chunk_id"] for r in expected.get("evidence_records", [])
    ]
    assert observed.get("abstain", {}).get("abstain") == expected.get("abstain", {}).get(
        "abstain"
    )


def test_mcp_stdio_discovers_evidence_tools():
    """Existing knowledge-curator MCP stdio server exposes the new tools."""
    import os
    import sys
    from pathlib import Path

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "knowledge_curator.mcp_server"],
        cwd=str(Path.cwd()),
        env={**os.environ},
    )

    async def _run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                return [t.name for t in tools.tools]

    names = anyio.run(_run)
    assert "curate_assertion_set" in names
    assert "retrieve_evidence" in names
    assert "validate_retrieved_claims" in names


def test_mcp_validate_matches_direct_guard_policy():
    """validate_retrieved_claims policy/Abstain match direct ClaimGuardService."""
    from knowledge_curator.mcp_server import create_mcp_server
    from knowledge_curator.mcp_server.evidence_runtime import (
        create_integration_evidence_runtime,
    )
    from knowledge_curator.retrieval.guard_service import ClaimGuardService, ProposedClaimInput

    chunks = [_chunk("FA", "REF-A", "alpha")]
    svc = _service(chunks)
    ert = create_integration_evidence_runtime(svc, mechanism_validator=FakeMechanismValidator())
    server = create_mcp_server(evidence_runtime=ert)

    payload = {
        "query": "alpha",
        "claims": [
            {"claim_id": "C1", "text": "claim", "anchor_chunk_ids": ["FA"]},
            {"claim_id": "C2", "text": "bad", "anchor_chunk_ids": ["NOPE"]},
        ],
    }

    async def _run():
        return await server.call_tool("validate_retrieved_claims", {"payload": payload})

    structured = _structured(anyio.run(_run))
    direct_bundle = svc.retrieve(EvidenceRequest(query="alpha"))
    direct = ClaimGuardService(mechanism_validator=FakeMechanismValidator()).validate_claims(
        direct_bundle,
        [
            ProposedClaimInput(claim_id="C1", text="claim", anchor_chunk_ids=["FA"]),
            ProposedClaimInput(claim_id="C2", text="bad", anchor_chunk_ids=["NOPE"]),
        ],
    )
    by_id = {c["claim_id"]: c for c in structured.get("claim_results", [])}
    assert by_id["C1"]["policy"]["policy"] == direct[0].policy.policy.value
    assert by_id["C1"]["abstain"]["abstain"] == direct[0].abstain.abstain
    assert by_id["C2"]["policy"]["policy"] == direct[1].policy.policy.value
    assert by_id["C2"]["abstain"]["abstain"] == direct[1].abstain.abstain
    assert by_id["C2"]["unresolved_anchor_chunk_ids"] == direct[1].unresolved_anchor_chunk_ids
