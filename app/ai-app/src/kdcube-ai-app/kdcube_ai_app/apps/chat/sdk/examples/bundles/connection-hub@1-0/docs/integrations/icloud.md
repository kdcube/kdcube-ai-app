---
id: connection-hub@1-0/integrations/icloud
title: "Connection Hub — iCloud setup"
summary: "iCloud mail uses an Apple app-specific password (not OAuth). What the user does and why no deployment secret is needed."
status: "active"
tags: ["integration", "connections", "icloud", "email", "app-password", "user-setup"]
keywords: ["icloud app-specific password", "apple two-factor", "delegated_to_kdcube_connect_credential", "imap smtp"]
see_also:
  - ./README.md
---

# Connection Hub — iCloud setup

iCloud mail does **not** use OAuth — it uses an Apple **app-specific password**.
There is no OAuth client and no redirect URI to register. It is configured as a
delegated to KDCube provider, usually
`connections.delegated_to_kdcube.providers.icloud_mail.connector_apps.app_password`.

Admin/operator setup is only the provider registry row under
`connections.delegated_to_kdcube.providers.icloud_mail.connector_apps.app_password`.
There is no OAuth client secret to put in `bundles.secrets.yaml`.

After that, the actual connection is a **per-user** action:

| # | Where | Action |
| --- | --- | --- |
| 1 | Apple Account → Sign-In and Security | Ensure **two-factor authentication** is on. |
| 2 | Apple Account → App-Specific Passwords | Create one for "KDCube". |
| 3 | Connections widget → iCloud Mail | Enter the iCloud email + the app-specific password. |

The password is submitted via `delegated_to_kdcube_connect_credential` and
stored as a **user-scoped secret** when the user connects. No deployment secret
in `bundles.secrets.yaml` is required for iCloud.

The SDK uses IMAP for reading and SMTP for sending; the app-specific password is
never placed in descriptor files or logs.
