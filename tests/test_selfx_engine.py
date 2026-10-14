from pathlib import Path

import pytest

from selfx_engine import SelfXEngine


def make_engine(tmp_path: Path) -> SelfXEngine:
    state = tmp_path / "state"
    models = tmp_path / "models"
    project = tmp_path / "project"
    state.mkdir()
    models.mkdir()
    project.mkdir()
    for name in ("app.py", "terminal_ai.py", "litert_api_backend.py"):
        (project / name).write_text("# test fixture\n", encoding="utf-8")
    return SelfXEngine(state, models, project)


def test_diagnostics_are_local_and_persisted(tmp_path):
    engine = make_engine(tmp_path)
    result = engine.diagnose()
    assert result["total"] >= 5
    assert result["status"] in {"healthy", "degraded", "attention"}
    assert (engine.state_dir / "selfx_state.json").is_file()
    assert engine.status()["latest_diagnostic"]["id"] == result["id"]


def test_evaluation_returns_bounded_operational_score(tmp_path):
    engine = make_engine(tmp_path)
    result = engine.evaluate()
    assert 0 <= result["score"] <= 100
    assert result["scope"].startswith("static local operational checks")
    assert len(result["checks"]) == 4


def test_research_note_is_saved_as_unverified(tmp_path):
    engine = make_engine(tmp_path)
    result = engine.add_research("LiteRT API", "Need to verify channel format.", "https://example.com/docs")
    assert result["status"] == "unverified"
    assert engine.status()["research"][0]["id"] == result["id"]


@pytest.mark.parametrize("url", ["file:///etc/passwd", "javascript:alert(1)", "not-a-url"])
def test_research_rejects_non_http_source_urls(tmp_path, url):
    with pytest.raises(ValueError):
        make_engine(tmp_path).add_research("Bad source", source_url=url)


def test_checkpoint_excludes_secret_files_and_restore_is_confirmed(tmp_path):
    engine = make_engine(tmp_path)
    (engine.state_dir / "memory.json").write_text('{"facts":[1]}', encoding="utf-8")
    (engine.state_dir / "hf_token").write_text("must-not-be-backed-up", encoding="utf-8")
    (engine.state_dir / "web_settings.json").write_text('{"mode":"local"}', encoding="utf-8")
    checkpoint = engine.create_checkpoint()
    folder = engine.backup_dir / checkpoint["id"]
    assert (folder / "memory.json").is_file()
    assert (folder / "web_settings.json").is_file()
    assert not (folder / "hf_token").exists()
    with pytest.raises(ValueError):
        engine.restore_checkpoint(checkpoint["id"], False)
    (engine.state_dir / "memory.json").write_text('{"facts":[2]}', encoding="utf-8")
    restored = engine.restore_checkpoint(checkpoint["id"], True)
    assert restored["safety_checkpoint"]
    assert (engine.state_dir / "memory.json").read_text(encoding="utf-8") == '{"facts":[1]}'


def test_restore_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        make_engine(tmp_path).restore_checkpoint("../outside", True)
