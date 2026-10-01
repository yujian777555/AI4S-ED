"""AI4S-ED system integration package (Phase SI-1).

Production runtime composition / bootstrap boundary.
Does not modify frozen knowledge_curator core.
"""

from system.composition import (
    CuratorDependencies,
    EvidenceDependencies,
    SystemRuntime,
    compose_system_runtime,
)
from system.provider_loader import (
    ProviderLoadError,
    load_provider_bundle,
)

__all__ = [
    "CuratorDependencies",
    "EvidenceDependencies",
    "SystemRuntime",
    "compose_system_runtime",
    "ProviderLoadError",
    "load_provider_bundle",
]
