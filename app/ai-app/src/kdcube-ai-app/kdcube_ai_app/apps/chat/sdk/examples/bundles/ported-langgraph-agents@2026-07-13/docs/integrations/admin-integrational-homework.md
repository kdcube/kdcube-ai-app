---
id: ported-langgraph-agents@2026-07-13/docs/integrations/admin-integrational-homework
title: "Ported LangGraph Agents — Telegram Operator Homework"
summary: "The external, outside-the-code steps an operator does to turn on the Telegram webhook surface for ported-langgraph-agents@2026-07-13: create the bot, get the token, generate the webhook secret, fill config + secrets, and register the webhook with Telegram."
status: active
tags: [integrations, telegram, operator, webhook, ported-langgraph-agents]
see_also:
  - "ks:docs/sdk/integrations/telegram/telegram-external-prereq-README.md"
  - "ks:docs/sdk/integrations/telegram/telegram-README.md"
  - "ks:docs/service/cicd/ngrok-README.md"
---

# Ported LangGraph Agents — Telegram Operator Homework

The Telegram webhook is a shared ingress: a Telegram message drives the same
`execute_core` (the DEFAULT agent) as the browser chat surface. The code side is already
wired (the entrypoint's `telegram_webhook` `@api` + the reusable Telegram SDK).
What remains is the work that **cannot** live in the code — creating the bot,
holding its token, generating the webhook secret, and telling Telegram where to
call. This page is the app-specific checklist; the canonical, app-agnostic
version is the SDK's
[Telegram External Prerequisites](../../../../../../../../docs/sdk/integrations/telegram/telegram-external-prereq-README.md).

## What is external (and why)

The SDK owns Bot API mechanics, but it cannot create your Telegram bot, choose a
public HTTPS host, generate your secret, or call `setWebhook` for you. Those are
operator actions with real-world side effects and real secrets.

## Steps

| # | Where | Action | Output |
| - | ----- | ------ | ------ |
| 1 | Telegram `@BotFather` | Create or choose a bot for this app. | Bot username + display name. |
| 2 | Telegram `@BotFather` | Copy the bot token. | `TELEGRAM_BOT_TOKEN`. |
| 3 | Deployment | Decide the public HTTPS base URL Telegram can reach (for local dev, a tunnel — see the ngrok guide). | Public host. |
| 4 | Your workstation | Generate a random webhook secret. | `TELEGRAM_WEBHOOK_SECRET`. |
| 5 | KDCube config + secrets | Fill the descriptor values below, then reload/restart. | Live webhook route. |
| 6 | Telegram Bot API | Register the webhook (after the route exists). | Successful `setWebhook`. |
| 7 | Telegram `@BotFather` | (Optional) Set the command list. | User-visible `/start`, `/help`. |

### 4 — generate the webhook secret

Allowed characters are `A-Z a-z 0-9 _ -`:

```bash
printf '%s\n' "$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '=')"
```

Store it only in the deployment secrets provider — never in source control.

### 5 — fill the descriptor

Non-secret config (`bundles.yaml`, mirroring
[../../config/bundles.template.yaml](../../config/bundles.template.yaml)) — flip
the integration on and enable the public route:

```yaml
config:
  enabled:
    api:
      public.telegram_webhook.POST: true
  integrations:
    telegram.default:
      provider: telegram
      enabled: true
      definition:
        bot_name: "<TELEGRAM_BOT_NAME>"
        bot_username: "<TELEGRAM_BOT_USERNAME>"
        webhook:
          url: "https://<PUBLIC_HOST>/api/integrations/bundles/<TENANT>/<PROJECT>/ported-langgraph-agents@2026-07-13/public/telegram_webhook?integration_id=telegram.default"
          send_responses: true
          stream_activity: true
          stream_activity_display: true
        web_app_auth_max_age_seconds: 86400
```

Secrets (`bundles.secrets.yaml`, mirroring
[../../config/bundles.secrets.template.yaml](../../config/bundles.secrets.template.yaml)):

```yaml
secrets:
  integrations:
    telegram.default:
      definition:
        bot_token: "<TELEGRAM_BOT_TOKEN>"
        webhook_secret: "<TELEGRAM_WEBHOOK_SECRET>"
```

Keep the config and secret rows under the **same** integration id
(`telegram.default`) — that id is the non-secret selector in the webhook URL.

### 6 — register the webhook with Telegram

After the public route exists (the app is deployed and enabled):

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
  -d "url=https://<PUBLIC_HOST>/api/integrations/bundles/<TENANT>/<PROJECT>/ported-langgraph-agents@2026-07-13/public/telegram_webhook?integration_id=telegram.default" \
  -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
```

Re-run `setWebhook` whenever the public host changes (for example, a new local
tunnel URL).

## Verify

- The webhook rejects a request with a missing or wrong
  `X-Telegram-Bot-Api-Secret-Token` (401).
- `setWebhook` points at the currently active public URL.
- A message to the bot produces an answer back in the Telegram chat (from the default agent).
- Each Telegram sender gets their own isolated memory (a Telegram user maps to the
  platform identity `telegram_<telegram_user_id>`, which the app's identity gate
  folds into a distinct per-user memory key).

## Boundary note

The app keeps a small bundle-owned Telegram user registry (chat/user metadata,
conversation binding, and webhook update-id dedupe claims) under the bundle
storage root — this is the SDK-shaped store the Telegram ingress needs. The
agents' turns themselves own no other bundle-local durable state.
