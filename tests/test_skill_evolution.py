from application.skill_evolution import SkillEvolutionStore


def _create(store):
    return store.create(
        name="Debug startup",
        task_type="debugging",
        rationale="Repeated reviewed incidents benefit from a stable evidence-first checklist.",
        steps=["Capture the complete error", "Reproduce in an isolated environment", "Verify with a regression test"],
        evidence_summary="Three manually reviewed successful debugging outcomes; no raw prompts or credentials.",
    )


def test_skill_proposal_requires_validation_then_human_approval(tmp_path):
    store = SkillEvolutionStore(tmp_path / "skills.sqlite3")
    proposal = _create(store)
    assert proposal["status"] == "proposed"
    assert proposal["executable"] is False

    try:
        store.transition(proposal["id"], "approve", "skip validation")
        assert False, "approval must require validation"
    except ValueError:
        pass

    validated = store.transition(proposal["id"], "validate", "Static checks passed")
    assert validated["status"] == "validated"
    approved = store.transition(proposal["id"], "approve", "Reviewed by operator")
    assert approved["status"] == "approved"
    promoted = store.transition(proposal["id"], "promote", "Approved catalog entry")
    assert promoted["status"] == "promoted"
    assert promoted["executable"] is False


def test_skill_proposal_rejects_executable_content_and_bounds(tmp_path):
    store = SkillEvolutionStore(tmp_path / "skills.sqlite3")
    try:
        store.create(
            name="Unsafe example", task_type="debugging", rationale="A reason",
            steps=["Use eval(user_input) to run the task"], evidence_summary="Reviewed manually",
        )
        assert False, "executable-code patterns must be rejected"
    except ValueError as exc:
        assert "executable-code" in str(exc)

    try:
        store.create(
            name="Bad name!", task_type="debugging", rationale="A reason",
            steps=["one"], evidence_summary="Reviewed manually",
        )
        assert False, "unsafe name should be rejected"
    except ValueError:
        pass


def test_skill_proposal_rejects_invalid_transitions_and_records_notes(tmp_path):
    store = SkillEvolutionStore(tmp_path / "skills.sqlite3")
    proposal = _create(store)
    rejected = store.transition(proposal["id"], "reject", "Not enough evidence")
    assert rejected["status"] == "rejected"
    assert rejected["review_note"] == "Not enough evidence"
    try:
        store.transition(proposal["id"], "promote")
        assert False, "rejected proposals must not be promoted"
    except ValueError:
        pass


def test_skill_proposals_are_persistent_and_filterable(tmp_path):
    path = tmp_path / "skills.sqlite3"
    proposal = _create(SkillEvolutionStore(path))
    reopened = SkillEvolutionStore(path)
    assert reopened.get(proposal["id"])["name"] == "Debug startup"
    assert reopened.list(status="proposed")[0]["id"] == proposal["id"]
