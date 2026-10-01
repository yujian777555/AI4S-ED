"""SI-2B revision application composition tests (plan section 16)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestSI2BCompositionFailClosed:
    def _compose_with_bundle(self, bundle: dict):
        from system.revision_application_composition import (
            _extract_revision_deps,
            _validate_revision_deps,
        )
        deps = _extract_revision_deps(bundle)
        _validate_revision_deps(deps)
        return deps

    def test_missing_revision_group_fails(self):
        from system.revision_application_composition import (
            RevisionCompositionError,
            _extract_revision_deps,
        )
        bundle = {"curator": {"repository": None}, "commit": {"commit_store": None}}
        with pytest.raises(RevisionCompositionError, match="revision"):
            _extract_revision_deps(bundle)

    def test_missing_source_registry_fails(self):
        from system.revision_application_composition import RevisionCompositionError
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["source_registry"] = None
        with pytest.raises(RevisionCompositionError, match="source_registry"):
            self._compose_with_bundle(bundle)

    def test_missing_lifecycle_store_fails(self):
        from system.revision_application_composition import RevisionCompositionError
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["lifecycle_store"] = None
        with pytest.raises(RevisionCompositionError, match="lifecycle_store"):
            self._compose_with_bundle(bundle)

    def test_missing_event_outbox_fails(self):
        from system.revision_application_composition import RevisionCompositionError
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["event_outbox"] = None
        with pytest.raises(RevisionCompositionError, match="event_outbox"):
            self._compose_with_bundle(bundle)

    def test_missing_publication_store_fails(self):
        from system.revision_application_composition import RevisionCompositionError
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["publication_store"] = None
        with pytest.raises(RevisionCompositionError, match="publication_store"):
            self._compose_with_bundle(bundle)

    def test_malformed_source_registry_fails(self):
        from system.revision_application_composition import RevisionCompositionError
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["source_registry"] = "not-a-registry"
        with pytest.raises(RevisionCompositionError):
            self._compose_with_bundle(bundle)

    def test_malformed_lifecycle_store_fails(self):
        from system.revision_application_composition import RevisionCompositionError
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["lifecycle_store"] = 42
        with pytest.raises(RevisionCompositionError):
            self._compose_with_bundle(bundle)

    def test_malformed_event_outbox_fails(self):
        from system.revision_application_composition import RevisionCompositionError
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["event_outbox"] = object()
        with pytest.raises(RevisionCompositionError):
            self._compose_with_bundle(bundle)

    def test_malformed_publication_store_fails(self):
        from system.revision_application_composition import RevisionCompositionError
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["publication_store"] = []
        with pytest.raises(RevisionCompositionError):
            self._compose_with_bundle(bundle)

    def test_inmemory_lifecycle_store_rejected(self):
        from system.revision_application_composition import RevisionCompositionError
        from knowledge_curator.adapters.in_memory_lifecycle import InMemoryLifecycleStore
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["lifecycle_store"] = InMemoryLifecycleStore()
        with pytest.raises(RevisionCompositionError, match="must not use test"):
            self._compose_with_bundle(bundle)

    def test_inmemory_event_outbox_rejected(self):
        from system.revision_application_composition import RevisionCompositionError
        from knowledge_curator.adapters.in_memory_lifecycle import InMemoryEventOutbox
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["event_outbox"] = InMemoryEventOutbox()
        with pytest.raises(RevisionCompositionError, match="must not use test"):
            self._compose_with_bundle(bundle)

    def test_inmemory_revision_publication_store_rejected(self):
        from system.revision_application_composition import RevisionCompositionError
        from knowledge_curator.adapters.in_memory_revision_publication import InMemoryRevisionPublicationStore
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["publication_store"] = InMemoryRevisionPublicationStore()
        with pytest.raises(RevisionCompositionError, match="must not use test"):
            self._compose_with_bundle(bundle)

    def test_inmemory_source_version_registry_rejected(self):
        from system.revision_application_composition import RevisionCompositionError
        from knowledge_curator.adapters.in_memory_source_versions import InMemorySourceVersionRegistry
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        bundle = create_si2b_provider_bundle()
        bundle["revision"]["source_registry"] = InMemorySourceVersionRegistry()
        with pytest.raises(RevisionCompositionError, match="must not use test"):
            self._compose_with_bundle(bundle)


class TestSI2BCompositionSuccess:
    def test_valid_testlocal_deps_compose(self):
        from integration.system.fixtures.si2b_provider import create_si2b_provider_bundle
        from system.revision_application_composition import (
            _extract_revision_deps,
            _validate_revision_deps,
        )
        bundle = create_si2b_provider_bundle()
        deps = _extract_revision_deps(bundle)
        _validate_revision_deps(deps)
        assert deps.source_registry is not None
        assert deps.lifecycle_store is not None
        assert deps.event_outbox is not None
        assert deps.publication_store is not None

    def test_compose_returns_all_coordinators(self):
        from system.revision_application_composition import compose_revision_publication_application
        old = os.environ.get("AI4S_SYSTEM_ADAPTER_FACTORY")
        os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = (
            "integration.system.fixtures.si2b_provider:create_si2b_provider_bundle"
        )
        try:
            rt = compose_revision_publication_application()
            from knowledge_curator.core.commit import DocumentCommitCoordinator
            from knowledge_curator.core.lifecycle import LifecycleRevisionCoordinator
            from knowledge_curator.core.revision_publication import RevisionPublicationCoordinator

            assert isinstance(rt.document_commit_coordinator, DocumentCommitCoordinator)
            assert isinstance(rt.lifecycle_coordinator, LifecycleRevisionCoordinator)
            assert isinstance(rt.revision_publication_coordinator, RevisionPublicationCoordinator)
        finally:
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old
            else:
                os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)

    def test_shared_version_store_identity(self):
        from system.revision_application_composition import compose_revision_publication_application
        old = os.environ.get("AI4S_SYSTEM_ADAPTER_FACTORY")
        os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = (
            "integration.system.fixtures.si2b_provider:create_si2b_provider_bundle"
        )
        try:
            rt = compose_revision_publication_application()
            assert rt.lifecycle_coordinator._versions is rt.document_commit_coordinator._versions
            assert rt.revision_publication_coordinator._versions is rt.document_commit_coordinator._versions
        finally:
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old
            else:
                os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)

    def test_shared_commit_store_identity(self):
        from system.revision_application_composition import compose_revision_publication_application
        old = os.environ.get("AI4S_SYSTEM_ADAPTER_FACTORY")
        os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = (
            "integration.system.fixtures.si2b_provider:create_si2b_provider_bundle"
        )
        try:
            rt = compose_revision_publication_application()
            assert rt.revision_publication_coordinator._commit_store is rt.document_commit_coordinator._commits
        finally:
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old
            else:
                os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)

    def test_split_brain_rejected(self):
        from system.revision_application_composition import (
            RevisionCompositionError,
            _reject_split_brain,
        )
        bundle = {
            "revision": {
                "version_store": "some-other-store",
                "source_registry": None,
            }
        }
        with pytest.raises(RevisionCompositionError, match="split-brain"):
            _reject_split_brain(bundle)

    def test_provider_factory_invoked_once(self):
        """Verify the composition loads the provider bundle exactly once."""
        call_count = [0]
        original_loader = None

        import system.revision_application_composition as mod

        original_loader = mod.load_provider_bundle

        def counting_loader(*args, **kwargs):
            call_count[0] += 1
            return original_loader(*args, **kwargs)

        mod.load_provider_bundle = counting_loader
        old = os.environ.get("AI4S_SYSTEM_ADAPTER_FACTORY")
        os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = (
            "integration.system.fixtures.si2b_provider:create_si2b_provider_bundle"
        )
        try:
            mod.compose_revision_publication_application()
            assert call_count[0] == 1, f"expected 1 provider load, got {call_count[0]}"
        finally:
            mod.load_provider_bundle = original_loader
            if old is not None:
                os.environ["AI4S_SYSTEM_ADAPTER_FACTORY"] = old
            else:
                os.environ.pop("AI4S_SYSTEM_ADAPTER_FACTORY", None)
