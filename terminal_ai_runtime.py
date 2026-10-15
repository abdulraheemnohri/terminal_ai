"""Guarded local-first agent runtime primitives for Terminal AI."""
from __future__ import annotations
import hashlib, json, os, re, sqlite3, threading, time, uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Callable

Risk = Literal["read", "low", "medium", "high", "critical"]
_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.:-]{1,100}$")

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

class PolicyDenied(PermissionError):
    pass

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk: Risk = "read"
    requires_approval: bool = True
    auto_allowed: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)

@dataclass
class ApprovalRequest:
    request_id: str
    tool_name: str
    arguments: dict[str, Any]
    reason: str
    risk: Risk
    created_at: float
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    decided_at: float | None = None
    decided_by: str | None = None

class ApprovalGate:
    """Fail-closed approval queue. Policy authorizes requests, never executes them."""
    def __init__(self, *, auto_execute: bool = False, allowlist: set[str] | None = None,
                 blocklist: set[str] | None = None, approval_ttl_seconds: int = 900) -> None:
        self.auto_execute = auto_execute
        self.allowlist, self.blocklist = set(allowlist or ()), set(blocklist or ())
        self.approval_ttl_seconds = max(30, int(approval_ttl_seconds))
        self._requests: dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()

    def request(self, spec: ToolSpec, arguments: dict[str, Any], reason: str) -> ApprovalRequest:
        if not _SAFE_NAME.fullmatch(spec.name):
            raise PolicyDenied("Invalid tool identifier")
        if spec.name in self.blocklist:
            raise PolicyDenied(f"Tool {spec.name!r} is blocked")
        if self.allowlist and spec.name not in self.allowlist:
            raise PolicyDenied(f"Tool {spec.name!r} is not allowlisted")
        # High/critical risk always requires a human decision.
        requires = spec.risk in ("high", "critical") or spec.requires_approval or not (
            self.auto_execute and spec.auto_allowed)
        req = ApprovalRequest(uuid.uuid4().hex, spec.name, dict(arguments), reason[:1000],
                              spec.risk, time.time())
        if not requires:
            req.status, req.decided_at, req.decided_by = "approved", time.time(), "policy:auto"
        with self._lock:
            self._requests[req.request_id] = req
        return req

    def decide(self, request_id: str, approve: bool, *, actor: str) -> ApprovalRequest:
        with self._lock:
            req = self._requests.get(request_id)
            if req is None:
                raise KeyError("Unknown approval request")
            if req.status != "pending":
                raise PolicyDenied("Request is no longer pending")
            if time.time() - req.created_at > self.approval_ttl_seconds:
                req.status, req.decided_at = "expired", time.time()
                raise PolicyDenied("Approval request expired")
            req.status = "approved" if approve else "rejected"
            req.decided_at, req.decided_by = time.time(), actor[:120]
            return req

    def get(self, request_id: str) -> ApprovalRequest | None:
        with self._lock:
            return self._requests.get(request_id)

    def pending(self) -> list[ApprovalRequest]:
        with self._lock:
            now = time.time()
            for req in self._requests.values():
                if req.status == "pending" and now - req.created_at > self.approval_ttl_seconds:
                    req.status, req.decided_at = "expired", now
            return [req for req in self._requests.values() if req.status == "pending"]

class AuditLedger:
    """Append-only JSONL hash chain. Tamper-evident, not a cryptographic signature."""
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event_type: str, actor: str, details: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            previous = "0" * 64
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as src:
                    for line in src:
                        if line.strip(): previous = json.loads(line)["hash"]
            entry = {"timestamp": time.time(), "event_id": uuid.uuid4().hex,
                     "event_type": event_type[:100], "actor": actor[:120],
                     "details": details, "previous_hash": previous}
            entry["hash"] = hashlib.sha256(canonical_json(entry).encode()).hexdigest()
            with self.path.open("a", encoding="utf-8") as dst:
                dst.write(canonical_json(entry) + "\n")
                dst.flush()
                os.fsync(dst.fileno())
            try: self.path.chmod(0o600)
            except OSError: pass
            return entry

    def verify(self) -> tuple[bool, int]:
        previous, count = "0" * 64, 0
        if not self.path.exists(): return True, 0
        with self.path.open("r", encoding="utf-8") as src:
            for line in src:
                if not line.strip(): continue
                entry = json.loads(line)
                supplied = entry.pop("hash", None)
                if entry.get("previous_hash") != previous: return False, count
                expected = hashlib.sha256(canonical_json(entry).encode()).hexdigest()
                if supplied != expected: return False, count
                previous, count = supplied, count + 1
        return True, count

@dataclass
class WorldFact:
    subject: str
    predicate: str
    value: Any
    source: str
    confidence: float
    observed_at: float = field(default_factory=time.time)
    expires_at: float | None = None

class WorldModel:
    """Explicit evidence/belief store with confidence and expiry; not consciousness."""
    def __init__(self) -> None:
        self._facts: dict[tuple[str, str], WorldFact] = {}
        self._lock = threading.RLock()

    def observe(self, subject: str, predicate: str, value: Any, *, source: str,
                confidence: float = 1.0, ttl_seconds: float | None = None) -> WorldFact:
        if not subject.strip() or not predicate.strip(): raise ValueError("subject and predicate required")
        now = time.time()
        fact = WorldFact(subject[:200], predicate[:200], value, source[:300],
                         min(1.0, max(0.0, float(confidence))), now,
                         now + ttl_seconds if ttl_seconds else None)
        with self._lock: self._facts[(fact.subject, fact.predicate)] = fact
        return fact

    def query(self, subject: str | None = None) -> list[WorldFact]:
        now = time.time()
        with self._lock:
            for key in [k for k, v in self._facts.items() if v.expires_at and v.expires_at <= now]:
                del self._facts[key]
            return [v for v in self._facts.values() if subject is None or v.subject == subject]

    def snapshot(self) -> dict[str, Any]:
        facts = self.query()
        return {"generated_at": time.time(), "fact_count": len(facts),
                "facts": [asdict(fact) for fact in facts]}

@dataclass(frozen=True)
class Plan:
    strategy: str
    steps: list[str]
    risk: Risk
    needs_approval: bool
    rationale: str

class AdaptivePlanner:
    """Deterministic dynamic strategy selection, with an explainable summary."""
    def plan(self, goal: str, *, complexity: int = 1, risk: Risk = "read",
             has_external_side_effects: bool = False) -> Plan:
        if not goal.strip(): raise ValueError("goal cannot be empty")
        complexity = max(1, min(10, int(complexity)))
        if risk in ("high", "critical") or has_external_side_effects:
            strategy = "plan-review-execute"
            steps = ["Clarify goal and constraints", "Inspect relevant state",
                     "Draft bounded plan", "Request approval before side effects",
                     "Execute approved steps", "Verify and record outcome"]
            approval = True
        elif complexity >= 7:
            strategy = "decompose-and-verify"
            steps = ["Decompose into testable tasks", "Gather evidence",
                     "Execute one bounded task at a time", "Validate each result",
                     "Summarize uncertainties and next steps"]
            approval = risk != "read"
        elif complexity >= 4:
            strategy = "research-then-act"
            steps = ["Gather context", "Compare options", "Perform bounded action",
                     "Check outcome"]
            approval = risk not in ("read", "low")
        else:
            strategy = "direct-verified"
            steps = ["Perform smallest safe action", "Verify result"]
            approval = risk in ("medium", "high", "critical")
        rationale = f"complexity={complexity}, risk={risk}, external_side_effects={has_external_side_effects}"
        return Plan(strategy, steps, risk, approval, rationale)

def init_sqlite(path: str | Path) -> sqlite3.Connection:
    """WAL mode, busy timeout and foreign keys for local SQLite storage."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=15, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def validate_skill_package(payload: Any) -> dict[str, Any]:
    """Validate declarative skills; imported skills never carry runnable source code."""
    if not isinstance(payload, dict): raise ValueError("Skill package must be an object")
    name, steps = payload.get("name"), payload.get("steps")
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValueError("Skill name must contain 1-120 characters")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        raise ValueError("Skill must contain 1-100 steps")
    allowed_keys = {"action", "description", "tool", "approval_required"}
    allowed_actions = {"ask", "observe", "search", "summarize", "propose", "verify", "tool_request"}
    clean = []
    for step in steps:
        if not isinstance(step, dict) or set(step) - allowed_keys:
            raise ValueError("Unsupported fields in skill step")
        if step.get("action") not in allowed_actions:
            raise ValueError("Unsupported declarative skill action")
        desc, tool = step.get("description", ""), step.get("tool", "")
        if not isinstance(desc, str) or len(desc) > 2000: raise ValueError("Invalid step description")
        if tool and (not isinstance(tool, str) or not _SAFE_NAME.fullmatch(tool)):
            raise ValueError("Invalid tool identifier")
        clean.append({"action": step["action"], "description": desc, "tool": tool,
                      "approval_required": True})
    return {"schema_version": 1, "name": name.strip(),
            "description": str(payload.get("description", ""))[:2000],
            "steps": clean, "trust": "untrusted-import-review-required"}

def export_skill(payload: dict[str, Any], path: str | Path) -> Path:
    skill, target = validate_skill_package(payload), Path(path).expanduser()
    if target.suffix.lower() not in {".json", ".yaml", ".yml"}:
        raise ValueError("Use .json, .yaml or .yml")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() in {".yaml", ".yml"}:
        try: import yaml
        except ImportError as exc: raise RuntimeError("Install PyYAML to use YAML") from exc
        content = yaml.safe_dump(skill, allow_unicode=True, sort_keys=False)
    else: content = json.dumps(skill, ensure_ascii=False, indent=2) + "\n"
    target.write_text(content, encoding="utf-8")
    try: target.chmod(0o600)
    except OSError: pass
    return target

def import_skill(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser()
    raw = target.read_text(encoding="utf-8")
    if len(raw) > 1_000_000: raise ValueError("Skill package exceeds 1 MB")
    if target.suffix.lower() == ".json": payload = json.loads(raw)
    elif target.suffix.lower() in {".yaml", ".yml"}:
        try: import yaml
        except ImportError as exc: raise RuntimeError("Install PyYAML to use YAML") from exc
        payload = yaml.safe_load(raw)
    else: raise ValueError("Use .json, .yaml or .yml")
    return validate_skill_package(payload)

class ActionEventBus:
    """Thread-safe event fan-out for WebSocket/SSE adapters; summaries only."""
    def __init__(self, history_limit: int = 500) -> None:
        from collections import deque
        self._history = deque(maxlen=max(10, history_limit))
        self._subscribers: set[Callable[[dict[str, Any]], None]] = set()
        self._lock = threading.RLock()

    def publish(self, event_type: str, summary: str, *, status: str = "info",
                tool_name: str | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {"event_id": uuid.uuid4().hex, "timestamp": time.time(),
                 "type": event_type[:80], "summary": summary[:1000], "status": status[:40],
                 "tool": tool_name, "details": details or {}}
        with self._lock:
            self._history.append(event)
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try: callback(event)
            except Exception: continue
        return event

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        with self._lock: self._subscribers.add(callback)
        def unsubscribe() -> None:
            with self._lock: self._subscribers.discard(callback)
        return unsubscribe

    def history(self) -> list[dict[str, Any]]:
        with self._lock: return list(self._history)


class ToolRegistry:
    """Allowlisted tool dispatcher. Handlers must be registered by trusted application code."""
    def __init__(self, gate: ApprovalGate, *, audit: AuditLedger | None = None,
                 events: ActionEventBus | None = None) -> None:
        self.gate, self.audit, self.events = gate, audit, events
        self._tools: dict[str, tuple[ToolSpec, Callable[[dict[str, Any]], Any]]] = {}
        self._lock = threading.RLock()

    def register(self, spec: ToolSpec, handler: Callable[[dict[str, Any]], Any]) -> None:
        if not _SAFE_NAME.fullmatch(spec.name):
            raise ValueError("Invalid tool name")
        with self._lock:
            if spec.name in self._tools:
                raise ValueError(f"Tool already registered: {spec.name}")
            self._tools[spec.name] = (spec, handler)

    def describe(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"name": spec.name, "description": spec.description, "risk": spec.risk,
                     "requires_approval": spec.requires_approval, "auto_allowed": spec.auto_allowed,
                     "input_schema": spec.input_schema}
                    for spec, _ in self._tools.values()]

    @staticmethod
    def _validate_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> None:
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object")
        schema = spec.input_schema or {}
        allowed = schema.get("properties", {})
        required = schema.get("required", [])
        if schema.get("additionalProperties") is False and set(arguments) - set(allowed):
            raise ValueError("Unexpected tool argument")
        missing = set(required) - set(arguments)
        if missing:
            raise ValueError("Missing required tool argument: " + ", ".join(sorted(missing)))
        type_map = {"string": str, "integer": int, "number": (int, float),
                    "boolean": bool, "object": dict, "array": list}
        for key, value in arguments.items():
            rule = allowed.get(key, {})
            expected = type_map.get(rule.get("type"))
            if expected and (not isinstance(value, expected) or
                             (rule.get("type") == "integer" and isinstance(value, bool)) or
                             (rule.get("type") == "number" and isinstance(value, bool))):
                raise ValueError(f"Invalid type for argument: {key}")
            if isinstance(value, str) and len(value) > int(rule.get("maxLength", 10000)):
                raise ValueError(f"Argument too long: {key}")

    def request(self, name: str, arguments: dict[str, Any], *, reason: str,
                actor: str = "agent") -> ApprovalRequest:
        with self._lock:
            entry = self._tools.get(name)
        if entry is None:
            raise PolicyDenied(f"Unknown tool: {name}")
        spec, _ = entry
        self._validate_arguments(spec, arguments)
        request = self.gate.request(spec, arguments, reason)
        if self.audit:
            self.audit.append("tool.approval_requested", actor, {
                "request_id": request.request_id, "tool": name, "risk": spec.risk,
                "status": request.status, "arguments": {"keys": sorted(arguments.keys())}})
        if self.events:
            self.events.publish("approval.requested" if request.status == "pending" else "tool.authorized",
                                f"{name}: " + ("waiting for approval" if request.status == "pending" else "authorized"),
                                status=request.status, tool_name=name,
                                details={"request_id": request.request_id, "risk": spec.risk})
        return request

    def decide(self, request_id: str, approve: bool, *, actor: str) -> ApprovalRequest:
        request = self.gate.decide(request_id, approve, actor=actor)
        if self.audit:
            self.audit.append("tool.approval_decided", actor, {
                "request_id": request_id, "tool": request.tool_name, "decision": request.status})
        if self.events:
            self.events.publish("approval.decided", f"{request.tool_name}: {request.status}",
                                status=request.status, tool_name=request.tool_name,
                                details={"request_id": request_id})
        return request

    def execute_approved(self, request_id: str, *, actor: str = "agent") -> Any:
        request = self.gate.get(request_id)
        if request is None:
            raise KeyError("Unknown approval request")
        if request.status != "approved":
            raise PolicyDenied("Tool execution requires an approved request")
        with self._lock:
            entry = self._tools.get(request.tool_name)
        if entry is None:
            raise PolicyDenied("Tool is no longer registered")
        spec, handler = entry
        self._validate_arguments(spec, request.arguments)
        if self.audit:
            self.audit.append("tool.execution_started", actor, {
                "request_id": request_id, "tool": spec.name, "argument_keys": sorted(request.arguments)})
        if self.events:
            self.events.publish("tool.started", f"Running {spec.name}", status="running",
                                tool_name=spec.name, details={"request_id": request_id})
        try:
            result = handler(dict(request.arguments))
        except Exception as exc:
            if self.audit:
                self.audit.append("tool.execution_failed", actor, {
                    "request_id": request_id, "tool": spec.name, "error_type": type(exc).__name__})
            if self.events:
                self.events.publish("tool.failed", f"{spec.name} failed: {type(exc).__name__}",
                                    status="error", tool_name=spec.name)
            raise
        if self.audit:
            self.audit.append("tool.execution_succeeded", actor, {
                "request_id": request_id, "tool": spec.name, "result_type": type(result).__name__})
        if self.events:
            self.events.publish("tool.completed", f"{spec.name} completed", status="success",
                                tool_name=spec.name,
                                details={"request_id": request_id, "result_type": type(result).__name__})
        return result
