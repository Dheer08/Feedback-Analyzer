import requests

import app


def test_summary_ignores_failed_reviews():
    results = [
        {"review": "a", "label": "positive", "score": 5, "theme": "taste", "error": ""},
        {"review": "b", "label": "negative", "score": 1, "theme": "delivery", "error": ""},
        {"review": "c", "label": "positive", "score": 4, "theme": "taste", "error": ""},
        {"review": "d", "label": "error", "score": None, "theme": "", "error": "timeout"},
    ]
    s = app.summarize(results)
    assert (s["total"], s["analyzed"], s["failed"]) == (4, 3, 1)
    assert s["avg_score"] == 3.3
    assert s["pct_positive"] == 67  # 2 of the 3 analysed reviews, not 2 of 4
    assert s["top_theme"] == "taste"


def test_summary_when_everything_failed():
    s = app.summarize([{"review": "a", "label": "error", "score": None, "theme": "", "error": "x"}])
    assert s["avg_score"] is None and s["pct_positive"] is None and s["top_theme"] is None


def test_unreachable_backend_returns_error_row(monkeypatch):
    def refuse(*args, **kwargs):
        raise requests.ConnectionError("Connection refused")
    monkeypatch.setattr(app.requests, "post", refuse)
    row = app.analyze_review("Great food")
    assert row["label"] == "error"
    assert "Connection refused" in row["error"]
