"""Keyless config contract tests for Phase 3.0 DSH smoke settings."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from integration.dsh.config import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    ConfigError,
    load_config,
    mask_secret,
)


def test_load_config_requires_dsh_home():
    with pytest.raises(ConfigError):
        load_config(environ={})


def test_load_config_rejects_relative_dsh_home():
    with pytest.raises(ConfigError):
        load_config(environ={"DSH_HOME": "relative/path"})


def test_load_config_accepts_absolute_isolated_home(tmp_path: Path):
    home = tmp_path / "dsh-home"
    env = {"DSH_HOME": str(home), "DSH_WORKSPACE": str(tmp_path / "ws")}
    cfg = load_config(environ=env)
    assert cfg.dsh_home == str(home.resolve())
    assert Path(cfg.dsh_home).is_dir()
    assert cfg.provider == DEFAULT_PROVIDER
    assert cfg.model == DEFAULT_MODEL
    assert cfg.max_tokens == DEFAULT_MAX_TOKENS
    assert cfg.api_key_present is False


def test_load_config_reads_model_provider_and_key_presence(tmp_path: Path):
    env = {
        "DSH_HOME": str(tmp_path / "home"),
        "DSH_WORKSPACE": str(tmp_path / "ws"),
        "DSH_MODEL": "my-custom-model",
        "DSH_PROVIDER": "deepseek-official",
        "DEEPSEEK_API_KEY": "sk-not-a-real-key-for-unit-test",
        "DEEPSEEK_BASE_URL": "https://example.invalid/v1",
    }
    cfg = load_config(environ=env)
    assert cfg.model == "my-custom-model"
    assert cfg.provider == "deepseek-official"
    assert cfg.api_key_present is True
    assert cfg.base_url == "https://example.invalid/v1"
    public = cfg.public_dict()
    assert "api_key" not in public
    assert "DEEPSEEK_API_KEY" not in str(public)


def test_load_config_rejects_bad_max_tokens(tmp_path: Path):
    env = {
        "DSH_HOME": str(tmp_path / "h"),
        "DSH_WORKSPACE": str(tmp_path / "w"),
        "DSH_MAX_TOKENS": "not-a-number",
    }
    with pytest.raises(ConfigError):
        load_config(environ=env)


def test_mask_secret_never_reveals_value():
    secret = "sk-super-secret-value-123"
    masked = mask_secret(secret)
    assert secret not in masked
    assert masked.startswith("***")


def test_config_public_dict_has_no_secret_fields(tmp_path: Path):
    env = {
        "DSH_HOME": str(tmp_path / "h"),
        "DSH_WORKSPACE": str(tmp_path / "w"),
        "DEEPSEEK_API_KEY": "sk-abc",
    }
    cfg = load_config(environ=env)
    dumped = repr(cfg)
    assert "sk-abc" not in dumped
