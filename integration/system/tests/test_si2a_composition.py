"""SI-2A application composition tests.

Covers plan section 14: provider bundle validation, Port checks, forbidden
adapter rejection, and successful composition.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestSI2ACompositionFailClosed:
    """Missing/malformed commit dependencies must fail closed at composition."""

    def _compose_with_bundle(self, bundle: dict):
        from system.application_composition import (
            _extract_commit_deps,
            _validate_commit_deps,
        )

        deps = _extract_commit_deps(bundle)
        _validate_commit_deps(deps)
        return deps

    def test_missing_commit_group_fails(self):
        from system.application_composition import (
            ApplicationCompositionError,
            _extract_commit_deps,
        )

        bundle = {"curator": {"repository": None}}
        with pytest.raises(ApplicationCompositionError, match="commit"):
            _extract_commit_deps(bundle)

    def test_missing_commit_store_fails(self):
        from system.application_composition import ApplicationCompositionError
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        bundle["commit"]["commit_store"] = None
        with pytest.raises(ApplicationCompositionError, match="commit_store"):
            self._compose_with_bundle(bundle)

    def test_missing_structural_store_fails(self):
        from system.application_composition import ApplicationCompositionError
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        bundle["commit"]["structural_store"] = None
        with pytest.raises(ApplicationCompositionError, match="structural_store"):
            self._compose_with_bundle(bundle)

    def test_missing_vector_index_fails(self):
        from system.application_composition import ApplicationCompositionError
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        bundle["commit"]["vector_index"] = None
        with pytest.raises(ApplicationCompositionError, match="vector_index"):
            self._compose_with_bundle(bundle)

    def test_missing_usdo_store_fails(self):
        from system.application_composition import ApplicationCompositionError
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        bundle["commit"]["usdo_store"] = None
        with pytest.raises(ApplicationCompositionError, match="usdo_store"):
            self._compose_with_bundle(bundle)

    def test_missing_version_store_fails(self):
        from system.application_composition import ApplicationCompositionError
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        bundle["commit"]["version_store"] = None
        with pytest.raises(ApplicationCompositionError, match="version_store"):
            self._compose_with_bundle(bundle)

    def test_malformed_commit_store_fails(self):
        from system.application_composition import ApplicationCompositionError
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        bundle["commit"]["commit_store"] = "not-a-store"
        with pytest.raises(ApplicationCompositionError):
            self._compose_with_bundle(bundle)

    def test_malformed_structural_store_fails(self):
        from system.application_composition import ApplicationCompositionError
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        bundle["commit"]["structural_store"] = 42
        with pytest.raises(ApplicationCompositionError):
            self._compose_with_bundle(bundle)

    def test_malformed_vector_index_fails(self):
        from system.application_composition import ApplicationCompositionError
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        bundle["commit"]["vector_index"] = object()
        with pytest.raises(ApplicationCompositionError):
            self._compose_with_bundle(bundle)

    def test_malformed_usdo_store_fails(self):
        from system.application_composition import ApplicationCompositionError
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        bundle["commit"]["usdo_store"] = []
        with pytest.raises(ApplicationCompositionError):
            self._compose_with_bundle(bundle)

    def test_malformed_version_store_fails(self):
        from system.application_composition import ApplicationCompositionError
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        bundle = create_si2a_provider_bundle()
        bundle["commit"]["version_store"] = {}
        with pytest.raises(ApplicationCompositionError):
            self._compose_with_bundle(bundle)

    def test_inmemory_commit_store_rejected(self):
        from system.application_composition import ApplicationCompositionError
        from knowledge_curator.adapters.in_memory_commit import InMemoryDocumentCommitStore

        bundle = {
            "commit": {
                "commit_store": InMemoryDocumentCommitStore(),
                "structural_store": None,
                "vector_index": None,
                "usdo_store": None,
                "version_store": None,
            },
        }
        with pytest.raises(ApplicationCompositionError, match="must not use test"):
            self._compose_with_bundle(bundle)

    def _valid_commit_dict(self):
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle

        b = create_si2a_provider_bundle()
        return dict(b["commit"])

    def test_inmemory_structural_store_rejected(self):
        from system.application_composition import ApplicationCompositionError
        from knowledge_curator.adapters.in_memory_commit import InMemoryStructuralKnowledgeStore

        commit = self._valid_commit_dict()
        commit["structural_store"] = InMemoryStructuralKnowledgeStore()
        bundle = {"commit": commit}
        with pytest.raises(ApplicationCompositionError, match="must not use test"):
            self._compose_with_bundle(bundle)

    def test_inmemory_vector_index_rejected(self):
        from system.application_composition import ApplicationCompositionError
        from knowledge_curator.adapters.in_memory_commit import InMemoryVectorIndex

        commit = self._valid_commit_dict()
        commit["vector_index"] = InMemoryVectorIndex()
        bundle = {"commit": commit}
        with pytest.raises(ApplicationCompositionError, match="must not use test"):
            self._compose_with_bundle(bundle)

    def test_inmemory_usdo_store_rejected(self):
        from system.application_composition import ApplicationCompositionError
        from knowledge_curator.adapters.in_memory_commit import InMemoryUSDOStore

        commit = self._valid_commit_dict()
        commit["usdo_store"] = InMemoryUSDOStore()
        bundle = {"commit": commit}
        with pytest.raises(ApplicationCompositionError, match="must not use test"):
            self._compose_with_bundle(bundle)

    def test_inmemory_version_store_rejected(self):
        from system.application_composition import ApplicationCompositionError
        from knowledge_curator.adapters.in_memory_commit import InMemoryVersionStore

        commit = self._valid_commit_dict()
        commit["version_store"] = InMemoryVersionStore()
        bundle = {"commit": commit}
        with pytest.raises(ApplicationCompositionError, match="must not use test"):
            self._compose_with_bundle(bundle)


class TestSI2ACompositionSuccess:
    def test_valid_testlocal_deps_compose(self):
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle
        from system.application_composition import (
            _extract_commit_deps,
            _validate_commit_deps,
        )

        bundle = create_si2a_provider_bundle()
        deps = _extract_commit_deps(bundle)
        _validate_commit_deps(deps)
        assert deps.commit_store is not None
        assert deps.structural_store is not None
        assert deps.vector_index is not None
        assert deps.usdo_store is not None
        assert deps.version_store is not None

    def test_compose_returns_coordinator(self):
        from system.application_composition import compose_curation_commit_application

        old = os.environ.get("AI4S_SYSTEM_ADAPTER_FACTORY")
        os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = (
            "integration.system.fixtures.si2a_provider:create_si2a_provider_bundle"
        )
        try:
            rt = compose_curation_commit_application()
            assert rt is not None
            assert rt.curator_runtime is not None
            assert rt.commit_coordinator is not None
            from knowledge_curator.core.commit import DocumentCommitCoordinator

            assert isinstance(rt.commit_coordinator, DocumentCommitCoordinator)
        finally:
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old
            else:
                os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)

    def test_extra_commit_group_mcp_tools_unchanged(self):
        """Existing four-tool MCP server still builds with extra commit group."""
        from integration.system.fixtures.si2a_provider import create_si2a_provider_bundle
        from system.composition import compose_system_runtime, CuratorDependencies

        bundle = create_si2a_provider_bundle()
        curator_raw = bundle["curator"]
        deps = CuratorDependencies(
            repository=curator_raw["repository"],
            ontology=curator_raw["ontology"],
            mechanism_validator=curator_raw["mechanism_validator"],
            provider_identity=curator_raw["provider_identity"],
        )
        rt = compose_system_runtime(curator_deps=deps, evidence_deps=None)
        assert rt.curator_runtime is not None

        from knowledge_curator.mcp_server.app import create_mcp_server

        server = create_mcp_server(
            runtime=rt.curator_runtime, evidence_runtime=rt.evidence_runtime
        )
        assert server is not None
