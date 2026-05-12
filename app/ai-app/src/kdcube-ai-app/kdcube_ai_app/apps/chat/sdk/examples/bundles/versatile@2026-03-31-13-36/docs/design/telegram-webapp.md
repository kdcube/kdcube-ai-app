---
title: Versatile Telegram WebApp Design
kind: design-note
bundle_id: versatile@2026-03-31-13-36
updated_at: 2026-05-12
---

# Versatile Telegram WebApp Design

The source-folder widget `widgets/versatile_webapp` is both a KDCube embedded
widget and a Telegram Mini App shell.

```text
KDCube control plane iframe
  -> operations/versatile_webapp_data
  -> operations/preferences_canvas_*
  -> operations/conversations_*
  -> operations/telegram_user_admin_* (admin role)

Telegram Mini App
  -> public/telegram_versatile_webapp_data
  -> public/telegram_memory_canvas_*
  -> public/telegram_conversations_*
  -> public/telegram_webapp_user_admin_* (Telegram admin role)
```

The frontend always sends platform tokens when embedded in KDCube and sends raw
Telegram `initData` as `X-Telegram-Init-Data` when running inside Telegram.
The public Telegram APIs verify that signed initData on every request before
reading or mutating data.

Tabs:

- Memory: current preferences canvas. This will be replaced by the new memory
  subsystem later, but the webapp route contract stays stable.
- Chats: Telegram-linked conversation/channel selection.
- Admin: Telegram user registry, visible to KDCube admins in the control plane
  and to Telegram users with role `admin` in the registry.
