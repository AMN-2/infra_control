# Runbook: a restore failed (A4.3)

Applies to `site.restore` (over a live site), `site.restore_test` (throwaway site), and the
restore step of a controller rebuild.

## Read the job first

Every step's output is in the job viewer (stdout/stderr of `bench restore`, masked). The
usual causes, by step:

| Step | Cause | Fix |
|---|---|---|
| Download the backup files | presigned URL expired (6 h) or Spaces unreachable | re-run the job (new URLs); check Infra Settings → Spaces |
| Read the database admin credentials | `~frappe/.config/infra-control/db-admin.cnf` missing on an old server | re-run the `mariadb` role: `server.provision`'s configure stage or a fresh provision; see `docs/runbooks/ansible.md` |
| Restore | dump from a newer Frappe/app version than the bench | `bench.update` the bench to at least that version, then retry; or restore on a bench of the right version |
| Restore | disk full (`df -h`) | `server.logs` → system; free space, retry |
| Restore | `--with-private-files` of a site that had none | expected; the job only passes the files it uploaded |

## site.restore over a live site failed half-way

`bench restore` replaces the database atomically after the import; a failure before that
point leaves the site as it was. If it failed after (rare: files step), the database is the
backup's and the files are the old ones: re-run `site.restore` with the same backup, which
re-imports both. The site stays in maintenance mode until a restore completes:
`site.maintenance` with `on: false` lifts it by hand.

## site.restore_test failed

Nothing on the real site changed; the throwaway site is dropped in the `always` block. The
Backup row shows `restore_test_result: failed` and the security posture turns red until a
test passes. Act on the cause above, then run `site.restore_test` again on that backup; if the
backup itself is corrupt, take a fresh `site.backup` and delete the bad one from Spaces
(retention will not, because it keeps the newest).

## Controller rebuild restore failed

`bench restore` on the new controller needs the same major Frappe version as the backup;
`bench version` on the old controller (or the `frappe` version in `pyproject.toml` of the
`integration/phase2` checkout) says which. Keep the off-site bucket's previous day as the
fallback: retention keeps 30 days by default.
