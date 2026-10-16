# Credential management controls

Terminal AI's Settings page provides explicit removal actions for saved provider API keys and the Hugging Face token.

## Provider API key

1. Select the provider in Settings.
2. Choose **Remove saved key for selected provider** and confirm.
3. The API removes that provider's key from the local `.env` file and current process environment, then refreshes provider status.
4. If the key is supplied by a shell profile, systemd unit, container orchestrator, or other external environment source, remove it there too; Terminal AI cannot rewrite external service configuration and that source can reintroduce the key after restart.

The remove action accepts only registered provider IDs and never returns key values. Blank input in the ordinary settings form still means “keep the existing key”; removal is a separate, explicit operation.

## Hugging Face token

Choose **Remove saved Hugging Face token** and confirm. Terminal AI removes the local token file and clears `HF_TOKEN` from the running process. As with provider keys, also remove externally injected values from the service manager or shell configuration if present.

Credential removal is intentionally separate from portable settings backups. The settings backup/export allowlist must never contain `api_key` or `hf_token`.

## Safety and limitations

- Credential removal does not revoke a token at its provider. Use the provider's account/security page to revoke or rotate a compromised credential.
- Existing in-flight requests may have already authenticated before the removal.
- A restart can reload credentials from external environment configuration.
- Human approval requirements and tool permissions are unaffected by credential changes.
