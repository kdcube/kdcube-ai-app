---
id: connection-hub@1-0/integrations/icloud
title: "Connection Hub — iCloud setup"
summary: "iCloud mail uses an Apple app-specific password (not OAuth). What the user does and why no deployment secret is needed."
status: "active"
tags: ["integration", "connections", "icloud", "email", "app-password", "user-setup"]
keywords: ["icloud app-specific password", "apple two-factor", "email_connect_app_password", "imap smtp"]
see_also:
  - ./README.md
---

# Connection Hub — iCloud setup

iCloud mail does **not** use OAuth — it uses an Apple **app-specific password**.
There is no client app and no redirect URI to register; the hub's
`integrations.email` integration serves iCloud only (Gmail moved to the
connections framework — see [google.md](./google.md)).

This is a **per-user** action (no admin/operator setup):

| # | Where | Action |
| --- | --- | --- |
| 1 | Apple Account → Sign-In and Security | Ensure **two-factor authentication** is on. |
| 2 | Apple Account → App-Specific Passwords | Create one for "KDCube". |
| 3 | Connections widget → iCloud | Enter the iCloud email + the app-specific password. |

The password is submitted via the `email_connect_app_password` op and stored as a
**user-scoped secret** when the user connects. No deployment secret in
`bundles.secrets.yaml` is required for iCloud.

The SDK uses IMAP for reading and SMTP for sending; the app-specific password is
never placed in descriptor files or logs.
