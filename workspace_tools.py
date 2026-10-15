"""Workspace-confined filesystem tools and approval-gated command execution."""
from __future__ import annotations
import os, subprocess
from pathlib import Path
class WorkspaceTools:
    SAFE_COMMANDS={"pwd","ls","cat","head","tail","grep","find","git","python","python3","pytest","ruff"}
    def __init__(self,workspace):
        self.workspace=Path(workspace).expanduser().resolve(); self.workspace.mkdir(parents=True,exist_ok=True)
    def resolve(self,relative):
        raw=Path(relative)
        if raw.is_absolute(): raise ValueError("Absolute paths are not allowed.")
        target=(self.workspace/raw).resolve()
        if target!=self.workspace and self.workspace not in target.parents: raise ValueError("Path escapes the configured workspace.")
        return target
    def list_files(self,relative="."):
        target=self.resolve(relative)
        if not target.exists(): raise FileNotFoundError(relative)
        if not target.is_dir(): raise ValueError("Path is not a directory.")
        return [{"name":p.name,"directory":p.is_dir(),"size":p.stat().st_size if p.is_file() else None} for p in sorted(target.iterdir(),key=lambda p:p.name.casefold())[:500]]
    def read_file(self,relative,max_bytes=200000):
        target=self.resolve(relative)
        if not target.is_file(): raise FileNotFoundError(relative)
        if target.stat().st_size>max_bytes: raise ValueError("File exceeds read limit.")
        return target.read_text(encoding="utf-8",errors="replace")
    def write_file(self,relative,content,*,approved=False):
        if not approved: raise PermissionError("Writing files requires explicit approval.")
        if len(content)>500000: raise ValueError("Content exceeds write limit.")
        target=self.resolve(relative); target.parent.mkdir(parents=True,exist_ok=True); tmp=target.with_name(target.name+".terminal-ai.tmp")
        tmp.write_text(content,encoding="utf-8"); os.replace(tmp,target)
        return {"path":str(target.relative_to(self.workspace)),"bytes":target.stat().st_size}
    def run_command(self,argv,*,approved=False,timeout=30):
        if not approved: raise PermissionError("Command execution requires explicit approval.")
        if not isinstance(argv,list) or not argv or len(argv)>32 or any(not isinstance(a,str) or len(a)>2000 for a in argv): raise ValueError("Provide a bounded argv list; shell syntax is not accepted.")
        if Path(argv[0]).name not in self.SAFE_COMMANDS: raise PermissionError("Command is not allowlisted.")
        if any(x in {"-c","--command","&&","||",";","|",">","<"} for x in argv): raise PermissionError("Shell operators and command strings are not allowed.")
        result=subprocess.run(argv,cwd=self.workspace,text=True,capture_output=True,timeout=max(1,min(int(timeout),60)),shell=False)
        return {"returncode":result.returncode,"stdout":result.stdout[-20000:],"stderr":result.stderr[-10000:],"cwd":str(self.workspace)}
