# Monitoring (A3.1)

Everything the control plane knows about a server's health comes from the metric collector.
Monitoring never calls DigitalOcean, Press or SSH directly (plan §3): it reads through the
provider layer (`Provider.get_metrics`, capability-gated).

## Pipeline

| Job | Schedule | Does |
|---|---|---|
| `infra_control.monitoring.collector.collect_all` | every minute (cron) | one `Server Metric` (`1m`) per managed server with the `metrics` capability; updates `last_heartbeat` and status; emits `infra:server.heartbeat` |
| `infra_control.monitoring.rollup.run_rollups` | hourly | folds `1m` → `1h` and `1h` → `1d` (idempotent upsert per bucket) |
| `infra_control.monitoring.rollup.purge_old_metrics` | daily | deletes metrics past retention |

`aggregate.py` is pure (rollup folds, resolution choice, retention cutoffs) and unit-tested.
cpu/ram/disk/load1 average into a bucket; `queue_backlog` takes the bucket's max.

| Resolution | Kept for |
|---|---|
| `1m` | 7 days |
| `1h` | 90 days |
| `1d` | 2 years |

## Status from a collection

- A collection that reaches the server sets it `Active`, or `Degraded` when cpu, ram or disk is
  at or above 90 %. It always clears a stale `Down`.
- No successful heartbeat for 3 minutes marks the server `Down` (plan §9.4). The alert engine
  (A3.2) turns that into a notification.
- One server's failure never stops the sweep; the error is logged and the next server runs.

## API

`GET /api/method/infra_control.api.metrics.series?server=&metric=&from=&to=&resolution=` returns
a `MetricSeries`. Without `resolution` the coarsest that keeps the range under 1000 points is
chosen (an hour → `1m`, a month → `1h`, a year → `1d`).

## DigitalOcean requirement

`get_metrics` reads DigitalOcean Monitoring, which needs:

1. The droplet created with `monitoring: true` (the provision playbook sets it).
2. The API token to carry the **`monitoring:read`** scope. Without it the monitoring endpoint
   returns 401 and the collector logs the server as failed (metrics simply do not flow; the
   server keeps its last status). Add the scope to the staging token to enable live metrics.

`queue_backlog` is not in DO Monitoring; the collector records 0 for it until the collector
playbook (a later task) reads it from the host.
