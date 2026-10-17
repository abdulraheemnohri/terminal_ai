from command_control import CommandControl


def test_policy_defaults_are_safe_and_wal_enabled(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    policy = control.get_policy()
    assert policy["auto_execute"] is False
    assert "python" in policy["allowlist"]
    assert control.verify_audit()["valid"] is True
    import sqlite3
    with sqlite3.connect(tmp_path / "control.sqlite3") as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_approval_is_a_decision_not_execution(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    queued = control.queue("workspace", "inspect", {"path": "README.md"})
    reviewed = control.review(queued["id"], True)
    assert reviewed["status"] == "approved"
    assert reviewed["arguments"] == {"path": "README.md"}
    assert control.verify_audit()["valid"] is True


def test_policy_never_allows_hard_denied_commands(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    policy = control.update_policy({"allowlist": ["ls", "rm", "python"], "auto_execute": True})
    assert "rm" not in policy["allowlist"]
    assert policy["auto_execute"] is False


def test_skill_import_is_unverified_procedure_text(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    result = control.import_skills({
        "format": "terminal-ai-skills", "version": 1,
        "skills": [{"name": "Safe checklist", "version": "1.0.0",
                    "description": "A test workflow", "steps": ["Inspect", "Validate"]}],
    })
    assert result["imported"][0]["verified"] is False
    exported = control.export_skills()
    assert exported["skills"][0]["verified"] is False
    assert control.verify_audit()["valid"] is True


def test_invalid_skill_package_rejected(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    try:
        control.import_skills({"format": "wrong", "version": 1, "skills": []})
    except ValueError:
        pass
    else:
        raise AssertionError("invalid package should be rejected")


def test_audit_rows_cannot_be_updated_or_deleted(tmp_path):
    import sqlite3

    path = tmp_path / "control.sqlite3"
    control = CommandControl(path)
    control.audit("test", "example", "item", {"safe": True})
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT seq FROM audit_log LIMIT 1").fetchone()
        try:
            db.execute("UPDATE audit_log SET action='tampered' WHERE seq=?", (row[0],))
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("audit updates should be blocked by SQLite trigger")


def test_approved_operation_can_only_be_claimed_once_under_race(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    control = CommandControl(tmp_path / "control.sqlite3")
    queued = control.queue("workspace", "inspect", {"path": "README.md"})
    reviewed = control.review(queued["id"], True)
    assert reviewed["status"] == "approved"

    barrier = Barrier(2)

    def claim():
        barrier.wait(timeout=5)
        try:
            item = control.claim_approved(
                queued["id"], "workspace", "inspect", {"path": "README.md"}
            )
            return ("claimed", item["status"])
        except ValueError:
            return ("rejected", None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))

    assert sum(result[0] == "claimed" for result in results) == 1
    assert sum(result[0] == "rejected" for result in results) == 1
    assert control.get_operation(queued["id"])["status"] == "executing"


def test_approved_operation_claim_is_bound_to_exact_arguments(tmp_path):
    control = CommandControl(tmp_path / "control.sqlite3")
    queued = control.queue("workspace", "inspect", {"path": "README.md"})
    control.review(queued["id"], True)

    try:
        control.claim_approved(
            queued["id"], "workspace", "inspect", {"path": "../secrets.txt"}
        )
    except ValueError as exc:
        assert "arguments do not match" in str(exc)
    else:
        raise AssertionError("a mismatched approval must not be claimable")

    assert control.get_operation(queued["id"])["status"] == "approved"
