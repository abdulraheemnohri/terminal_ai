"""Ordered cloud-provider fallback with local inference as the final backend."""
from __future__ import annotations

from collections.abc import Iterator, Sequence

import terminal_ai as core


class CloudFirstFallbackBackend(core.Backend):
    """Try each configured cloud backend in order, then local inference.

    Fallback is allowed only before any output has been emitted. Once a stream
    has produced text, an error is surfaced instead of duplicating partial output.
    """

    def __init__(self, clouds: Sequence[core.Backend], local: core.Backend | None):
        self.clouds = list(clouds)
        self.local = local
        self._active: core.Backend | None = None
        self.supports_tools = any(item.supports_tools for item in self.clouds)
        self.label = "cloud-first fallback"

    def stream(self, system: str, history: list[core.Msg],
               tools: list[dict] | None = None) -> Iterator[str]:
        candidates = [*self.clouds, *([self.local] if self.local is not None else [])]
        if not candidates:
            raise core.BackendError("No configured cloud provider or local model is available.")
        failures: list[str] = []
        for candidate in candidates:
            self._active = candidate
            emitted = False
            try:
                for chunk in candidate.stream(system, history, tools):
                    emitted = True
                    self.label = getattr(candidate, "label", type(candidate).__name__)
                    yield chunk
                if not emitted:
                    raise core.BackendError("provider returned an empty response")
                return
            except (KeyboardInterrupt, GeneratorExit):
                raise
            except Exception as exc:
                if emitted:
                    raise core.BackendError(
                        f"{getattr(candidate, \"label\", type(candidate).__name__)} failed after partial output; refusing duplicate fallback output."
                    ) from exc
                name = getattr(candidate, "label", type(candidate).__name__)
                failures.append(f"{name}: {type(exc).__name__}")
        raise core.BackendError("All cloud providers and local inference failed: " + "; ".join(failures))

    def cancel(self) -> None:
        if self._active is not None:
            self._active.cancel()

    def close(self) -> None:
        seen: set[int] = set()
        for backend in [*self.clouds, *([self.local] if self.local is not None else [])]:
            if id(backend) not in seen:
                seen.add(id(backend))
                backend.close()

    def describe(self) -> dict[str, object]:
        return {
            "strategy": "cloud-first-then-local",
            "cloud_candidates": [getattr(item, "label", type(item).__name__) for item in self.clouds],
            "local_available": self.local is not None,
            "execution_enabled": False,
        }
