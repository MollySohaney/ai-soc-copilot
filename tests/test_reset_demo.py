from __future__ import annotations

import pytest

from db.reset_demo import reset_demo


def test_reset_demo_requires_matching_confirmation(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "demo")
    with pytest.raises(RuntimeError, match="matching"):
        reset_demo(database_name="ai_soc_copilot_demo", confirmation="wrong")


def test_reset_demo_refuses_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="outside"):
        reset_demo(database_name="ai_soc_copilot_demo", confirmation="ai_soc_copilot_demo")


def test_reset_demo_falls_back_to_app_env(monkeypatch):
    """APP_ENV is honored when ENVIRONMENT is unset, so one setting governs both."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="outside"):
        reset_demo(database_name="ai_soc_copilot_demo", confirmation="ai_soc_copilot_demo")


def test_environment_takes_precedence_over_app_env(monkeypatch):
    """An explicit ENVIRONMENT still wins, preserving the existing contract."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_ENV", "development")
    with pytest.raises(RuntimeError, match="outside"):
        reset_demo(database_name="ai_soc_copilot_demo", confirmation="ai_soc_copilot_demo")
