# Runbook: the provider API is down or rate-limited (A4.3)

## What keeps working

Managed servers and their sites. SSH-backed playbooks (site operations, bench.update,
logs, console, exec) do not need the DigitalOcean API and keep running. Only these stop:
`server.provision`, `server.reboot`, `server.snapshot`, `server.deprovision`, DNS for
`site.add_domain`, the metric collector (DigitalOcean Monitoring) and the hourly
`inventory.sync` discovery of new droplets.

## Symptoms

- Jobs fail with `DigitalOcean … failed with 5xx` or `DigitalOcean unreachable after 3
  attempts`; the client already retried with backoff and honours `Retry-After`.
- `429` → the client sleeps until the rate-limit window resets (at most an hour) before the
  next call; a job may simply take longer.
- Metrics stop, servers show `Down` after 3 minutes (heartbeat rule) although they answer.

## Do

1. Confirm it is the provider: `curl -s https://status.digitalocean.com/api/v2/status.json`
   and the job's error. A `401` instead means the token was revoked: create a new one with
   the scopes in `docs/providers/digitalocean.md` §9 and update the Provider Account.
2. Do not retry provisioning jobs in a loop: one retry after the status page is green.
   Interrupted provisions leave a droplet; `inventory.sync` adopts it once the API is back,
   or delete it from the DigitalOcean console.
3. Suppress noise: acknowledge the heartbeat alerts, or disable the `heartbeat` rule for the
   duration from Alerts → Rules (it resolves itself when metrics return).
4. Site operations stay available; prefer them over server operations until the API is
   healthy.

## After

`inventory.sync` reconciles whatever changed during the outage; drift alerts list anything a
human must decide on.
