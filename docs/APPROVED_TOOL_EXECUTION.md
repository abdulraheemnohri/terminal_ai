# Approved tool execution and browser adapter

## One-time tool approval

`agent/approved_dispatch.py` connects the existing `CommandControl` review queue to `ToolRegistry`. It requires a queued operation to be reviewed as approved, binds it to the exact registered tool name and canonical arguments, checks the approval age, atomically consumes the approval, and records the final outcome. Replaying the same approval is rejected.

Use this dispatcher only behind an authenticated, CSRF-protected endpoint or a trusted local operator action. Do not expose an unauthenticated public endpoint that accepts arbitrary operation IDs. Approval authorizes only the exact queued operation, never a different tool or modified arguments. Global auto-execution remains disabled.

## Optional Playwright browser

Install the optional dependency:

```bash
pip install playwright
playwright install chromium
```

Use `application/browser_runtime.py:create_browser_runtime()` with an explicit `allowed_domains` list to wire the Playwright adapter to `ToolRegistry`. It registers only implemented handlers and starts Chromium lazily on first use; call `BrowserRuntime.close()` during shutdown. The lower-level `handlers()` and `register_browser_tools()` APIs remain available for custom hosts. The adapter rejects non-HTTP(S) schemes, embedded URL credentials, unlisted hosts, private/loopback/reserved IPs and hostnames resolving to non-public addresses. Browser contexts block service workers, disallow downloads, restrict page count, and apply the same allowlist to subresources and redirects.

Read-only page reading is registered without tool-level approval; clicks, screenshots, form fills and submissions require approval through `ToolRegistry`. Use the approval dispatcher for state-changing actions. The allowlist accepts DNS names only (including IDNs normalized to IDNA), not wildcards, URL-shaped entries, ports, or IP literals. Malformed URL authorities and ports are rejected before DNS resolution. Browser output is untrusted page content. Do not place passwords, session cookies, API keys or private tokens into browser pages or tool results.

The browser adapter is optional and is not automatically launched by the web server. The application must configure its domain allowlist and wire the handler registry and approval UI deliberately. Domain allowlisting plus DNS checks is defense-in-depth, not a substitute for operating-system/network egress controls against DNS rebinding or compromised public hosts. Keep the service bound to localhost unless authentication, TLS, CSRF protection and network controls are enabled.


## Browser domain settings

Configure the optional allowlist in **Settings → Safety & change control**. Enter one DNS name per line (comma-separated entries are also accepted). Server-side validation normalizes case, trailing dots, and IDNs; wildcard entries, URLs, ports, malformed DNS names, and IP literals are rejected. An empty list disables browser access.

`GET /api/browser/status` reports only whether domains are configured and whether the optional Playwright package is installed. It never launches Chromium and always reports `execution_enabled: false`. The Settings allowlist is configuration groundwork, not a remote-action endpoint: do not enable browser actions until an authenticated, CSRF-safe dispatch path and operator approval workflow are available.
