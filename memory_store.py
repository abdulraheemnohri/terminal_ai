"""Persistent local knowledge store. SQLite and lexical search work fully offline."""
from __future__ import annotations
import json, sqlite3, time, uuid
from pathlib import Path
class MemoryStore:
    def __init__(self,path):
        self.path=Path(path).expanduser(); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=15); db.row_factory=sqlite3.Row; db.execute("PRAGMA busy_timeout=15000"); db.execute("PRAGMA journal_mode=WAL"); db.execute("PRAGMA synchronous=NORMAL"); return db
    def _init(self):
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS knowledge(id TEXT PRIMARY KEY,title TEXT NOT NULL,content TEXT NOT NULL,kind TEXT NOT NULL DEFAULT 'note',tags TEXT NOT NULL DEFAULT '[]',source TEXT NOT NULL DEFAULT 'user',created_at REAL NOT NULL,updated_at REAL NOT NULL,pinned INTEGER NOT NULL DEFAULT 0)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_updated ON knowledge(updated_at DESC)")
            db.execute("CREATE TABLE IF NOT EXISTS conversation_archive(id TEXT PRIMARY KEY,session_id TEXT NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created_at REAL NOT NULL,metadata TEXT NOT NULL DEFAULT '{}')")
            db.execute("CREATE INDEX IF NOT EXISTS idx_archive_session ON conversation_archive(session_id,created_at)")
    @staticmethod
    def _item(row):
        item=dict(row); item["tags"]=json.loads(item.get("tags") or "[]"); item["pinned"]=bool(item.get("pinned",0)); return item
    def add(self,title,content,*,kind="note",tags=None,source="user",pinned=False):
        title,content=title.strip(),content.strip()
        if not title or not content: raise ValueError("Title and content are required.")
        if len(title)>240 or len(content)>20000: raise ValueError("Title or content exceeds limits.")
        now=time.time(); ident=uuid.uuid4().hex
        with self._connect() as db: db.execute("INSERT INTO knowledge VALUES(?,?,?,?,?,?,?,?,?)",(ident,title,content,kind,json.dumps(list(tags or [])[:30]),source,now,now,int(pinned)))
        return self.get(ident)
    def get(self,ident):
        with self._connect() as db: row=db.execute("SELECT * FROM knowledge WHERE id=?",(ident,)).fetchone()
        return self._item(row) if row else None
    def list(self,limit=100,kind=None):
        with self._connect() as db:
            sql="SELECT * FROM knowledge"+(" WHERE kind=?" if kind else "")+" ORDER BY pinned DESC,updated_at DESC LIMIT ?"
            rows=db.execute(sql,((kind,max(1,min(limit,500))) if kind else (max(1,min(limit,500)),))).fetchall()
        return [self._item(r) for r in rows]
    def search(self,query,limit=10):
        terms=[t.casefold() for t in query.split() if len(t)>1]
        if not terms:return []
        scored=[]
        for item in self.list(500):
            title=item["title"].casefold(); body=item["content"].casefold(); tags=" ".join(item["tags"]).casefold()
            score=sum((4 if t in title else 0)+(3 if t in tags else 0)+(1 if t in body else 0) for t in terms)
            if score: scored.append((score,item))
        scored.sort(key=lambda x:(x[0],x[1]["pinned"],x[1]["updated_at"]),reverse=True)
        return [{"score":s,**i} for s,i in scored[:max(1,min(limit,50))]]
    def delete(self,ident):
        with self._connect() as db: cur=db.execute("DELETE FROM knowledge WHERE id=?",(ident,))
        return cur.rowcount>0
    def archive_message(self,session_id,role,content,metadata=None):
        content=str(content).strip()
        if content:
            with self._connect() as db: db.execute("INSERT INTO conversation_archive VALUES(?,?,?,?,?,?)",(uuid.uuid4().hex,session_id,role,content[:30000],time.time(),json.dumps(metadata or {})))
    def archive_search(self,query,limit=10):
        terms=[t.casefold() for t in query.split() if len(t)>1]
        if not terms:return []
        with self._connect() as db: rows=db.execute("SELECT * FROM conversation_archive ORDER BY created_at DESC LIMIT 2000").fetchall()
        out=[]
        for r in rows:
            score=sum(r["content"].casefold().count(t) for t in terms)
            if score: out.append({"score":score,"id":r["id"],"session_id":r["session_id"],"role":r["role"],"content":r["content"],"created_at":r["created_at"]})
        return sorted(out,key=lambda x:(x["score"],x["created_at"]),reverse=True)[:max(1,min(limit,50))]
