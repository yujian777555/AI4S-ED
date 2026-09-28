"""Keyless smoke-contract tests for Phase 3.0 DSH runner.

These do not require DEEPSEEK_API_KEY and must not make network calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from integration.dsh.config import REVIEWED_DSH_REVISION, load_config
from integration.dsh.smoke import (
    SENTINEL_TOKEN,
    SmokeResult,
    build_harness_config,
    run_live_smoke,
    write_result,
)


def test_sdk_import_when_installed():
    try:
        import deepseek_harness
    except ImportError:
        pytest.skip("deepseek-harness-sdk not installed in this environment")
    assert hasattr(deepseek_harness, "DeepSeekHarness")


def test_smoke_result_serializes_without_secrets():
    r = SmokeResult(secret_present=False)
    payload = r.to_json()
    text = json.dumps(payload)
    assert "sk-" not in text
    assert payload["reviewed_dsh_revision"] == REVIEWED_DSH_REVISION
    assert payload["live_test_attempted"] is False


def test_run_live_smoke_without_key_reports_not_run(tmp_path: Path):
    env = {
        "DSH_HOME": str(tmp_path / "home"),
        "DSH_WORKSPACE": str(tmp_path / "ws"),
        "DSH_MODEL": "test-model",
    }
    cfg = load_config(environ=env)
    result = run_live_smoke(cfg, api_key=None)
    assert result.live_test_attempted is False
    assert result.live_test_passed is False
    assert any("LIVE_SMOKE_NOT_RUN_NO_SECRET" in e for e in result.errors)


def test_build_harness_config_passes_provider_model_home(tmp_path: Path):
    pytest.importorskip("deepseek_harness")
    env = {
        "DSH_HOME": str(tmp_path / "home"),
        "DSH_WORKSPACE": str(tmp_path / "ws"),
        "DSH_MODEL": "cfg-model",
        "DSH_PROVIDER": "deepseek-official",
        "DSH_PROFILE": "sdk-minimal",
        "DSH_MAX_TOKENS": "128",
    }
    cfg = load_config(environ=env)
    hc = build_harness_config(cfg, api_key=None)
    assert hc.provider == cfg.provider
    assert hc.model == cfg.model
    assert hc.profile == cfg.profile
    assert hc.dsh_home == cfg.dsh_home
    assert hc.cwd == cfg.workspace
    assert hc.max_tokens == 128


def test_write_result_does_not_persist_env_or_key(tmp_path: Path):
    r = SmokeResult(
        sdk_version="0.0.0",
        secret_present=False,
        errors=["LIVE_SMOKE_NOT_RUN_NO_SECRET"],
    )
    out = tmp_path / "smoke.json"
    write_result(out, r)
    text = out.read_text(encoding="utf-8")
    assert "LIVE_SMOKE_NOT_RUN_NO_SECRET" in text
    assert "DEEPSEEK_API_KEY=" not in text
    assert "sk-" not in text


def test_sentinel_token_is_stable():
    assert SENTINEL_TOKEN == "AI4S_ED_DSH_SMOKE_2026"


def test_knowledge_curator_core_has_no_dsh_import():
    forbidden = ("deepseek_harness", "deepseek_harness_sdk", "integration.dsh")
    import sys

    core = "knowledge_curator.core.commit"
    if core not in sys.modules:
        __import__(core)
    src = open(sys.modules[core].__file__, encoding="utf-8").read()
    for token in forbidden:
        assert token not in src


def test_error_paths_config_and_timeout(tmp_path: Path):
    with pytest.raises(Exception):
        load_config(environ={"DSH_HOME": "", "DSH_WORKSPACE": str(tmp_path)})
    with pytest.raises(Exception):
        load_config(
            environ={
                "DSH_HOME": str(tmp_path / "h"),
                "DSH_WORKSPACE": str(tmp_path / "w"),
                "DSH_REQUEST_TIMEOUT_SECONDS": "abc",
            }
        )
