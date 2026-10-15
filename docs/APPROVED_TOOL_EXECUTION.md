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

Use `agent/playwright_browser.py` with an explicit `allowed_domains` list, then pass its `handlers()` mapping to `register_browser_tools` in `agent/browser_tools.py`. The adapter rejects non-HTTP(S) schemes, embedded URL credentials, unlisted hosts, private/loopback/reserved IPs and hostnames resolving to non-public addresses. Browser contexts block service workers, disallow downloads, restrict page count, and apply the same allowlist to subresources and redirects.

Read-only page reading is registered without tool-level approval; clicks, screenshots, form fills and submissions require approval through `ToolRegistry`. Use the approval dispatcher for state-changing actions. The allowlist accepts DNS names only (including IDNs normalized to IDNA), not wildcards, URL-shaped entries, ports, or IP literals. Malformed URL authorities and ports are rejected before DNS resolution. Browser output is untrusted page content. Do not place passwords, session cookies, API keys or private tokens into browser pages or tool results.

The browser adapter is optional and is not automatically launched by the web server. The application must configure its domain allowlist and wire the handler registry and approval UI deliberately. Domain allowlisting plus DNS checks is defense-in-depth, not a substitute for operating-system/network egress controls against DNS rebinding or compromised public hosts. Keep the service bound to localhost unless authentication, TLS, CSRF protection and network controls are enabled.
