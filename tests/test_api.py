import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import api


def fake_llm(monkeypatch, reply=None, error=None):
    def call_llm(text):
        if error:
            raise error
        return reply
    monkeypatch.setattr(api, "call_llm", call_llm)


def test_returns_structured_analysis(monkeypatch):
    fake_llm(monkeypatch, api.LLMAnalysis(label="negative", score=2, theme=" Delivery "))
    result = api.analyze(api.Review(text="Cold food and late delivery."))
    assert (result.label, result.score, result.theme) == ("negative", 2, "delivery")


def test_provider_failure_becomes_502(monkeypatch):
    fake_llm(monkeypatch, error=RuntimeError("503 high demand"))
    with pytest.raises(HTTPException) as exc:
        api.analyze(api.Review(text="Nice"))
    assert exc.value.status_code == 502
    assert "503 high demand" in exc.value.detail


def test_refusal_or_unparseable_reply_becomes_502(monkeypatch):
    fake_llm(monkeypatch, reply=None)
    with pytest.raises(HTTPException) as exc:
        api.analyze(api.Review(text="Nice"))
    assert exc.value.status_code == 502


def test_out_of_range_score_becomes_502(monkeypatch):
    fake_llm(monkeypatch, api.LLMAnalysis(label="positive", score=9, theme="taste"))
    with pytest.raises(HTTPException) as exc:
        api.analyze(api.Review(text="Great"))
    assert exc.value.status_code == 502


def test_schema_rejects_unknown_label():
    with pytest.raises(ValidationError):
        api.LLMAnalysis(label="angry", score=3, theme="x")


def test_empty_review_is_rejected():
    with pytest.raises(ValidationError):
        api.Review(text="")


def test_health_reports_provider_and_model():
    assert api.health() == {"status": "ok", "provider": "openai", "model": "gpt-4.1"}
