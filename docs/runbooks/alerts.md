# Alerts: rules, evaluation and notification (A3.2)

Alerting turns the metrics of A3.1 and the inventory drift of A2.5 into a small set of
**Alert** records and, optionally, a Telegram message or email. The whole decision is pure
(`infra_control/monitoring/rules.py`); the engine (`alerts.py`) only gathers inputs, writes
the lifecycle, emits realtime, and notifies. Nothing here mutates infrastructure.

## The three rule kinds

An **Alert Rule** has a `kind`, a `severity` (info | warning | critical), a `target_doctype`,
a `for_minutes` window and a list of notification `channels`.

| Kind | Fires when | Clears when |
|---|---|---|
| `metric` | the metric breaches `operator`/`threshold` for **every** 1m reading across `for_minutes` (a lone spike does not fire) | the latest reading is back within threshold |
| `heartbeat` | `now - last_heartbeat ≥ for_minutes`; never before first contact (a fresh provision is not a missing heartbeat) | a heartbeat arrives inside the window |
| `ssl_expiry` | days until the certificate expires `≤ threshold` | more than `threshold` days remain |

`drift` alerts are not evaluated on a schedule — they are opened and resolved directly by
`inventory.reconcile()` through `sync_drift_alerts(account, findings)`.

## Lifecycle (one Alert per rule+target)

```
          breach sustained            recovery
NOOP ───────────────────────▶ firing ──────────▶ resolved
                               ▲   │
                    (operator  │   │ human
                     acks it)  │   ▼
                           acknowledged
```

- **Fire once.** `evaluate_rules()` runs each minute (scheduler). On the first sustained breach
  it inserts one `Alert` (status `firing`), emits `infra:alert.fired`, and notifies **once**.
- **Dedup.** While an alert is open — `firing` *or* `acknowledged` — a continuing breach only
  refreshes it. No duplicate record, no repeat notification. Acknowledging is a human action
  that silences re-notification without resolving.
- **Resolve once.** When the condition clears, the alert moves to `resolved` (`resolved_at`
  set), emits `infra:alert.resolved`, and notifies once. A later clear pass does nothing.

Alert realtime payloads carry no free-text `message` (the event contract is
`additionalProperties:false`); the human-readable line lives on the `Alert` record.

## Notifications

`notify(alert, channels, status)` **never raises** — a failing channel is logged and the
lifecycle proceeds. Configure channels per rule; both read **Infra Settings**:

- **telegram** — `telegram_bot_token` (stored as a password) and `telegram_chat_id`. POSTs to
  the Bot API with a 15 s timeout, 3 attempts, retrying 5xx. An unconfigured token is a no-op,
  not a failure.
- **email** — `frappe.sendmail` to the users holding the **Infra Admin** role.

### Enabling live Telegram delivery

1. Create a bot with @BotFather, copy its token.
2. Add the bot to the target chat/channel and get the numeric `chat_id`.
3. In **Infra Settings** set `telegram_bot_token` and `telegram_chat_id`, save.
4. Trigger a test rule (e.g. a low disk threshold) or wait for the next per-minute pass.

Until a token is set, telegram channels are exercised only by the mocked-HTTP tests; no live
message is sent.

## Where it runs

- `hooks.py` → `scheduler_events` cron, per minute: `monitoring.alerts.evaluate_rules`.
- `inventory.reconcile()` (hourly `sync_all_providers`) calls `sync_drift_alerts`.

## Tests

- `tests/backend/test_alert_rules.py` — pure evaluators (sustain, heartbeat age, ssl window).
- `tests/backend/test_notify.py` — Telegram over mocked HTTP; failure isolation.
- `tests/backend/test_alert_engine.py` — fire/dedup/ack/resolve + drift, on the fake Frappe.
- `infra_control/tests/test_a32_alerts.py` — the same lifecycle against a real site.
