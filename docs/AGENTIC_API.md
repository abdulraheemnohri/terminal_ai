# Adaptive Agent API

The Litestar application exposes the adaptive planning and evidence world model under `/api/agentic`.

## Endpoints

- `GET /api/agentic/status` — reports enabled foundations and their boundaries.
- `POST /api/agentic/plan` — creates a deterministic plan summary; does not execute the plan.
- `GET /api/agentic/world-model?subject=...` — reads currently active evidence facts.
- `POST /api/agentic/world-model/observe` — records a bounded observation with source, confidence, and optional TTL.
- `POST /api/agentic/skills/validate` — validates a declarative skill package without saving or executing it.

### Plan request

```json
{
  "goal": "Review the deployment configuration",
  "complexity": 5,
  "risk": "medium",
  "has_external_side_effects": false
}
```

Allowed risk values are `read`, `low`, `medium`, `high`, and `critical`. Complexity must be an integer from 1 to 10. High/critical risk or any declared external side effect results in a plan that requires human review.

### Evidence observation request

```json
{
  "subject": "deployment",
  "predicate": "health",
  "value": {"status": "healthy"},
  "source": "operator-check",
  "confidence": 0.9,
  "ttl_seconds": 3600
}
```

Confidence is clamped by the underlying model and validated to the range 0–1 at the API boundary. Values are limited to 20,000 serialized characters. TTL is optional and, when supplied, must be between one second and one year. Facts are stored in `world_model.json` under the configured application state directory. The model stores operational evidence; it is not a complete simulation of the world and is not evidence of sentience.

All routes are data/planning operations. They do not launch browser actions, execute shell commands, mutate system settings, or start a planned workflow. Actual side effects must continue through the existing Command Control Center review and execution boundaries. Keep the web server on loopback unless authentication, CSRF protections, and network controls are configured.
