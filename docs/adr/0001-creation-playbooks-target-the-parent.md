# ADR 0001: creation playbooks target the parent document

Date: 2026-10-07. Status: accepted (reviewer decision in the PR #4 contracts review).

## Context

Plan section 9.2 lists `server.provision` with target `Server` and `site.create` with target `Site`,
but `jobs.run` (section 6.1) requires an existing `target_name`, so a job cannot target a document
that does not exist yet.

## Decision

- `Bench` is added to `TargetDoctype`.
- `server.provision` targets the `Provider Account`; `site.create` targets the `Bench`. The new
  entity's fields travel in `params`, described by the playbook's `params_schema`.
- `Playbook.creates` names the doctype a playbook creates (`Server`, `Site`) or is `null`.
- `Job.created` is a nullable `TargetRef` set when the job succeeds; realtime
  `infra:inventory.changed` (`change: created`) is emitted at the same moment.
- The job engine locks the parent's server for `site.create` (DigitalOcean) and nothing for
  `server.provision` (no server exists yet); the provider adapter's `OpRef` is polled as usual.

## Consequences

The frontend renders "create" forms from `params_schema` when `creates` is set, and navigates to
`Job.created` on success. Section 9.2 of the plan is read with these two targets.
