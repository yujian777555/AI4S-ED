"""Production provider loading boundary (Phase SI-1).

Deployment contract:
    AI4S_SYSTEM_ADAPTER_FACTORY=package.module:factory_function

The factory returns a dependency bundle for system.composition.

Fail-closed: any missing/invalid provider configuration raises ProviderLoadError
before MCP server startup. Never falls back to InMemory/Fake adapters.
"""

from __future__ import annotations

import importlib
import os
from typing import Any, Callable, Optional

PROVIDER_ENV_VAR = "AI4S_SYSTEM_ADAPTER_FACTORY"


class ProviderLoadError(RuntimeError):
    """Raised when a production provider cannot be loaded or is invalid."""


def _load_factory(spec: str) -> Callable[..., Any]:
    """Import and return the factory callable from 'package.module:attr'."""
    if not spec or ":" not in spec:
        raise ProviderLoadError(
            f"invalid provider spec (expected 'module:factory'): {spec!r}"
        )
    module_name, attr_name = spec.split(":", 1)
    module_name = module_name.strip()
    attr_name = attr_name.strip()
    if not module_name or not attr_name:
        raise ProviderLoadError(
            f"invalid provider spec (empty module or factory): {spec!r}"
        )
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise ProviderLoadError(
            f"provider module import failed: {module_name}: {exc}"
        ) from exc
    if not hasattr(module, attr_name):
        raise ProviderLoadError(
            f"provider factory not found: {module_name}.{attr_name}"
        )
    factory = getattr(module, attr_name)
    if not callable(factory):
        raise ProviderLoadError(
            f"provider factory is not callable: {module_name}.{attr_name}"
        )
    return factory


def _validate_bundle(bundle: Any) -> Any:
    """Validate the dependency bundle shape returned by the factory."""
    if bundle is None:
        raise ProviderLoadError("provider factory returned None")
    # Accept either a mapping-like or an object with expected attributes.
    if isinstance(bundle, dict):
        if "curator" not in bundle:
            raise ProviderLoadError("dependency bundle missing 'curator' key")
        return bundle
    if not hasattr(bundle, "curator"):
        raise ProviderLoadError(
            "dependency bundle missing 'curator' attribute"
        )
    return bundle


def load_provider_bundle(
    spec: Optional[str] = None,
    *,
    environ: Optional[dict[str, str]] = None,
) -> Any:
    """Load and validate the production provider dependency bundle.

    Args:
        spec: explicit 'module:factory' string; if None, read from environ.
        environ: environment mapping; defaults to os.environ.

    Returns:
        The validated dependency bundle from the factory.

    Raises:
        ProviderLoadError: on any missing/invalid provider configuration.
    """
    env = environ if environ is not None else os.environ
    raw_spec = spec if spec is not None else env.get(PROVIDER_ENV_VAR, "")
    if not raw_spec or not raw_spec.strip():
        raise ProviderLoadError(
            f"missing production provider: set {PROVIDER_ENV_VAR}=package.module:factory"
        )
    factory = _load_factory(raw_spec.strip())
    try:
        bundle = factory()
    except Exception as exc:
        raise ProviderLoadError(
            f"provider factory raised exception: {raw_spec}: {exc}"
        ) from exc
    return _validate_bundle(bundle)
