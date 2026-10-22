from database import init_db, load_history, save_results


def test_saves_and_loads_reviews(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    saved = save_results([
        {"review": "Great taste", "label": "positive", "score": 5, "theme": "taste"},
        {"review": "Slow delivery", "label": "negative", "score": 2, "theme": "delivery"},
    ], db)
    assert saved == 2
    assert load_history(db) == [
        {"review": "Great taste", "label": "positive", "score": 5, "theme": "taste"},
        {"review": "Slow delivery", "label": "negative", "score": 2, "theme": "delivery"},
    ]


def test_error_rows_are_not_saved(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    saved = save_results([
        {"review": "Fine", "label": "neutral", "score": 3, "theme": "quality"},
        {"review": "???", "label": "error", "score": None, "theme": ""},
    ], db)
    assert saved == 1
    assert len(load_history(db)) == 1


def test_init_is_safe_to_run_twice(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    init_db(db)
    assert load_history(db) == []
