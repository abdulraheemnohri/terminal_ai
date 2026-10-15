from application.learning import LearningStore


def test_learning_store_persists_verified_outcomes_and_summary(tmp_path):
    path = tmp_path / "state" / "learning.sqlite3"
    store = LearningStore(path)
    record = store.record(
        task_type="research", algorithm="evidence-first",
        outcome="success", rating=5, verified=True,
    )
    assert record["verified"] is True
    assert store.summary()["count"] == 1
    assert store.recommend("research", "direct-verify")["adapted"] is False

    reopened = LearningStore(path)
    assert reopened.summary()["groups"][0]["samples"] == 1


def test_learning_requires_explicit_verified_outcome(tmp_path):
    import pytest

    store = LearningStore(tmp_path / "learning.sqlite3")
    with pytest.raises(ValueError, match="verified"):
        store.record(
            task_type="research", algorithm="evidence-first",
            outcome="success", rating=5, verified=False,
        )
    assert store.summary()["count"] == 0


def test_learning_rejects_untrusted_or_invalid_fields(tmp_path):
    import pytest

    store = LearningStore(tmp_path / "learning.sqlite3")
    for payload in [
        {"task_type": [], "algorithm": "evidence-first", "outcome": "success", "rating": 5, "verified": True},
        {"task_type": "research", "algorithm": "shell", "outcome": "success", "rating": 5, "verified": True},
        {"task_type": "research", "algorithm": "evidence-first", "outcome": "success", "rating": True, "verified": True},
    ]:
        with pytest.raises(ValueError):
            store.record(**payload)


def test_learning_adapts_only_after_repeated_reviewed_outcomes(tmp_path):
    store = LearningStore(tmp_path / "learning.sqlite3")
    for _ in range(3):
        store.record(task_type="research", algorithm="decompose-and-verify",
                     outcome="success", rating=5, verified=True)
    choice = store.recommend("research", "evidence-first")
    assert choice["adapted"] is True
    assert choice["algorithm"] == "decompose-and-verify"


def test_learning_retention_is_bounded_by_configured_limit(tmp_path):
    import application.learning as learning

    store = learning.LearningStore(tmp_path / "learning.sqlite3")
    original_limit = learning._MAX_RECORDS
    learning._MAX_RECORDS = 2
    try:
        for outcome in ("success", "partial", "failure"):
            store.record(task_type="writing", algorithm="direct-verify",
                         outcome=outcome, rating=3, verified=True)
        assert store.summary()["count"] == 2
    finally:
        learning._MAX_RECORDS = original_limit
