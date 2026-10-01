"""System-level MCP stdio bootstrap (Phase SI-1).

Entry point: python -m system.mcp_stdio

1. load configured production provider;
2. validate dependency bundle;
3. compose CuratorRuntime;
4. compose EvidenceRuntime;
5. call existing create_mcp_server(...);
6. start stdio server.

Does NOT implement orchestrator/workflows.
Does NOT change public MCP tool contracts.
"""

from __future__ import annotations

import sys
from typing import Optional

from system.composition import (
    CuratorDependencies,
    EvidenceDependencies,
    compose_system_runtime,
)
from system.provider_loader import ProviderLoadError, load_provider_bundle


def _extract_deps(bundle) -> tuple[CuratorDependencies, Optional[EvidenceDependencies]]:
    """Extract CuratorDependencies / EvidenceDependencies from a provider bundle."""
    if isinstance(bundle, dict):
        curator_raw = bundle.get("curator")
        evidence_raw = bundle.get("evidence")
    else:
        curator_raw = getattr(bundle, "curator", None)
        evidence_raw = getattr(bundle, "evidence", None)

    if curator_raw is None:
        raise ProviderLoadError("bundle.curator is required")

    if isinstance(curator_raw, dict):
        curator_deps = CuratorDependencies(
            repository=curator_raw.get("repository"),
            ontology=curator_raw.get("ontology"),
            mechanism_validator=curator_raw.get("mechanism_validator"),
            provider_identity=str(curator_raw.get("provider_identity", "external")),
        )
    else:
        curator_deps = CuratorDependencies(
            repository=getattr(curator_raw, "repository", None),
            ontology=getattr(curator_raw, "ontology", None),
            mechanism_validator=getattr(curator_raw, "mechanism_validator", None),
            provider_identity=str(getattr(curator_raw, "provider_identity", "external")),
        )

    evidence_deps = None
    if evidence_raw is not None:
        if isinstance(evidence_raw, dict):
            evidence_deps = EvidenceDependencies(
                retrieval=evidence_raw.get("retrieval"),
                mechanism_validator=evidence_raw.get("mechanism_validator"),
                provider_identity=str(evidence_raw.get("provider_identity", "external")),
            )
        else:
            evidence_deps = EvidenceDependencies(
                retrieval=getattr(evidence_raw, "retrieval", None),
                mechanism_validator=getattr(evidence_raw, "mechanism_validator", None),
                provider_identity=str(getattr(evidence_raw, "provider_identity", "external")),
            )

    return curator_deps, evidence_deps


def build_system_mcp_server(spec: Optional[str] = None):
    """Build the MCP server from a production provider bundle."""
    bundle = load_provider_bundle(spec)
    curator_deps, evidence_deps = _extract_deps(bundle)
    runtime = compose_system_runtime(
        curator_deps=curator_deps, evidence_deps=evidence_deps
    )
    from knowledge_curator.mcp_server.app import create_mcp_server

    return create_mcp_server(
        runtime=runtime.curator_runtime,
        evidence_runtime=runtime.evidence_runtime,
    )


def run_stdio(spec: Optional[str] = None) -> None:
    """Start the MCP stdio server from a production provider bundle."""
    server = build_system_mcp_server(spec)
    import anyio

    anyio.run(server.run_stdio_async)


def main() -> int:
    try:
        run_stdio()
        return 0
    except ProviderLoadError as exc:
        print(f"production provider load failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"system MCP bootstrap failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
