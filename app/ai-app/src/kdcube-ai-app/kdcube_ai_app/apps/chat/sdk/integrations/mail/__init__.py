# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

"""Mail named-service integration.

The ``mail`` namespace is the provider-neutral realm for user-connected mail
accounts. Concrete transports such as Gmail live under their provider modules;
this package maps the common named-service contract onto those transports.
"""

from kdcube_ai_app.apps.chat.sdk.integrations.mail.named_service import (
    MAIL_NAMESPACE,
    MailNamedServiceProvider,
    mail_named_service_spec,
    make_mail_named_service_provider,
)

__all__ = [
    "MAIL_NAMESPACE",
    "MailNamedServiceProvider",
    "mail_named_service_spec",
    "make_mail_named_service_provider",
]
