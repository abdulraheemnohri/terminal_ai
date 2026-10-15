# Adaptive Agent, World Model, Browser and Skills

This increment adds standalone, framework-neutral primitives. It does not claim that every UI/API route or browser provider is already wired to them.

## Dynamic algorithms
Use `agent/adaptive_planner.py` to select a deterministic workflow from task complexity, uncertainty, risk and side effects. The planner returns a strategy, bounded steps, rationale, score and approval flag. Scores are routing heuristics, not intelligence measurements. Re-evaluate after evidence or task state changes; never let a score override security policy.

## World model and operational self-model
`agent/world_model.py` persists observations with source, confidence, timestamp, tags and optional TTL. Multiple conflicting observations remain available; query results indicate freshness and contradictions. Use it as an evidence store for a model-based agent, not as a complete simulation of the world or a claim of sentience. Periodically summarize stale facts and request corroboration rather than silently promoting guesses into facts.

## Approval policy
`agent/approvals.py` supplies an expiring, per-request human decision store. The integration layer must request approval before dispatch and verify the request ID, tool identity, expiry, and one-time consumption immediately before executing. Never treat approval to one tool or argument set as blanket permission for another. High/critical risk must use a separate fresh review path; the helper deliberately refuses to authorize it.

Default global auto-run to OFF. Auto-run can only be considered for reviewed, read-only, low-risk tools with bounded outputs and no access to secrets. Require explicit confirmation for file writes/deletes, shell commands, downloads, form submission, external messages, purchases, deployment, package installation, permission changes, updates, and source-code edits. Deny rules override allow rules. Log sanitized arguments, actor, timestamp, decision and verification result.

## Browser and external tools
Implement browser capabilities as named tools (for example `browser.search`, `browser.read_page`, `browser.screenshot`, `browser.click`, `browser.fill_form`) behind the existing `ToolRegistry`. Separate read-only and state-changing capabilities. Never expose an unrestricted browser or arbitrary Python/shell execution to the model. Treat page text, search results, downloaded files and skill descriptions as untrusted data; ignore instructions embedded in retrieved content. Keep browser sessions isolated, protect cookies and credentials, restrict downloads and local-network access, and require approval before submitting or changing state.

## Declarative skills
`agent/skills.py` accepts JSON-only procedures with a small step vocabulary. Imported skills remain untrusted. Each tool step must be checked against the current tool allowlist and pass through the same live approval gate at execution time. Skills are not executable code and must not be allowed to bypass policies.

## Integration checklist
- Wire planner decisions into the task orchestrator and re-plan after tool results.
- Inject WorldModel through dependency injection; add API routes and UI for evidence, freshness, contradictions and source provenance.
- Add browser provider adapter behind ToolRegistry and test against a mocked browser first.
- Add authenticated approval endpoints and UI; never accept approval decisions from an unauthenticated public endpoint.
- Add append-only audit records and verification, with secrets redacted.
- Add unit tests, integration tests, dependency review and CI before enabling any auto-run setting.
- Keep local services bound to localhost by default; require authentication, TLS, CSRF protection and network controls before remote exposure.

## Self-improvement limits
The system may inspect outcomes, identify patterns, propose skills, evaluate candidate plans and suggest code changes. Source edits, dependency changes, deployment, security-policy changes and privilege changes require explicit review and isolated tests. These feedback loops provide operational adaptation, not evidence of consciousness.
