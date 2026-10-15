from __future__ import annotations

import sqlite3

import pytest

from application.learning import LearningStore


def test_source_ref_makes_learning_record_idempotent(tmp_path):
    store = LearningStore(tmp_path / "learning.sqlite3")
    first = store.record(
        task_type="debugging", algorithm="evidence-first",
        outcome="success", rating=4, verified=True,
        source_ref="recovery:proposal-1",
    )
    replay = store.record(
        task_type="debugging", algorithm="evidence-first",
        outcome="success", rating=4, verified=True,
        source_ref="recovery:proposal-1",
    )
    assert first["id"] == replay["id"]
    assert replay["idempotent_replay"] is True
    assert store.summary()["count"] == 1


def test_source_ref_rejects_conflicting_replay(tmp_path):
    store = LearningStore(tmp_path / "learning.sqlite3")
    store.record(
        task_type="research", algorithm="direct-verify",
        outcome="success", rating=5, verified=True,
        source_ref="recovery:proposal-2",
    )
    with pytest.raises(ValueError, match="different reviewed outcome"):
        store.record(
            task_type="research", algorithm="direct-verify",
            outcome="failure", rating=1, verified=True,
            source_ref="recovery:proposal-2",
        )
    assert store.summary()["count"] == 1


def test_existing_learning_database_migrates_source_ref_column(tmp_path):
    path = tmp_path / "legacy-learning.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("""
            CREATE TABLE task_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                outcome TEXT NOT NULL,
                rating INTEGER NOT NULL,
                verified INTEGER NOT NULL CHECK (verified = 1),
                created_at REAL NOT NULL
            )
        """)
        db.execute(
            "INSERT INTO task_outcomes(task_type, algorithm, outcome, rating, verified, created_at) VALUES(?,?,?,?,1,?)",
            ("debugging", "evidence-first", "success", 4, 123.0),
        )
        db.commit()

    store = LearningStore(path)
    record = store.record(
        task_type="debugging", algorithm="evidence-first",
        outcome="partial", rating=3, verified=True,
        source_ref="recovery:proposal-legacy",
    )
    assert record["id"] == 2
    with sqlite3.connect(path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(task_outcomes)")}
    assert "source_ref" in columns
