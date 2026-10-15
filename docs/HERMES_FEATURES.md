# Hermes-style Agent Capabilities for Terminal AI

This implementation adds provider-neutral building blocks inspired by common agent
framework patterns. It does **not** claim to be the Hermes model, reproduce its
training, or expose hidden chain-of-thought.

## Included runtime primitives

- **Structured tool calls:** parse strict JSON tool envelopes and validate argument
  schemas (types, required fields, extra fields, enums, bounds, patterns, arrays).
- **Explicit tool allowlist:** tools must be registered by application code; model
  output is never evaluated as Python, shell, or arbitrary source.
- **Approval gates:** tools can require a caller-provided approval flag. An unapproved
  call is refused before its handler runs.
- **Bounded output and errors:** tool output is truncated, errors are bounded, and
  results include duration and call ID.
- **Self-correction/recovery:** a bounded retry/repair loop supports application-level
  validators and repair callbacks. Maximum attempts are capped at five.
- **Multi-turn context:** bounded message and character budgets; supported roles are
  system, user, assistant, and tool. Private chain-of-thought is deliberately not
  stored or emitted as a conversation role.
- **Test coverage:** unit tests exercise structured calls, schema rejection, approval,
  context limits, and bounded recovery.

## Minimal example

```python
from agentic_runtime import ToolRegistry, ToolSpec, parse_tool_call

tools = ToolRegistry()
tools.register(ToolSpec(
    name="add",
    description="Add two integers",
    handler=lambda a, b: a + b,
    parameters={
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
        "additionalProperties": False,
    },
))
name, arguments = parse_tool_call(
    '{"name":"add","arguments":{"a":2,"b":3}}'
)
result = tools.execute(name, arguments)
if result.ok:
    print(result.output)
else:
    print(result.error)
```

## Security and operational boundaries

- Register only narrowly scoped handlers and validate all inputs at the handler too.
- Treat web pages, tool outputs, and user files as untrusted data, not instructions.
- Mark file writes, command execution, network mutations, and other consequential
  actions as approval-required. Approval should be collected by the UI, not inferred
  from model output.
- The synchronous handler API cannot safely interrupt arbitrary Python functions;
  network/file handlers must implement their own timeouts. Do not register unbounded
  or blocking handlers in a web request path.
- Recovery is intentionally bounded. It does not silently rerun dangerous actions.
- Do not log credentials, full private prompts, or hidden reasoning traces.
- These primitives are an integration foundation. A provider adapter must still map
  its native tool-call response format into the normalized JSON envelope and feed
  conversation history into the selected model backend.

## Rollout notes

This module is intentionally decoupled from the current chat endpoint so it can be
reviewed and tested without changing established provider behavior. The next integration
step is to connect provider-native tool-call responses to this registry, add UI approval
prompts for risky tools, and expose per-feature settings after end-to-end tests.
