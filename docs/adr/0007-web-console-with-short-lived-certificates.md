# ADR 0007: web SSH console with short-lived certificates

Date: 2026-10-09. Status: accepted (reviewer request 2026-10-09: an interactive terminal like
Frappe Cloud's, one-time certificate, and a record of what happened in the session).

## Context

Every change still goes through an `Infra Job`, and `server.exec` runs one audited command.
Operators also need an interactive shell for diagnosis without handing out SSH keys or
losing the record of what was done.

## Decision

- **Certificate authority on the controller** (`infra_control/console/ca.py`): one ed25519 CA
  key under `~/.infra-control/ssh_ca` (0600). Managed servers trust its public key through
  `TrustedUserCAKeys` (`tasks/trust_ca.yml`, applied at provision and by `server.trust_ca`
  for existing servers). No user key is ever authorised on a server for the console.
- **One ticket, one certificate, one session.** `console.ticket` (Infra Admin, audited)
  generates a fresh ed25519 key pair, signs it into a user certificate valid for 10 minutes
  with principal `frappe` and identity `console:<operator>:<server>:<time>`, and stores a
  60-second single-use ticket in Redis. The browser only ever sees the ticket.
- **Bridge** (`infra_control/console/service.py`, aiohttp on 127.0.0.1:8012, behind the edge at
  `/console/`): redeems the ticket (GETDEL), runs the system `ssh` under a pseudo-terminal
  with that certificate, relays bytes to the xterm in the browser, applies resizes, ends on
  30 minutes idle or 4 hours total, deletes the ephemeral key and certificate.
- **Record of the session.** The bridge writes a transcript (`.log`, the full terminal stream)
  and a sidecar (`.json`: who, which server, start, end, bytes, why it ended) under the site's
  `private/infra_console/`. `console.sessions` lists them, `console.transcript` returns the
  last 200 KB, and the Console tab replays them. The server's auth log carries the
  certificate identity, so both sides name the operator.

## Consequences

- The plan's rule "nothing mutates infrastructure except a job" gets an explicit exception
  for Infra Admin interactive sessions, traded for a complete transcript and audit row.
- Contract tag `console`; staging component `console`; Molecule should assert the
  `TrustedUserCAKeys` drop-in on provisioned hosts (follow-up).
