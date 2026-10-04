"""Lifecycle visibility helpers (Phase 5.0)."""

from __future__ import annotations

from typing import Optional

from knowledge_curator.adapters.in_memory_lifecycle import (
    InMemoryLifecycleStore,
    InMemoryLifecycleVisibility,
)
from knowledge_curator.ports.version_store import VersionStore


def make_version_visible_fn(version_store: VersionStore):
    """Return VersionVisibleFn: is effective_version_id ancestor-or-self of at_version_id?"""

    def version_visible(effective_version_id: str, at_version_id: Optional[str]) -> bool:
        if at_version_id is None:
            cur = version_store.current_version()
            at_version_id = cur.version_id if cur else None
        if at_version_id is None:
            return True
        if effective_version_id == at_version_id:
            return True
        # Walk prior_version_id chain from at_version_id.
        seen = set()
        cursor = version_store.get_version(at_version_id)
        while cursor is not None and cursor.version_id not in seen:
            seen.add(cursor.version_id)
            if cursor.version_id == effective_version_id:
                return True
            if cursor.prior_version_id is None:
                break
            cursor = version_store.get_version(cursor.prior_version_id)
        return False

    return version_visible


def build_lifecycle_visibility(
    *,
    version_store: VersionStore,
    lifecycle_store: Optional[InMemoryLifecycleStore] = None,
) -> tuple[InMemoryLifecycleStore, InMemoryLifecycleVisibility]:
    store = lifecycle_store or InMemoryLifecycleStore(
        version_visible=make_version_visible_fn(version_store)
    )
    return store, InMemoryLifecycleVisibility(store)
