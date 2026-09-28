"""Official DeepSeek Harness + DeepSeek API smoke runner (Phase 3.0).

Uses only:

    from deepseek_harness import DeepSeekHarness

No requests/httpx/OpenAI direct API calls. No secrets in output.
"""

from __future__ import annotations

import json
import platform
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from integration.dsh.config import (
    REVIEWED_DSH_RELEASE,
    REVIEWED_DSH_REVISION,
    DshSmokeConfig,
    load_config,
)

SENTINEL_TOKEN = "AI4S_ED_DSH_SMOKE_2026"


@dataclass
class SmokeResult:
    """Machine-readable smoke outcome without secret material."""

    sdk_version: str = ""
    runtime_version: str = ""
    reviewed_dsh_revision: str = REVIEWED_DSH_REVISION
    reviewed_dsh_release: str = REVIEWED_DSH_RELEASE
    installed_sdk_matches_reviewed: bool = False
    python_version: str = ""
    platform: str = ""
    profile: str = ""
    provider: str = ""
    model: str = ""
    session_id: str = ""
    live_test_attempted: bool = False
    live_test_passed: bool = False
    session_continuity_passed: bool = False
    finish_reasons: list[str] = field(default_factory=list)
    secret_present: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "sdk_version": self.sdk_version,
            "runtime_version": self.runtime_version,
            "reviewed_dsh_revision": self.reviewed_dsh_revision,
            "reviewed_dsh_release": self.reviewed_dsh_release,
            "installed_sdk_matches_reviewed": self.installed_sdk_matches_reviewed,
            "python_version": self.python_version,
            "platform": self.platform,
            "profile": self.profile,
            "provider": self.provider,
            "model": self.model,
            "session_id": self.session_id,
            "live_test_attempted": self.live_test_attempted,
            "live_test_passed": self.live_test_passed,
            "session_continuity_passed": self.session_continuity_passed,
            "finish_reasons": self.finish_reasons,
            "secret_present": self.secret_present,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _sdk_version() -> str:
    try:
        import importlib.metadata as md

        return md.version("deepseek-harness-sdk")
    except Exception:
        return "unknown"


def _runtime_version() -> str:
    try:
        import importlib.metadata as md

        return md.version("deepseek-harness-runtime-bin")
    except Exception:
        return "unknown"


def build_harness_config(config: DshSmokeConfig, api_key: str | None = None):
    """Create DeepSeekHarnessConfig with isolated home/workspace and explicit provider/model."""
    from deepseek_harness import DeepSeekHarnessConfig

    return DeepSeekHarnessConfig(
        provider=config.provider,
        model=config.model,
        profile=config.profile,
        dsh_home=config.dsh_home,
        cwd=config.workspace,
        max_tokens=config.max_tokens,
        request_timeout_seconds=config.request_timeout_seconds,
        base_url=config.base_url,
        api_key=api_key,
    )


def run_live_smoke(
    config: DshSmokeConfig,
    *,
    api_key: str | None = None,
) -> SmokeResult:
    """Run the two-turn same-session live smoke through the official SDK.

    Turn 1 stores a sentinel. Turn 2 recalls it in the same session_id.
    """
    result = SmokeResult(
        sdk_version=_sdk_version(),
        runtime_version=_runtime_version(),
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        profile=config.profile,
        provider=config.provider,
        model=config.model,
        session_id=config.session_id,
        secret_present=config.api_key_present,
    )
    result.installed_sdk_matches_reviewed = result.sdk_version.startswith("0.2.0")

    if not api_key and not config.api_key_present:
        result.errors.append("LIVE_SMOKE_NOT_RUN_NO_SECRET")
        result.warnings.append("DEEPSEEK_API_KEY not present")
        return result

    if not result.installed_sdk_matches_reviewed:
        result.warnings.append(
            f"SDK version {result.sdk_version} != reviewed {REVIEWED_DSH_RELEASE}"
        )

    result.live_test_attempted = True

    try:
        from deepseek_harness import DeepSeekHarness
    except Exception as exc:
        result.errors.append(f"sdk import failed: {type(exc).__name__}: {exc}")
        return result

    harness_config = build_harness_config(config, api_key=api_key)
    session_id = config.session_id

    try:
        with DeepSeekHarness(harness_config) as harness:
            turn1_prompt = (
                f"Remember the sentinel {SENTINEL_TOKEN}. "
                "Reply briefly that you stored it."
            )
            turn1 = harness.run(turn1_prompt, session_id=session_id)
            result.finish_reasons.append(turn1.finish_reason or "unknown")
            if not (turn1.final_response or "").strip():
                result.errors.append("turn1 final_response empty")
            if turn1.session_id != session_id:
                result.errors.append(
                    f"turn1 session_id mismatch: {turn1.session_id!r} != {session_id!r}"
                )

            turn2_prompt = (
                "What sentinel did I ask you to remember in the previous turn? "
                "Return only the sentinel."
            )
            turn2 = harness.run(turn2_prompt, session_id=session_id)
            result.finish_reasons.append(turn2.finish_reason or "unknown")
            final2 = (turn2.final_response or "").strip()
            if not final2:
                result.errors.append("turn2 final_response empty")
            if SENTINEL_TOKEN not in final2:
                result.errors.append(
                    "turn2 did not return expected sentinel (session continuity failed)"
                )
            else:
                result.session_continuity_passed = True

            if turn2.session_id != session_id:
                result.errors.append(
                    f"turn2 session_id mismatch: {turn2.session_id!r} != {session_id!r}"
                )

        result.live_test_passed = result.session_continuity_passed and not result.errors
    except Exception as exc:
        result.errors.append(f"live smoke failed: {type(exc).__name__}: {exc}")
        result.live_test_passed = False

    return result


def write_result(path: Path, result: SmokeResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_json(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    import os

    try:
        config = load_config(session_id=f"ai4s-ed-dsh-smoke-{uuid.uuid4().hex[:8]}")
    except Exception as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    api_key = os.environ.get("DEEPSEEK_API_KEY") or None
    result = run_live_smoke(config, api_key=api_key)
    out = Path("results/phase-03-0-dsh-smoke.json")
    write_result(out, result)
    print(json.dumps(result.to_json(), indent=2, ensure_ascii=False))
    return 0 if result.live_test_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
