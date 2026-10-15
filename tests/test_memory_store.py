from memory_store import MemoryStore

def test_knowledge_persists_and_searches_offline(tmp_path):
    store=MemoryStore(tmp_path/"memory.sqlite3")
    saved=store.add("SolarPulse setup","Use SQLite and keep offline mode working",tags=["offline","solar"])
    assert store.get(saved["id"])["title"]=="SolarPulse setup"
    assert store.search("offline solar")[0]["id"]==saved["id"]
    assert MemoryStore(tmp_path/"memory.sqlite3").get(saved["id"]) is not None

def test_conversation_archive_search(tmp_path):
    store=MemoryStore(tmp_path/"memory.sqlite3")
    store.archive_message("session-a","user","How do I fix local inference?")
    results=store.archive_search("local inference")
    assert results and results[0]["session_id"]=="session-a"

def test_delete_knowledge(tmp_path):
    store=MemoryStore(tmp_path/"memory.sqlite3")
    item=store.add("A title","A body")
    assert store.delete(item["id"]) is True
    assert store.get(item["id"]) is None
