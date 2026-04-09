from types import SimpleNamespace

from kdcube_ai_app.apps.chat.ingress.economics import routines as economics_routines
from kdcube_ai_app.apps.chat.ingress.opex import routines as opex_routines
from kdcube_ai_app.infra.channel import email as email_channel


def test_email_smtp_settings_prefers_plain_descriptor(monkeypatch):
    values = {
        "notifications.email.host": "smtp.descriptor.local",
        "notifications.email.port": "2525",
        "notifications.email.user": "mailer",
        "notifications.email.from": "noreply@example.com",
        "notifications.email.to": "ops@example.com",
        "notifications.email.use_tls": False,
        "notifications.email.enabled": True,
    }

    monkeypatch.setattr(email_channel, "read_plain", lambda key, default=None: values.get(key, default))
    monkeypatch.setattr(
        email_channel,
        "get_settings",
        lambda: SimpleNamespace(
            EMAIL_HOST="smtp.env.local",
            EMAIL_PORT=587,
            EMAIL_USER="env-user",
            EMAIL_FROM="env-from@example.com",
            EMAIL_TO="env-ops@example.com",
            EMAIL_USE_TLS=True,
            EMAIL_ENABLED=False,
        ),
    )
    monkeypatch.setattr(email_channel, "get_secret", lambda *_args, **_kwargs: "pw")

    cfg = email_channel._smtp_settings()

    assert cfg["host"] == "smtp.descriptor.local"
    assert cfg["port"] == 2525
    assert cfg["user"] == "mailer"
    assert cfg["from_addr"] == "noreply@example.com"
    assert cfg["to_default"] == "ops@example.com"
    assert cfg["use_tls"] is False
    assert cfg["enabled"] is True
    assert cfg["password"] == "pw"


def test_economics_routines_prefer_plain_descriptor(monkeypatch):
    values = {
        "routines.stripe.reconcile_enabled": False,
        "routines.stripe.reconcile_cron": "5 * * * *",
        "routines.stripe.reconcile_lock_ttl_seconds": 321,
        "routines.economics.subscription_rollover_enabled": False,
        "routines.economics.subscription_rollover_cron": "7 * * * *",
        "routines.economics.subscription_rollover_lock_ttl_seconds": 654,
        "routines.economics.subscription_rollover_sweep_limit": 77,
    }

    monkeypatch.setattr(economics_routines, "read_plain", lambda key, default=None: values.get(key, default))
    monkeypatch.setattr(
        economics_routines,
        "get_settings",
        lambda: SimpleNamespace(
            STRIPE_RECONCILE_ENABLED=True,
            STRIPE_RECONCILE_CRON="45 * * * *",
            STRIPE_RECONCILE_LOCK_TTL_SECONDS=900,
            SUBSCRIPTION_ROLLOVER_ENABLED=True,
            SUBSCRIPTION_ROLLOVER_CRON="15 * * * *",
            SUBSCRIPTION_ROLLOVER_LOCK_TTL_SECONDS=900,
            SUBSCRIPTION_ROLLOVER_SWEEP_LIMIT=500,
        ),
    )

    assert economics_routines.stripe_reconcile_enabled() is False
    assert economics_routines._get_stripe_reconcile_cron_expression() == "5 * * * *"
    assert economics_routines._stripe_reconcile_lock_ttl_seconds() == 321
    assert economics_routines.subscription_rollover_enabled() is False
    assert economics_routines._get_subscription_rollover_cron_expression() == "7 * * * *"
    assert economics_routines._subscription_rollover_lock_ttl_seconds() == 654
    assert economics_routines._subscription_rollover_sweep_limit() == 77


def test_opex_cron_prefers_plain_descriptor(monkeypatch):
    monkeypatch.setattr(
        opex_routines,
        "read_plain",
        lambda key, default=None: "11 6 * * *" if key == "routines.opex.agg_cron" else default,
    )
    monkeypatch.setattr(
        opex_routines,
        "get_settings",
        lambda: SimpleNamespace(OPEX_AGG_CRON="0 3 * * *"),
    )

    assert opex_routines._get_cron_expression() == "11 6 * * *"
