"""Unit tests for terminal_ai.py — pure logic only, no network, no API keys."""
from pathlib import Path

import pytest

import terminal_ai as tai
from terminal_ai import (
    Backend,
    BackendError,
    EnvManager,
    GoalPlanner,
    HybridBackend,
    Journal,
    KnowledgeGraph,
    Memory,
    ModelRegistry,
    Msg,
    PatternLearner,
    SessionManager,
    SettingsManager,
    StatsTracker,
    TaskRouter,
    ToolForge,
    ToolRegistry,
    parse_tool_calls,
    TOOL_SCHEMA,
)

OPEN = "<tool" + "_call>"
CLOSE = "</tool" + "_call>"


def _call(name: str, args_json: str = "") -> str:
    return OPEN + '{"name": "%s"%s}' % (name, args_json) + CLOSE


# ───────────────────────────────────────────────  tool-call parsing  ────────
def test_parse_tool_calls_basic():
    text = "prefix " + _call("remember", ', "args": {"key": "name", "value": "Ada"}}') + " suffix"
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "remember"
    assert calls[0]["args"]["key"] == "name"


def test_parse_tool_calls_multiple():
    text = (_call("done", ', "args": {"answer": "ok"}}') + " middle "
            + _call("list_goals") + " trailing")
    calls = parse_tool_calls(text)
    assert [c["name"] for c in calls] == ["done", "list_goals"]


def test_parse_tool_calls_malformed_falls_back():
    text = _call("shell", ', "args": {"cmd": "echo hi}broken')
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "shell"


def test_parse_tool_calls_none():
    assert parse_tool_calls("just a normal answer") == []


def test_parse_tool_calls_args_default_empty():
    calls = parse_tool_calls(_call("list_goals"))
    assert calls[0]["args"] == {}


# ───────────────────────────────────────────────  task router  ─────────────
def test_router_classify_coding():
    router = TaskRouter(ModelRegistry())
    assert router.classify("fix this python bug in my function") == "coding"


def test_router_classify_privacy_overrides():
    router = TaskRouter(ModelRegistry())
    assert router.classify(
        "write a poem, but this is private so keep it local only") == "privacy"


def test_router_classify_simple_chat():
    router = TaskRouter(ModelRegistry())
    assert router.classify("hello there, how are you today?") == "simple_chat"


def test_router_classify_all_task_types():
    router = TaskRouter(ModelRegistry())
    cases = {
        "debug this python function": "coding",
        "analyze and prove this theorem about logic": "complex_reasoning",
        "research the latest news and verify the source": "research",
        "write a creative short story": "creative",
        "calculate the integral and solve the equation": "math",
        "keep this private and offline": "privacy",
    }
    for prompt, expected in cases.items():
        got = router.classify(prompt)
        assert got == expected, f"{prompt!r} → {got}, expected {expected}"


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


def test_router_describe():
    router = TaskRouter(ModelRegistry())
    desc = router.describe("write a python function")
    assert "task=" in desc and "→" in desc


def test_registry_best_for():
    reg = ModelRegistry()
    assert reg.best_for("math").name == "gemini-3-pro"
    assert reg.best_for("coding").name == "gemini-3.1-pro"
    assert reg.best_for("creative").name == "gemini-3.5-flash"
    assert reg.get("does-not-exist") is None
    assert len(reg.all_models()) == len(reg.CLOUD_MODELS) + len(reg.LOCAL_MODELS)


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


def test_memory_episodes_capped():
    m = Memory()
    for i in range(250):
        m.add_episode(f"q{i}", f"a{i}")
    assert len(m.episodes) <= 200


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


def test_goals_context_block():
    gp = GoalPlanner()
    gp.add("learn rust")
    gp.add_subgoal(gp.goals[-1].id, "read book")
    ctx = gp.context_block()
    assert "ACTIVE GOALS" in ctx and "learn rust" in ctx and "read book" in ctx


def test_pattern_learner():
    p = PatternLearner()
    p.record("coding", "gemini-3.1-pro", 10)
    p.record("coding", "gemini-3.1-pro", 12)
    assert p.task_counts["coding"] == 2
    assert p.preferred_model("coding") == "gemini-3.1-pro"
    assert "coding: 2x" in p.summary()
    assert p.most_common_task() == "coding"


def test_meta_learner_best_strategy():
    meta = tai.MetaLearner()
    meta.record("coding", "tool_use", True)
    meta.record("coding", "tool_use", True)
    meta.record("coding", "direct", False)
    assert meta.best_strategy("coding") == "tool_use"
    assert "worked best" in meta.context_block("coding")


# ───────────────────────────────────────────────  settings  ─────────────────
def test_settings_defaults(tmp_path):
    s = SettingsManager(path=tmp_path / "settings.json")
    assert s.get("mode") == "auto"
    assert s.get("temperature") == 0.8
    assert s.get("shell_timeout") == 30
    assert s.get("cloud_retries") == 2
    assert s.get("auto_backup_every") == 0
    assert s.get("autonomy") == 3
    # v4.2 defaults
    assert s.get("debug") is False
    assert s.get("history_limit") == 40
    assert s.get("tool_rounds") == 10
    assert s.get("ask_delete") is True
    assert s.get("env_autoload") is True


def test_settings_set_all_keys(tmp_path):
    s = SettingsManager(path=tmp_path / "settings.json")
    assert s.set("temperature", "0.5") is True
    assert s.get("temperature") == 0.5
    assert s.set("self_critique", "on") is True
    assert s.get("self_critique") is True
    assert s.set("proactive", "yes") is True
    assert s.set("confirm_shell", "off") is True
    assert s.get("confirm_shell") is False
    assert s.set("shell_timeout", "60") is True
    assert s.set("mode", "local") is True
    assert s.set("autonomy", "5") is True
    assert s.get("autonomy") == 5
    # v4.2 keys
    assert s.set("debug", "on") is True
    assert s.get("debug") is True
    assert s.set("tool_rounds", "3") is True
    assert s.get("tool_rounds") == 3
    assert s.set("ask_delete", "off") is True
    assert s.get("ask_delete") is False
    assert s.set("history_limit", "20") is True
    assert s.get("history_limit") == 20
    assert s.set("env_autoload", "no") is True
    assert s.get("env_autoload") is False
    # invalid values rejected
    assert s.set("autonomy", "9") is False
    assert s.set("mode", "banana") is False
    assert s.set("chat_template", "nope") is False
    assert s.set("unknown_key", "x") is False
    assert "system" in SettingsManager.LIVE_KEYS
    assert "temperature" not in SettingsManager.LIVE_KEYS
    assert "debug" in SettingsManager.LIVE_KEYS
    assert "tool_rounds" in SettingsManager.LIVE_KEYS
    assert "ask_delete" in SettingsManager.LIVE_KEYS


def test_settings_persist_roundtrip(tmp_path):
    p = tmp_path / "settings.json"
    s1 = SettingsManager(path=p)
    s1.set("gemini_model", "gemini-3.1-pro")
    s1.set("max_tokens", "2048")
    s2 = SettingsManager(path=p)
    assert s2.get("gemini_model") == "gemini-3.1-pro"
    assert s2.get("max_tokens") == 2048


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


def test_settings_corrupt_file_falls_back(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("not json at all {{{", encoding="utf-8")
    s = SettingsManager(path=p)
    assert s.get("mode") == "auto"


# ───────────────────────────────────────────────  stats / sessions  ─────────
def test_stats_record_and_summary(tmp_path):
    st = StatsTracker(path=tmp_path / "stats.json")
    st.record("gemini · test", chars_in=10, chars_out=50, seconds=1.5,
              tool_calls=2)
    st.record("litert · test", chars_in=5, chars_out=20, seconds=0.5)
    assert st.data["turns"] == 2
    assert st.data["tool_calls"] == 2
    assert "gemini · test" in st.summary()


def test_stats_persist(tmp_path):
    p = tmp_path / "stats.json"
    StatsTracker(path=p).record("b1", 1, 2, 3.0)
    st2 = StatsTracker(path=p)
    assert st2.data["turns"] == 1


def test_sessions_save_load(tmp_path):
    sm = SessionManager(dir_path=tmp_path)
    hist = [Msg("user", "hi"), Msg("model", "hello!")]
    p = sm.save("work session", hist)
    assert p.exists()
    loaded = sm.load("work session")
    assert [m.text for m in loaded] == ["hi", "hello!"]
    assert sm.load("missing") == []
    assert "work session" in sm.list_sessions()


def test_session_name_sanitized(tmp_path):
    sm = SessionManager(dir_path=tmp_path)
    sm.save("weird/../name!", [Msg("user", "x")])
    assert sm.list_sessions() == ["weird_.._name_"]


def test_sessions_corrupt_file(tmp_path):
    sm = SessionManager(dir_path=tmp_path)
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert sm.load("bad") == []


# ───────────────────────────────────────────────  env manager (v4.2)  ──────
def test_env_parse_line():
    assert EnvManager._parse_line("FOO=bar") == ("FOO", "bar")
    assert EnvManager._parse_line("QUOTED=\x22hello world\x22") == ("QUOTED", "hello world")
    assert EnvManager._parse_line("SQ=\x27v\x27") == ("SQ", "v")
    assert EnvManager._parse_line("export PREFIXED=yes") == ("PREFIXED", "yes")
    assert EnvManager._parse_line("# comment") is None
    assert EnvManager._parse_line("no_equals_sign") is None
    assert EnvManager._parse_line("1BAD=x") is None
    assert EnvManager._parse_line("  SPACED =  value  ") == ("SPACED", "value")


def test_env_load_file(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("# comment\n\nFOO=bar\nBAZ=\x22quoted value\x22\nBAD-KEY=x\n",
                 encoding="utf-8")
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    em = EnvManager(env_file=p, workspace=tmp_path)
    n = em.load(apply=False)
    assert n == 2
    assert em._data["FOO"] == "bar"
    assert em._data["BAZ"] == "quoted value"
    assert "BAD-KEY" not in em._data


def test_env_apply_respects_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("TAI_TEST_EXISTING", "original")
    p = tmp_path / ".env"
    p.write_text("TAI_TEST_EXISTING=fromfile\n", encoding="utf-8")
    em = EnvManager(env_file=p, workspace=tmp_path)
    em.load(apply=True)
    import os
    assert os.environ["TAI_TEST_EXISTING"] == "original"   # setdefault, no clobber


def test_env_set_get_unset(tmp_path, monkeypatch):
    monkeypatch.delenv("TAI_TEST_K", raising=False)
    em = EnvManager(env_file=tmp_path / ".env", workspace=tmp_path)
    assert em.set("TAI_TEST_K", "v1") is True
    assert em.get("TAI_TEST_K") == "v1"
    import os
    assert os.environ["TAI_TEST_K"] == "v1"
    assert em.unset("TAI_TEST_K") is True
    assert "TAI_TEST_K" not in os.environ
    assert em.unset("TAI_TEST_MISSING") is False
    assert em.set("1bad key", "x") is False


def test_env_save_roundtrip(tmp_path, monkeypatch):
    monkeypatch.delenv("TAI_TEST_SAVE", raising=False)
    p = tmp_path / ".env"
    em = EnvManager(env_file=p, workspace=tmp_path)
    em.set("TAI_TEST_SAVE", "hello world", persist=False)
    assert em.save() == p
    em2 = EnvManager(env_file=p, workspace=tmp_path)
    assert em2.load(apply=False) >= 1
    assert em2.get("TAI_TEST_SAVE") == "hello world"


def test_env_mask():
    assert EnvManager.mask("GEMINI_API_KEY", "abcdefgh") == "ab***gh"
    assert EnvManager.mask("HF_TOKEN", "xyz") == "***"
    assert EnvManager.mask("MY_SECRET_PASSWORD", "secret123") == "se***23"
    assert EnvManager.mask("PLAIN_VAR", "visible") == "visible"


def test_env_summary_filters_and_masks(tmp_path):
    p = tmp_path / ".env"
    p.write_text("GEMINI_API_KEY=abcdefgh\nPLAIN=visible\n", encoding="utf-8")
    em = EnvManager(env_file=p, workspace=tmp_path)
    em.load(apply=False)
    all_sum = em.summary()
    assert "ab***gh" in all_sum and "abcdefgh" not in all_sum
    assert "visible" in all_sum
    filtered = em.summary("GEMINI")
    assert "PLAIN" not in filtered


def test_env_missing_file(tmp_path):
    em = EnvManager(env_file=tmp_path / "nope.env", workspace=tmp_path)
    assert em.load(apply=True) == 0
    assert em.status() == "(no .env file)"


# ───────────────────────────────────────────────  tool forge  ──────────────
def test_forge_rejects_dangerous_constructs(tmp_path):
    f = ToolForge(path=tmp_path / "tools.json")
    assert f.forge("bad1", "import os") is False
    assert f.forge("bad2", "x = eval('1+1')") is False
    assert f.forge("bad3", "exec('code')") is False


def test_forge_word_boundary_allows_normal_words(tmp_path):
    f = ToolForge(path=tmp_path / "tools.json")
    # "important" contains "import" as substring but must be allowed
    assert f.forge("note", "def tool_impl():\n    return 'this is important'") is True
    fn = f.get("note")
    assert fn() == "this is important"
    assert "note" in f.list_tools()


def test_forge_broken_source_returns_none(tmp_path):
    f = ToolForge(path=tmp_path / "tools.json")
    f.forge("broken", "def tool_impl(:\n  pass")
    assert f.get("broken") is None
    assert f.get("nonexistent") is None


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


def test_journal_context_block(tmp_path):
    j = Journal(path=tmp_path / "journal.md")
    assert j.context_block() == ""                 # empty journal -> no block
    j.write("learned something")
    assert "LAST JOURNAL ENTRY" in j.context_block()


def test_journal_empty(tmp_path):
    j = Journal(path=tmp_path / "journal.md")
    assert j.read() == "(journal is empty)"


# ───────────────────────────────────────────────  file tools  ──────────────
@pytest.fixture()
def registry(tmp_path):
    return ToolRegistry(
        memory=Memory(), graph=KnowledgeGraph(), goals=GoalPlanner(),
        journal=Journal(path=tmp_path / "j.md"),
        forge=ToolForge(path=tmp_path / "tools.json"), workspace=tmp_path,
        confirm_shell=False, shell_timeout=5)


@pytest.fixture()
def env_registry(tmp_path, monkeypatch):
    monkeypatch.delenv("TAI_TOOL_VAR", raising=False)
    em = EnvManager(env_file=tmp_path / ".env", workspace=tmp_path)
    return ToolRegistry(
        memory=Memory(), graph=KnowledgeGraph(), goals=GoalPlanner(),
        journal=Journal(path=tmp_path / "j.md"),
        forge=ToolForge(path=tmp_path / "tools.json"), workspace=tmp_path,
        confirm_shell=False, shell_timeout=5, env=em, ask_delete=False)


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


def test_file_tools_errors(registry):
    assert "error" in registry.call("read_file", {"path": "missing.txt"})
    assert "error" in registry.call("copy_file", {"src": "nope", "dst": "x"})
    assert "error" in registry.call("edit_file", {"path": "missing.txt", "old": "a", "new": "b"})
    assert "error" in registry.call("web_fetch", {"url": "ftp://bad"})
    assert "error" in registry.call("delete_file", {"path": "missing.txt"})


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
    assert "error" in registry.call("list_dir", {"path": "missing"})


def test_memory_tools(registry):
    assert "remembered" in registry.call("remember", {"key": "lang", "value": "py"})
    assert "lang" in registry.call("search_memory", {"query": "lang"})
    assert "forgot" in registry.call("forget", {"key": "lang"})


def test_goal_tools(registry):
    r = registry.call("set_goal", {"text": "test goal"})
    gid = r.split("[")[1].split("]")[0]
    assert "set goal" in r
    assert "added subgoal" in registry.call("add_subgoal", {"goal_id": gid, "subgoal": "s1"})
    assert gid in registry.call("list_goals", {})
    assert "completed" in registry.call("complete_goal", {"goal_id": gid})


def test_graph_tools(registry):
    assert "added entity" in registry.call("add_entity", {"name": "ada", "type": "person"})
    assert "added relation" in registry.call(
        "add_relation", {"from": "ada", "to": "py", "rel": "knows"})
    assert "ada" in registry.call("query_graph", {"entity": "ada"})
    assert "missing" in registry.call("add_relation", {"to": "x"})


def test_web_search_input_validation(registry):
    assert registry.call("web_search", {"query": "   "}) == "error: empty query"


def test_shell_refuses_dangerous_commands(registry):
    assert "refused" in registry.call("shell", {"cmd": "rm -rf /"})
    assert "refused" in registry.call("shell", {"cmd": "mkfs something"})
    assert "error" in registry.call("shell", {"cmd": "   "})


def test_shell_runs_simple_command(registry):
    out = registry.call("shell", {"cmd": "echo hello-ci-test"})
    assert "hello-ci-test" in out


def test_forged_tool_callable_via_registry(registry, tmp_path):
    registry.call("forge_tool", {"name": "greet",
                                 "source": "def tool_impl():\n    return 'hi from forge'"})
    assert registry.call("greet", {}) == "hi from forge"
    assert "greet" in registry.call("list_forged_tools", {})


def test_unknown_tool_errors(registry):
    assert "unknown tool" in registry.call("nope", {})


# ───────────────────────────────────────────────  v4.2 system tools  ───────
def test_sys_info_tool(registry):
    out = registry.call("sys_info", {})
    assert "python" in out.lower()
    assert "platform" in out.lower()
    assert "cwd" in out


def test_now_tool(registry):
    import re as _re
    out = registry.call("now", {})
    assert _re.match(r"\d{4}-\d{2}-\d{2} ", out)
    custom = registry.call("now", {"format": "%Y"})
    assert len(custom) == 4 and custom.isdigit()


def test_find_files_tool(registry):
    registry.call("write_file", {"path": "d/sub/a.txt", "content": "x"})
    registry.call("write_file", {"path": "d/b.py", "content": "y"})
    out = registry.call("find_files", {"pattern": "*.txt", "path": "d"})
    assert "a.txt" in out and "b.py" not in out
    assert "(no files matching" in registry.call(
        "find_files", {"pattern": "*.zzz", "path": "d"})
    assert "error" in registry.call("find_files", {"pattern": "*", "path": "missing"})


def test_read_lines_tool(registry):
    registry.call("write_file", {"path": "lines.txt",
                                 "content": "one\ntwo\nthree\nfour"})
    out = registry.call("read_lines", {"path": "lines.txt", "start": 2, "end": 3})
    assert "2: two" in out and "3: three" in out
    assert "one" not in out
    tail = registry.call("read_lines", {"path": "lines.txt", "start": 3})
    assert "3: three" in tail and "4: four" in tail and "two" not in tail
    assert "error" in registry.call("read_lines", {"path": "lines.txt", "start": 99})
    assert "error" in registry.call("read_lines", {"path": "missing.txt", "start": 1})


def test_env_tool_actions(env_registry, tmp_path):
    r = env_registry
    assert r.call("env", {"action": "set", "key": "TAI_TOOL_TOKEN",
                          "value": "abc123key"}) == "set TAI_TOOL_TOKEN=ab***ey"
    assert "TAI_TOOL_TOKEN" in r.call("env", {"action": "list"})
    assert r.call("env", {"action": "get", "key": "TAI_TOOL_TOKEN"}) == \
        "TAI_TOOL_TOKEN=ab***ey"
    assert "unset TAI_TOOL_TOKEN" in r.call("env", {"action": "unset",
                                                    "key": "TAI_TOOL_TOKEN"})
    assert "saved" in r.call("env", {"action": "save"})
    assert "error" in r.call("env", {"action": "banana"})
    assert "error" in r.call("env", {"action": "set", "key": "1bad", "value": "x"})


def test_env_tool_requires_manager(registry):
    assert registry.env is None
    assert registry.call("env", {"action": "list"}) == \
        "error: env manager not available"


def test_delete_file_ask_delete_flag(tmp_path):
    r = ToolRegistry(
        memory=Memory(), graph=KnowledgeGraph(), goals=GoalPlanner(),
        journal=Journal(path=tmp_path / "j.md"),
        forge=ToolForge(path=tmp_path / "tools.json"), workspace=tmp_path,
        confirm_shell=False, ask_delete=False)
    r.call("write_file", {"path": "x.txt", "content": "data"})
    assert "deleted" in r.call("delete_file", {"path": "x.txt"})   # no input() prompt


def test_tool_schema_unique_names():
    names = [t["name"] for t in TOOL_SCHEMA]
    assert len(names) == len(set(names))
    for required in ("list_dir", "edit_file", "append_file", "delete_file",
                     "copy_file", "grep_files", "web_search", "done", "shell",
                     "read_file", "write_file", "remember", "forge_tool",
                     "dream", "sys_info", "now", "find_files", "read_lines",
                     "env"):
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
    # cloud fails AFTER yielding "one" -> error must propagate, no local fallback
    hb = _hybrid(FakeBackend(["one", "two"], fail_after=1), FakeBackend(["local"]))
    got = []
    with pytest.raises(BackendError):
        for chunk in hb.stream("sys", [Msg("user", "write a python function")]):
            got.append(chunk)
    assert got == ["one"]


def test_hybrid_uses_cloud_when_healthy():
    hb = _hybrid(FakeBackend(["cloud", "fine"]), FakeBackend(["local"]))
    out = list(hb.stream("sys", [Msg("user", "write a python function")]))
    assert out == ["cloud", "fine"]


def test_hybrid_no_backend_raises():
    hb = _hybrid(None, None)
    with pytest.raises(BackendError):
        list(hb.stream("sys", [Msg("user", "write a python function")]))


# ───────────────────────────────────────────────  gemini retry logic  ───────
def test_gemini_stream_retries_with_backoff(monkeypatch):
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


# ───────────────────────────────────────────────  agent turn (offline)  ────
def _make_agent(tmp_path, backend, autonomy=0, stats=None, settings=None):
    memory = Memory()
    journal = Journal(path=tmp_path / "j.md")
    tools = ToolRegistry(memory, KnowledgeGraph(), GoalPlanner(), journal,
                         tai.SkillLibrary(), ToolForge(path=tmp_path / "tools.json"),
                         workspace=tmp_path, confirm_shell=False)
    return tai.Agent(backend, memory, KnowledgeGraph(), GoalPlanner(), journal,
                     tai.SkillLibrary(), tai.MetaLearner(), tools,
                     ToolForge(path=tmp_path / "tools.json"),
                     TaskRouter(ModelRegistry()), PatternLearner(),
                     "system prompt", autonomy=autonomy, stats=stats,
                     settings=settings)


def test_agent_turn_direct_answer(tmp_path):
    agent = _make_agent(tmp_path, FakeBackend(["direct answer"]), autonomy=0,
                        stats=StatsTracker(path=tmp_path / "stats.json"))
    answer = agent.turn("hello")
    assert answer == "direct answer"
    assert agent.stats.data["turns"] == 1
    assert agent.stats.data["chars_out"] == len("direct answer")
    assert agent.memory.episodes                # episode recorded


def test_agent_turn_records_tool_calls(tmp_path):
    chunk1 = OPEN + '{"name": "shell", "args": {"cmd": "echo agent-tool-test"}}' + CLOSE
    chunk2 = OPEN + '{"name": "done", "args": {"answer": "finished"}}' + CLOSE
    stats = StatsTracker(path=tmp_path / "stats.json")
    agent = _make_agent(tmp_path, FakeBackend([chunk1, chunk2]), autonomy=1,
                        stats=stats)
    seq = iter([(chunk1, parse_tool_calls(chunk1)),
                (chunk2, parse_tool_calls(chunk2))])
    agent._stream_collect = lambda system, history: next(seq)
    answer = agent.turn("run a tool")
    assert answer == "finished"
    assert stats.data["tool_calls"] == 1


def test_agent_max_tool_rounds_from_settings(tmp_path):
    s = SettingsManager.blank()
    s.data["tool_rounds"] = 2
    agent = _make_agent(tmp_path, FakeBackend(["x"]), autonomy=1, settings=s)
    assert agent.max_tool_rounds == 2


def test_agent_max_rounds_enforced(tmp_path):
    # every round returns a non-done tool call -> must stop at max_tool_rounds
    chunk = _call("list_goals")
    agent = _make_agent(tmp_path, FakeBackend([chunk]), autonomy=1)
    agent.max_tool_rounds = 2
    agent._stream_collect = lambda system, history: (chunk, parse_tool_calls(chunk))
    assert agent.turn("loop forever") == "(reached max tool rounds)"
    assert agent.meta.strategies                # failure recorded in meta


def test_agent_history_limit_trim(tmp_path):
    agent = _make_agent(tmp_path, FakeBackend(["x"]), autonomy=0)
    agent.history_limit = 3
    agent.history = [Msg("user", f"m{i}") for i in range(5)]
    agent._trim()
    assert len(agent.history) == 3
    assert agent.history[-1].text == "m4"
