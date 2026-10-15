from application.task_intelligence import analyze_task


def test_task_signals_choose_research_when_facts_are_uncertain():
    signals = analyze_task("Research the latest browser automation tools")
    assert signals["task_type"] == "research"
    assert signals["algorithm"] == "evidence-first"
    assert signals["uncertainty_estimate"] >= 0.65


def test_task_signals_choose_test_driven_loop_for_software_debugging():
    signals = analyze_task("Debug the failing test and fix the code")
    assert signals["task_type"] == "debugging"
    assert signals["algorithm"] == "test-driven-loop"
    assert 1 <= signals["complexity_estimate"] <= 10


def test_evidence_changes_uncertainty_without_changing_permissions():
    without = analyze_task("Research browser automation tools", evidence_available=False)
    with_evidence = analyze_task("Research browser automation tools", evidence_available=True)
    assert with_evidence["uncertainty_estimate"] < without["uncertainty_estimate"]
    assert "requires_approval" not in with_evidence


def test_task_signals_validate_input():
    import pytest

    with pytest.raises(ValueError):
        analyze_task(" ")
    with pytest.raises(ValueError):
        analyze_task("x" * 4001)
    with pytest.raises(ValueError):
        analyze_task("inspect", evidence_available="yes")
