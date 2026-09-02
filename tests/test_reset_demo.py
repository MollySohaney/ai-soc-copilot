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
