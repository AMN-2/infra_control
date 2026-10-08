# ADR 0006: provisioning from a live plan catalogue

Date: 2026-10-09. Status: accepted (reviewer request 2026-10-08: "choose a plan and create a
complete server without problems").

## Context

`server.provision` takes `region` and `size` as free strings; the UI had no way to run a
creation playbook at all (creation flows were deferred to a "create" form that was never
built), and the bench role installed Node 18 while current Frappe apps require Node 20.

## Decision

- `providers.list` (accounts without tokens) and `providers.options` (regions, available
  sizes with vCPU/RAM/disk/transfer/price, defaults) under the `providers` tag. The catalogue
  is read through the provider client and cached one hour per account. Reading a catalogue is
  not a mutation: the "nothing touches a provider except a job" rule governs changes to
  infrastructure, and this endpoint changes nothing.
- The Servers screen gains "New server": account, region, a plan grid grouped by family
  (basic, general, cpu, memory), hostname, role and tags, then `jobs.run server.provision`.
  Invalid combinations are refused by DigitalOcean and surface as the job's error.
- The `bench` role installs Node 20 from NodeSource (idempotent apt repository), and
  `server_provision.yml` ends with a verification play: the services the role set requires
  are active, `node --version` is 20 or newer, `bench --version` answers, and (when the bench
  was initialised) `bench version` lists frappe. A provision that leaves any of this unmet
  fails the job instead of reporting a half-built server.

## Consequences

Contract tag `providers`; `docs/runbooks/ansible.md` and the Molecule verify cover Node 20.
