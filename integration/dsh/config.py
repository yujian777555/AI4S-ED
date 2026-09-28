"""DSH smoke configuration (Phase 3.0).

Secrets come only from the environment. Never log or serialize API keys.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PROVIDER = "deepseek-official"
DEFAULT_PROFILE = "sdk-minimal"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_MAX_TOKENS = 256
REVIEWED_DSH_REVISION = "4878cdabd87d4041bdaff61d04c966883b9fd07a"
REVIEWED_DSH_RELEASE = "0.2.0-rc.1"


@dataclass(frozen=True)
class DshSmokeConfig:
    """Runtime settings for one DSH + DeepSeek smoke run."""

    provider: str
    model: str
    profile: str
    dsh_home: str
    workspace: str
    api_key_present: bool
    base_url: str | None
    max_tokens: int
    session_id: str
    request_timeout_seconds: float

    def public_dict(self) -> dict[str, object]:
        """Serializable view with no secret material."""
        return {
            "provider": self.provider,
            "model": self.model,
            "profile": self.profile,
            "dsh_home": self.dsh_home,
            "workspace": self.workspace,
            "api_key_present": self.api_key_present,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "session_id": self.session_id,
            "request_timeout_seconds": self.request_timeout_seconds,
        }


class ConfigError(ValueError):
    """Raised when smoke configuration is invalid."""


def _require_absolute_existing_or_creatable(path_str: str, label: str) -> str:
    if not path_str or not path_str.strip():
        raise ConfigError(f"{label} must be non-empty")
    path = Path(path_str)
    if not path.is_absolute():
        raise ConfigError(f"{label} must be an absolute path: {path_str}")
    return str(path.resolve())


def load_config(
    *,
    environ: dict[str, str] | None = None,
    session_id: str = "ai4s-ed-dsh-smoke-001",
) -> DshSmokeConfig:
    """Load smoke settings from the environment.

    Required: DSH_HOME (or an isolated temp home is created only when explicitly
    requested by the caller via env DSH_HOME_ALLOW_TEMP=1). Model comes from
    DSH_MODEL. API key is only presence-checked via DEEPSEEK_API_KEY.
    """
    env = dict(environ if environ is not None else os.environ)

    dsh_home = env.get("DSH_HOME", "").strip()
    if not dsh_home:
        if env.get("DSH_HOME_ALLOW_TEMP", "").strip() == "1":
            dsh_home = tempfile.mkdtemp(prefix="ai4s-ed-dsh-home-")
        else:
            raise ConfigError("DSH_HOME must be set to an isolated absolute path")

    workspace = env.get("DSH_WORKSPACE", "").strip()
    if not workspace:
        workspace = str(Path(tempfile.gettempdir()) / "ai4s-ed-dsh-workspace")
    Path(workspace).mkdir(parents=True, exist_ok=True)
    Path(dsh_home).mkdir(parents=True, exist_ok=True)

    dsh_home = _require_absolute_existing_or_creatable(dsh_home, "DSH_HOME")
    workspace = _require_absolute_existing_or_creatable(workspace, "workspace")

    model = env.get("DSH_MODEL", DEFAULT_MODEL).strip()
    if not model:
        raise ConfigError("DSH_MODEL must be non-empty")

    provider = env.get("DSH_PROVIDER", DEFAULT_PROVIDER).strip() or DEFAULT_PROVIDER
    profile = env.get("DSH_PROFILE", DEFAULT_PROFILE).strip() or DEFAULT_PROFILE

    api_key = env.get("DEEPSEEK_API_KEY", "")
    base_url = env.get("DEEPSEEK_BASE_URL", "").strip() or None

    max_tokens_raw = env.get("DSH_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)).strip()
    try:
        max_tokens = int(max_tokens_raw)
    except ValueError as exc:
        raise ConfigError(f"DSH_MAX_TOKENS must be an integer: {max_tokens_raw}") from exc
    if max_tokens <= 0:
        raise ConfigError("DSH_MAX_TOKENS must be positive")

    timeout_raw = env.get("DSH_REQUEST_TIMEOUT_SECONDS", "60").strip()
    try:
        request_timeout_seconds = float(timeout_raw)
    except ValueError as exc:
        raise ConfigError(
            f"DSH_REQUEST_TIMEOUT_SECONDS must be a number: {timeout_raw}"
        ) from exc

    return DshSmokeConfig(
        provider=provider,
        model=model,
        profile=profile,
        dsh_home=dsh_home,
        workspace=workspace,
        api_key_present=bool(api_key.strip()),
        base_url=base_url,
        max_tokens=max_tokens,
        session_id=session_id,
        request_timeout_seconds=request_timeout_seconds,
    )


def mask_secret(value: str) -> str:
    """Mask a secret for diagnostics. Never return the original."""
    if not value:
        return ""
    return f"***{len(value)}***"
