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


## Tracked task lifecycle

The task lifecycle API records the path from a planned goal to an existing Command Control operation, operator verification, and reviewed learning. It does not add a tool dispatcher.

### Create a tracked plan

`POST /api/agentic/tasks`

```json
{
  "goal": "Inspect application health and verify the result",
  "risk": "read",
  "complexity": 2,
  "has_external_side_effects": false,
  "evidence_available": false
}
```

- `goal`: required non-empty string, at most 4,000 characters.
- `risk`: `read`, `low`, `medium`, `high`, or `critical`.
- `complexity`: integer from 1 through 10.
- `has_external_side_effects` and `evidence_available`: booleans when supplied.
- The response includes a persisted task, plan strategy/signals, and `execution_started: false`.

### List and inspect

- `GET /api/agentic/tasks?limit=50` — list recent records; `limit` is bounded to 1–200.
- `GET /api/agentic/tasks?status=planned` — filter by lifecycle status.
- `GET /api/agentic/tasks/{task_id}` — inspect a task and synchronize its linked operation status from Command Control.

Lifecycle statuses include `planned`, `awaiting_approval`, `approved`, `executing`, `executed`, `verified`, `reviewed`, `failed`, `rejected`, and `expired`.

### Link an existing operation

`POST /api/agentic/tasks/{task_id}/operation`

```json
{"operation_id": "existing-command-control-operation-id"}
```

The operation must already exist in Command Control. A task can be linked once. Linking records the relationship; it does not approve, authorize, or execute the operation.

### Record verification

`POST /api/agentic/tasks/{task_id}/verify`

```json
{
  "passed": true,
  "evidence": "A separate health check returned HTTP 200",
  "verifier": "operator"
}
```

Verification is rejected until the linked operation is recorded as `executed`. Evidence must be non-empty and at most 4,000 characters; verifier labels are bounded. If verification fails, the task enters `failed` and cannot be reviewed for learning. Operator-entered evidence is an attestation, not cryptographic proof.

### Submit a reviewed outcome

`POST /api/agentic/tasks/{task_id}/review`

```json
{
  "outcome": "success",
  "rating": 5,
  "reviewer": "operator"
}
```

Allowed outcomes are `success`, `partial`, and `failure`; rating is an integer from 1 to 5. Only a passing verified task can be reviewed. A successful review writes a verified outcome to the learning store and adds an audit event. Learning influences recommendations only; it does not change tool permissions or safety policy.

### Operational and security boundaries

- The lifecycle database is bounded to 2,000 recent tasks.
- Task goals and evidence can contain user data; secure the state directory and backups accordingly.
- Lifecycle routes do not run shell commands, browser actions, or planned steps.
- Protect these APIs with authentication and authorization before exposing the application to an untrusted network. Loopback binding is the safe default.


## Bounded failure recovery proposals

- `GET /api/agentic/tasks/{task_id}/recovery-proposals` — list a task's bounded proposal history.
- `POST /api/agentic/tasks/{task_id}/recovery-proposals` — draft guidance for a task whose linked operation is recorded as `failed` or `expired`.
- `POST /api/agentic/tasks/{task_id}/recovery-proposals/{proposal_id}/review` — explicitly approve replanning or reject a proposal.
- `POST /api/agentic/tasks/{task_id}/recovery-proposals/{proposal_id}/operation` — create a fresh pending Command Control operation from an approved proposal.
- `POST /api/agentic/tasks/{task_id}/recovery-proposals/{proposal_id}/verify` — record verification after the new operation is recorded as executed.

Create request:

```json
{"failure_category":"timeout","error_summary":"Connection timed out"}
```

Allowed categories: `timeout`, `transient_network`, `rate_limit`, `missing_dependency`, `validation`, `permission`, `destructive`, and `unknown`. The error summary is limited to 500 characters; do not include credentials, tokens, or other secrets. There are at most three proposals per task and 5,000 retained proposals globally.

Transient categories can be marked eligible for a retry only after human review; missing dependency and validation categories require a correction and fresh approval. Permission, destructive-risk, and unknown failures are marked no-retry and cannot be approved as retries. Categories are operator-supplied labels, not an automatic diagnosis or calibrated classifier.

Review request:

```json
{"decision":"approve","reviewer":"operator","note":"Confirmed idempotency and checked side effects"}
```

Approval changes the proposal to `approved_for_replanning` only. It does not execute, enqueue, or authorize the previous operation again. A changed or repeated action must be represented by a new Command Control operation with exact arguments and fresh human approval. Non-idempotent side effects must be checked before considering a retry. Every proposal and review writes a metadata-only audit event; never put secrets in error summaries or notes.


### Queue a fresh operation after review

Only an `approved_for_replanning` proposal can create one new operation. The operation is queued in Command Control and must receive its own human review:

```json
{"tool":"workspace","operation":"workspace","arguments":{"path":"README.md"}}
```

The `tool` and `operation` names must match a dispatchable registered tool. The response includes the new pending operation ID and `approval_required: true`. Each proposal can create at most one new operation. Queueing is not execution; the original failed operation and its approval remain unchanged. Review and approve the new operation through `/api/control/pending/{operation_id}/review`; execute it only through the existing approved dispatcher in an authenticated, CSRF-protected workflow. The UI prompts for exact arguments and displays the new operation ID.


### Verify the recovery result

`GET /api/agentic/tasks/{task_id}/recovery-proposals` includes the new operation's current Command Control status. Verification is accepted only when that operation is recorded as `executed`:

```json
{"passed":true,"evidence":"Independent service health check passed","verifier":"operator"}
```

Evidence must be non-empty and at most 4,000 characters. Verification can be recorded once and is stored on the recovery proposal as `verified` or `verification_failed`. The operator-supplied evidence is an attestation, not cryptographic proof. A failed verification does not trigger another retry; create and review a separate recovery proposal within the existing attempt limit.
