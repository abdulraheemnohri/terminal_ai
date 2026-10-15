"""Persistent interval scheduler restricted to safe maintenance job types."""
from __future__ import annotations
import json, sqlite3, time, uuid
from pathlib import Path
ALLOWED={"diagnostics","backup_memory","cleanup_temp"}
class TaskScheduler:
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=15); db.row_factory=sqlite3.Row; db.execute("PRAGMA busy_timeout=15000"); db.execute("PRAGMA journal_mode=WAL"); db.execute("PRAGMA synchronous=NORMAL"); return db
    def _init(self):
        with self._connect() as db: db.execute("CREATE TABLE IF NOT EXISTS scheduled_tasks(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,interval_minutes INTEGER NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,next_run REAL NOT NULL,last_run REAL,last_status TEXT,payload TEXT NOT NULL DEFAULT '{}',created_at REAL NOT NULL)")
    def list(self):
        with self._connect() as db: rows=db.execute("SELECT * FROM scheduled_tasks ORDER BY enabled DESC,next_run").fetchall()
        return [dict(r,enabled=bool(r["enabled"]),payload=json.loads(r["payload"])) for r in rows]
    def create(self,name,kind,interval_minutes,payload=None):
        name=name.strip()
        if not name or len(name)>120: raise ValueError("Task name is required (max 120 characters).")
        if kind not in ALLOWED: raise ValueError("Unsupported scheduled task type.")
        if not isinstance(interval_minutes,int) or not 5<=interval_minutes<=10080: raise ValueError("Interval must be 5–10080 minutes.")
        now=time.time(); ident=uuid.uuid4().hex
        with self._connect() as db: db.execute("INSERT INTO scheduled_tasks VALUES(?,?,?,?,?,?,?,?,?,?)",(ident,name,kind,interval_minutes,1,now+interval_minutes*60,None,None,json.dumps(payload or {}),now))
        return next(x for x in self.list() if x["id"]==ident)
    def toggle(self,ident,enabled):
        with self._connect() as db: cur=db.execute("UPDATE scheduled_tasks SET enabled=?,next_run=? WHERE id=?",(int(bool(enabled)),time.time()+300,ident))
        return cur.rowcount>0
    def delete(self,ident):
        with self._connect() as db: cur=db.execute("DELETE FROM scheduled_tasks WHERE id=?",(ident,))
        return cur.rowcount>0
    def due(self):
        with self._connect() as db: rows=db.execute("SELECT * FROM scheduled_tasks WHERE enabled=1 AND next_run<=?",(time.time(),)).fetchall()
        return [dict(r,payload=json.loads(r["payload"])) for r in rows]
    def mark(self,ident,status):
        with self._connect() as db:
            row=db.execute("SELECT interval_minutes FROM scheduled_tasks WHERE id=?",(ident,)).fetchone()
            if row: db.execute("UPDATE scheduled_tasks SET last_run=?,last_status=?,next_run=? WHERE id=?",(time.time(),status[:500],time.time()+row["interval_minutes"]*60,ident))
