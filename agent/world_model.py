"""Evidence-aware local world model; facts are observations, not ground truth."""
from __future__ import annotations
import json, math, time, uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

@dataclass
class WorldFact:
    key: str
    value: Any
    source: str
    confidence: float
    observed_at: float
    expires_at: float | None = None
    tags: tuple[str, ...] = ()
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id: self.id = uuid.uuid4().hex
        if not self.key.strip(): raise ValueError("Fact key cannot be empty.")
        if not 0 <= self.confidence <= 1 or not math.isfinite(self.confidence):
            raise ValueError("confidence must be finite and between 0 and 1.")
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("expires_at must be later than observed_at.")

    def fresh(self, now: float | None = None) -> bool:
        return self.expires_at is None or self.expires_at > (time.time() if now is None else now)

class WorldModel:
    """Stores sourced observations and preserves conflicting evidence."""
    VERSION = 1
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._facts: list[WorldFact] = []
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("version") != self.VERSION: return
            for item in raw.get("facts", []):
                item["tags"] = tuple(item.get("tags", []))
                self._facts.append(WorldFact(**item))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._facts = []

    def _save(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({"version": self.VERSION, "facts": [asdict(f) for f in self._facts]},
                                  ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def observe(self, key: str, value: Any, *, source: str, confidence: float = 0.5,
                ttl_seconds: float | None = None, tags: list[str] | None = None) -> WorldFact:
        if not source.strip(): raise ValueError("A source is required.")
        if ttl_seconds is not None and (not math.isfinite(ttl_seconds) or ttl_seconds <= 0):
            raise ValueError("ttl_seconds must be a positive finite number.")
        now = time.time()
        fact = WorldFact(key=key.strip(), value=value, source=source.strip()[:500],
                         confidence=confidence, observed_at=now,
                         expires_at=now + ttl_seconds if ttl_seconds else None,
                         tags=tuple((tags or [])[:30]))
        self._facts.append(fact)
        self._facts = self._facts[-5000:]
        self._save()
        return fact

    def query(self, key: str, *, include_expired: bool = False) -> list[dict[str, Any]]:
        now = time.time()
        matches = [f for f in self._facts if f.key.casefold() == key.casefold()
                   and (include_expired or f.fresh(now))]
        matches.sort(key=lambda f: (f.confidence, f.observed_at), reverse=True)
        return [{**asdict(f), "fresh": f.fresh(now)} for f in matches]

    def contradictions(self, key: str) -> bool:
        """True when fresh observations for a key disagree; never silently resolves them."""
        values = {json.dumps(f.value, sort_keys=True, default=str)
                  for f in self._facts if f.key.casefold() == key.casefold() and f.fresh()}
        return len(values) > 1

    def summary(self) -> dict[str, Any]:
        now = time.time()
        fresh = [f for f in self._facts if f.fresh(now)]
        return {"facts": len(self._facts), "fresh_facts": len(fresh),
                "expired_facts": len(self._facts)-len(fresh),
                "keys": sorted({f.key for f in fresh}),
                "contradictory_keys": sorted(k for k in {f.key for f in fresh} if self.contradictions(k))}
