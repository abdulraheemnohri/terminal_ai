"""Unit tests for terminal_ai.py — pure logic only, no network, no API keys."""
import time
from pathlib import Path

import pytest

from terminal_ai import (
    Backend,
    BackendError,
    GoalPlanner,
    HybridBackend,
    Journal,
    KnowledgeGraph,
    Memory,
    Msg,
    PatternLearner,
    SessionManager,
    SettingsManager,
    StatsTracker,
    TaskRouter,
    ToolForge,
    ToolRegistry,
    ModelRegistry,
    parse_tool_calls,
    TOOL_SCHEMA,
)

OPEN = "<tool" + "_call>"
CLOSE = "</tool" + "_call>"


def _call(name: str, args: str = "") -> str:
    return OPEN + '{"name": "%s"%s}' % (name, args) + CLOSE


# ───────────────────────────────────────────────  tool-call parsing  ────────
def test_parse_tool_calls_basic():
    text = "prefix " + _call("remember", ', "args": {"key": "name", "value": "Ada"}') + " suffix"
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "remember"
    assert calls[0]["args"]["key"] == "name"


def test_parse_tool_calls_multiple():
    text = _call("done", ', "args": {"answer": "ok"}') + " middle " + _call("list_goals") + " trailing"
    calls = parse_tool_calls(text)
    assert [c["name"] for c in calls] == ["done", "list_goals"]


def test_parse_tool_calls_malformed_falls_back():
    text = _call("shell", ', "args": {"cmd": "echo hi}broken').replace("}}", "}")
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "shell"


def test_parse_tool_calls_none():
    assert parse_tool_calls("just a normal answer") == []


# ───────────────────────────────────────────────  task router  ─────────────
def test_router_classify_coding():
    router = TaskRouter(ModelRegistry())
    assert router.classify("fix this python bug in my function") == "coding"


def test_router_classify_privacy_overrides():
    router = TaskRouter(ModelRegistry())
    assert router.classify("write a poem, but this is private so keep it local only") == "privacy"


def test_router_classify_simple_chat():
    router = TaskRouter(ModelRegistry())
    assert router.classify("hello there, how are you today?") == "simple_chat"


def test_router_select_backend_coding_routes_to_pro():
    router = TaskRouter(ModelRegistry())
    backend, model = router.select_backend(
        "debug this python code and fix the bug", local_available=False)
    assert backend == "cloud"
    assert model == "gemini-3.1-pro"


def test_router_select_backend_privacy_prefers_local():
    router = TaskRouter(ModelRegistry())
    backend, model = router.select_backend(
        "this is private, answer locally", local_available=True)
    assert backend == "local"
    assert model == "gemma-3-1b-it"


def test_registry_best_for():
    reg = ModelRegistry()
    assert reg.best_for("math").name == "gemini-3-pro"
    assert reg.best_for("coding").name == "gemini-3.1-pro"
    assert reg.get("does-not-exist") is None


# ───────────────────────────────────────────────  memory / graph  ───────────
def test_memory_add_fact_recall_forget():
    m = Memory()
    m.add_fact("favorite_lang", "Python", source="test")
    rec = m.recall("favorite programming language")
    assert any(it.get("k") == "favorite_lang" for it in rec)
    assert m.forget("favorite_lang") >= 1
    assert not any(it.get("k") == "favorite_lang" for it in m.recall("favorite_lang"))


def test_memory_correction_and_prefs():
    m = Memory()
    m.add_correction("name: Bob", "name: Alice")
    m.set_pref("style", "concise")
    assert "style" in m.preferences
    ctx = m.context_block("what is my preferred style")
    assert "PREFERENCES:" in ctx


def test_graph_entities_relations():
    g = KnowledgeGraph()
    g.add_entity("ada", "person")
    g.add_relation("ada", "python", "knows")
    assert g.query(entity="ada")
    assert not g.query(entity="nobody")
    ctx = g.context_block("does ada know python")
    assert "ada" in ctx and "python" in ctx


def test_goals_lifecycle():
    gp = GoalPlanner()
    g = gp.add("ship v4.1")
    assert g.id and g in gp.active()
    gp.add_subgoal(g.id, "write tests")
    assert "write tests" in gp.goals[-1].subgoals
    gp.complete(g.id)
    assert g not in gp.active()
    assert g.status == "done" and g.completed is not None


def test_pattern_learner():
    p = PatternLearner()
    p.record("coding", "gemini-3.1-pro", 10)
    p.record("coding", "gemini-3.1-pro", 12)
    assert p.task_counts["coding"] == 2
    assert p.preferred_model("coding") == "gemini-3.1-pro"
    assert "coding: 2x" in p.summary()


# ───────────────────────────────────────────────  settings  ─────────────────
def test_settings_defaults_and_set():
    s = SettingsManager(path=Path("/tmp/terminal_ai_test_settings.json"))
    assert s.get("mode") in ("auto", "cloud", "local", "hybrid")
    assert s.set("temperature", "0.5") is True
    assert s.get("temperature") == 0.5
    assert s.set("self_critique", "on") is True
    assert s.get("self_critique") is True
    assert s.set("autonomy", "9") is False          # out of range 0..5
    assert s.set("unknown_key", "x") is False
    assert "system" in SettingsManager.LIVE_KEYS


def test_settings_blank_never_touches_disk(tmp_path):
    s = SettingsManager.blank()
    assert s.path is None
    assert s.set("temperature", 0.1) is True       # saves are silent no-ops
    assert s.data["temperature"] == 0.1
    assert not (tmp_path / "settings.json").exists()


def test_settings_load_sanitizes_bad_values(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text('{"mode": "banana", "autonomy": 99, "temperature": "fast"}',
                 encoding="utf-8")
    s = SettingsManager(path=p)
    assert s.get("mode") == "auto"
    assert s.get("autonomy") == 3
    assert s.get("temperature") == 0.8              # cast failure -> default


# ───────────────────────────────────────────────  stats / sessions  ─────────
def test_stats_record_and_summary():
    st = StatsTracker()
    st.record("gemini · test", chars_in=10, chars_out=50, seconds=1.5, tool_calls=2)
    st.record("litert · test", chars_in=5, chars_out=20, seconds=0.5)
    assert st.data["turns"] == 2
    assert st.data["tool_calls"] == 2
    assert "gemini · test" in st.summary()


def test_sessions_save_load(tmp_path):
    sm = SessionManager(dir_path=tmp_path)
    hist = [Msg("user", "hi"), Msg("model", "hello!")]
    p = sm.save("work session", hist)
    assert p.exists()
    loaded = sm.load("work session")
    assert [m.text for m in loaded] == ["hi", "hello!"]
    assert sm.load("missing") == []
    assert "work session" in sm.list_sessions()


# ───────────────────────────────────────────────  tool forge  ──────────────
def test_forge_rejects_dangerous_constructs(tmp_path):
    f = ToolForge(path=tmp_path / "tools.json")
    assert f.forge("bad1", "import os") is False
    assert f.forge("bad2", "x = eval('1+1')") is False


def test_forge_word_boundary_allows_normal_words(tmp_path):
    f = ToolForge(path=tmp_path / "tools.json")
    # "important" contains "import" as substring but must be allowed
    assert f.forge("note", "def tool_impl():\n    return 'this is important'") is True
    fn = f.get("note")
    assert fn() == "this is important"
    assert "note" in f.list_tools()


# ───────────────────────────────────────────────  journal  ──────────────────
def test_journal_write_read(tmp_path):
    j = Journal(path=tmp_path / "journal.md")
    j.write("first entry")
    j.write("second entry")
    j.write("third entry")
    out = j.read(2)
    assert "second entry" in out and "third entry" in out
    assert "first entry" not in out
    assert out.count("## ") == 2


# ───────────────────────────────────────────────  file tools  ──────────────
@pytest.fixture()
def registry(tmp_path):
    reg = ToolRegistry(
        memory=Memory(), graph=KnowledgeGraph(), goals=GoalPlanner(),
        journal=Journal(path=tmp_path / "j.md"),
        forge=ToolForge(path=tmp_path / "tools.json"), workspace=tmp_path,
        confirm_shell=False, shell_timeout=5)
    return reg


def test_safe_path_resolution(registry, tmp_path):
    assert registry._safe_path("sub/x.txt") == (tmp_path / "sub" / "x.txt").resolve()
    home_rel = registry._safe_path("~/x.txt")
    assert str(home_rel).startswith(str(Path.home()))


def test_file_tools_roundtrip(registry):
    assert "wrote" in registry.call("write_file", {"path": "a.txt", "content": "hello world"})
    assert registry.call("read_file", {"path": "a.txt"}) == "hello world"
    assert "appended" in registry.call("append_file", {"path": "a.txt", "content": "!"})
    assert registry.call("read_file", {"path": "a.txt"}) == "hello world!"
    assert "edited" in registry.call(
        "edit_file", {"path": "a.txt", "old": "world", "new": "python"})
    assert registry.call("read_file", {"path": "a.txt"}) == "hello python!"
    assert "copied" in registry.call("copy_file", {"src": "a.txt", "dst": "b.txt"})
    assert registry.call("read_file", {"path": "b.txt"}) == "hello python!"
    assert "deleted" in registry.call("delete_file", {"path": "b.txt"})
    assert "error" in registry.call("read_file", {"path": "b.txt"})


def test_edit_file_ambiguous_match_errors(registry):
    registry.call("write_file", {"path": "dup.txt", "content": "ab ab"})
    out = registry.call("edit_file", {"path": "dup.txt", "old": "ab", "new": "cd"})
    assert out.startswith("error:") and "2 times" in out


def test_list_dir_and_grep(registry):
    registry.call("write_file", {"path": "d/one.txt", "content": "alpha beta"})
    registry.call("write_file", {"path": "d/two.txt", "content": "gamma"})
    listing = registry.call("list_dir", {"path": "d"})
    assert "one.txt" in listing and "two.txt" in listing
    hits = registry.call("grep_files", {"pattern": "alpha", "path": "d"})
    assert "one.txt" in hits and "beta" in hits
    assert "(no matches" in registry.call("grep_files", {"pattern": "zzz", "path": "d"})
    assert "error" in registry.call("grep_files", {"pattern": "[", "path": "d"})


def test_web_search_input_validation(registry):
    assert registry.call("web_search", {"query": "   "}) == "error: empty query"


def test_shell_refuses_dangerous_commands(registry):
    assert "refused" in registry.call("shell", {"cmd": "rm -rf /"})
    assert "error" in registry.call("shell", {"cmd": "   "})


def test_unknown_tool_errors(registry):
    assert "unknown tool" in registry.call("nope", {})


def test_tool_schema_unique_names():
    names = [t["name"] for t in TOOL_SCHEMA]
    assert len(names) == len(set(names))
    for required in ("list_dir", "edit_file", "append_file", "delete_file",
                     "copy_file", "grep_files", "web_search", "done"):
        assert required in names


# ───────────────────────────────────────────────  hybrid backend  ───────────
class FakeBackend(Backend):
    def __init__(self, chunks=None, fail_after=None, fail_immediately=False):
        self.label = "fake"
        self.chunks = chunks or ["hello"]
        self.fail_after = fail_after
        self.fail_immediately = fail_immediately

    def stream(self, system, history, tools=None):
        if self.fail_immediately:
            raise BackendError("immediate boom")
        for i, c in enumerate(self.chunks):
            if self.fail_after is not None and i == self.fail_after:
                raise BackendError("mid-stream boom")
            yield c


def _hybrid(cloud, local):
    return HybridBackend(cloud, local, TaskRouter(ModelRegistry()))


def test_hybrid_falls_back_when_cloud_fails_before_output():
    hb = _hybrid(FakeBackend(fail_immediately=True), FakeBackend(["local", "ok"]))
    out = list(hb.stream("sys", [Msg("user", "write a python function")]))
    assert out == ["local", "ok"]


def test_hybrid_no_duplicate_output_on_midstream_failure():
    hb = _hybrid(FakeBackend(["one", "two"], fail_after=0), FakeBackend(["local"]))
    got = []
    with pytest.raises(BackendError):
        for chunk in hb.stream("sys", [Msg("user", "write a python function")]):
            got.append(chunk)
    assert got == ["one"]          # yielded once, then error — no fallback duplicate


def test_hybrid_uses_cloud_when_healthy():
    hb = _hybrid(FakeBackend(["cloud", "fine"]), FakeBackend(["local"]))
    out = list(hb.stream("sys", [Msg("user", "write a python function")]))
    assert out == ["cloud", "fine"]


# ───────────────────────────────────────────────  gemini retry logic  ───────
def test_gemini_stream_retries_with_backoff(monkeypatch):
    import terminal_ai as tai
    monkeypatch.setattr(tai.time, "sleep", lambda s: None)
    gb = tai.GeminiBackend.__new__(tai.GeminiBackend)
    gb.retries = 2
    attempts = {"n": 0}

    def flaky_once(system, history, tools=None):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient network error")
        yield "recovered"

    gb._stream_once = flaky_once
    assert list(gb.stream("sys", [])) == ["recovered"]
    assert attempts["n"] == 3


def test_gemini_stream_gives_up_after_max_retries(monkeypatch):
    import terminal_ai as tai
    monkeypatch.setattr(tai.time, "sleep", lambda s: None)
    gb = tai.GeminiBackend.__new__(tai.GeminiBackend)
    gb.retries = 1
    attempts = {"n": 0}

    def always_fails(system, history, tools=None):
        attempts["n"] += 1
        raise RuntimeError("down")
        yield  # pragma: no cover

    gb._stream_once = always_fails
    with pytest.raises(RuntimeError):
        list(gb.stream("sys", []))
    assert attempts["n"] == 2       # 1 initial + 1 retry
