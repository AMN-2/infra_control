# ADR 0004: `bench.update` playbook (code rollout to a bench)

Date: 2026-10-08. Status: accepted (reviewer request: "I want to push an update to my SaaS").

## Context

Plan section 9.2 ships `site.migrate` (backup, then `bench migrate` on one site) but nothing
that brings new application code onto a managed bench. Operating the SaaS needs exactly that:
pull the apps' branches, install requirements, migrate every site, rebuild assets, restart.

## Decision

- New playbook `bench.update`, target `Bench`, risk `medium`, capability `ssh` (it runs Ansible on the bench host, so Frappe Cloud benches never see it), provider
  method `update_bench(bench, apps, branch, migrate, build)`; Ansible `bench_update.yml`.
- The pull is `git pull --ff-only` per app (never reset or force); a diverged checkout fails
  the job for a human. `branch` switches the selected apps first; `apps` empty = every app.
- With `migrate` (default) the playbook puts every site on the bench in maintenance mode,
  runs `bench --site all backup` and stops if that fails (plan 13.7), then
  `bench --site all migrate`, and always lifts maintenance. `build` runs `bench build`.
- Frappe Cloud: `MANAGED_UPDATE` covers it later through Press; the base interface carries
  the method so the engine dispatch is identical.
- The UI offers it on each bench row of the server screen (benches have no screen of their
  own), through the same capability-driven `TargetActions`.

## Consequences

Section 9.2's table gains the row. A fleet-wide code rollout is `bench.update` per bench
through Bulk rollouts; `site.migrate` stays the per-site operation.
