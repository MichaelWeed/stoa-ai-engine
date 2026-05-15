"""Tests for the policy gateway."""

import pytest
from stoa.policy.gateway import PolicyDenied, PolicyGateway, ToolCall


def test_allowed_tool_passes():
    gw = PolicyGateway()
    gw.authorize(ToolCall(tool="http_get"))


def test_denied_tool_raises():
    gw = PolicyGateway()
    with pytest.raises(PolicyDenied):
        gw.authorize(ToolCall(tool="shell"))


def test_unknown_tool_denied_by_default():
    gw = PolicyGateway()
    with pytest.raises(PolicyDenied, match="no policy rule"):
        gw.authorize(ToolCall(tool="some_unknown_tool"))


def test_is_allowed():
    gw = PolicyGateway()
    assert gw.is_allowed("http_get") is True
    assert gw.is_allowed("shell") is False
    assert gw.is_allowed("nonexistent") is False


def test_summary_returns_all_rules():
    gw = PolicyGateway()
    summary = gw.summary()
    assert "http_get" in summary
    assert "shell" in summary
