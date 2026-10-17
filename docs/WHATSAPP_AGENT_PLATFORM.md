# WhatsApp Agent Platform

Terminal AI can connect to an agent created inside WhatsApp's **Settings → Agents** experience. This integration uses Meta's Agent Platform API, not WhatsApp Web QR pairing and not the WhatsApp Business Cloud API.

## Setup

1. Confirm the **Agents** feature is available in your WhatsApp account. Meta is rolling it out gradually and Terminal AI cannot enable it for an account.
2. In WhatsApp, create or open your agent, open its chat, then go to **Chat info → API key** and copy the key.
3. Open Terminal AI's **WhatsApp Agent** dashboard page.
4. Paste the Agent API key, select **Enable WhatsApp polling**, and save.
5. Wait for the connection status to update, then send a text message in that agent's WhatsApp chat. The first valid creator message is verified using Meta's read-receipt endpoint before it is passed to the AI backend.

The agent API key is not a WhatsApp Linked Devices QR code, phone number, or Cloud API token. Only one active poller should use an agent API key at a time; multiple pollers can replace each other's long polls.

## Supported in v1

- Save and remove the API key through the dashboard.
- Enable or disable background polling.
- Test API connectivity and inspect local connection status without advancing the inbound update cursor; queued messages remain available to the poller.
- Receive text messages through Meta's long-poll `GET /updates` endpoint.
- Verify the creator using `POST /statuses`; do not forward unverified senders to the model.
- Generate replies through Terminal AI's existing serialized chat pipeline and send text replies through `POST /messages`.
- Manually send a text message to the creator after the creator ID is verified.
- Persist an update cursor, a bounded set of message IDs, timestamps, and counters locally.

## Not yet supported

Media, voice notes, image/document/video handling, reactions, rich interactive messages, proactive scheduled delivery, multi-agent profiles inside one Terminal AI instance, and agent-key rotation UX are not implemented in this v1. The UI explicitly labels the connector text-only.

## Privacy and security

- WhatsApp says conversations with third-party agents are **not end-to-end encrypted**. Treat this channel differently from personal WhatsApp chats.
- Messages received by the connector are sent to the configured Terminal AI model backend and may be archived according to the existing conversation archive setting.
- The API key is stored in `STATE_DIR/whatsapp_agent_platform.json` with mode `0600` where supported. It is never included in the status response or logged intentionally.
- The integration only responds after Meta accepts a read receipt for the sender. The first confirmed creator ID is pinned locally. Outbound manual sends are restricted to that creator ID.
- The connector does not subscribe to or read a user's other WhatsApp chats.
- Disable polling or remove the key from the dashboard at any time. Removing the key also stops polling and clears the stored creator ID and cursor.
- The HTTP client does not follow redirects, and logs avoid raw request bodies, API keys, and message content.

## API endpoints

- `GET /api/whatsapp-agent/status` — safe status snapshot; never returns the API key.
- `POST /api/whatsapp-agent/config` — save `api_key`, set `enabled`, or set `clear_key: true`. These fields are type-checked; key removal cannot be combined with a new key or an explicit `enabled: true`.
- `POST /api/whatsapp-agent/test` — test connectivity when no background poll is active, or report the active worker's state. The probe restores the prior cursor so it cannot consume an unread message.
- `POST /api/whatsapp-agent/send` — send `{"message":"..."}` to the verified creator only.

The API is mounted behind the same Litestar middleware as the rest of Terminal AI. Deploy it only behind the application's configured access control; do not expose the dashboard to the public internet without authentication and TLS.

## References

- [WhatsApp Agent Platform Developer Manual](https://www.whatsapp.com/developer/WhatsApp-Agent-Platform-Developer-Manual.pdf)
- [WhatsApp third-party agent terms](https://www.whatsapp.com/legal/third-party-agents-terms)
- [WhatsApp Help Center: third-party agents](https://faq.whatsapp.com/1050934623978152)
- [Community Agent Platform implementation reference](https://github.com/ahtishamdilawar/hermes-whatsapp-agent-platform) (used to cross-check endpoint shape; not affiliated with Meta or WhatsApp)
