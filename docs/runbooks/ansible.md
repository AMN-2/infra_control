# Ansible on DigitalOcean servers (A2.2)

Every SSH-backed operation on a DigitalOcean server (provisioning's configure stage,
`service.control`, `server.apt_security`, the site playbooks of A2.3) is an Ansible playbook run
by `AnsibleRunner` (`infra_control/providers/digitalocean/ansible.py`) inside the job's worker.
Plan 9.1 step 3 holds: one Ansible task is one `Infra Job Step`.

## Layout

```
ansible/
├── ansible.cfg
├── playbooks/          server_provision.yml, service_control.yml, server_apt_security.yml,
│                       site_{create,backup,restore,migrate,maintenance,add_domain,suspend}.yml,
│                       tasks/ (site_preflight, backup_upload)
├── roles/              base, mariadb, redis, nginx, bench (built-in modules only)
└── molecule/default/   converge, idempotence, verify in Ubuntu 24.04 (systemd container)
```

| Role | Does |
|---|---|
| `base` | apt network timeouts (30 s) and 5 retries first, so a stalled mirror cannot hang a provision; packages, UTC timezone, `frappe` sudo user, sysctl file, 2 GB swap (not in containers), unattended security upgrades |
| `mariadb` | MariaDB with utf8mb4 and InnoDB settings, bound to 127.0.0.1, root over the unix socket; a `infra_admin` database user whose password is generated on the server once and kept in `~frappe/.config/infra-control/db-admin.cnf` (0600) for `bench new-site` and `bench restore` |
| `redis` | Redis bound to localhost, 256 MB cap |
| `nginx` | nginx and certbot, default site removed, global limits, `nginx -t` before every reload |
| `bench` | nodejs, npm, yarn, supervisor, wkhtmltopdf, `bench` CLI via pipx for `frappe`; `bench init` only when `bench_init: true` |

`server_provision.yml` waits for SSH and `cloud-init status --wait`, then applies roles by the
server's role: `all` = every role, `app` = base, redis, nginx, bench, `db` = base, mariadb,
`proxy` = base, nginx.

## How a run works

1. The adapter calls `runner.start(server, playbook, extra_vars)`. The runner refuses any file
   outside `ansible/playbooks/`, creates `<site>/private/infra_ansible/<ident>/`, writes a
   one-host inventory (public IP, `frappe` user, port, the controller key) and launches
   `ansible_runner.run_async` with the bench venv's `ansible-playbook`.
2. The job engine polls `get_status()`. The runner rebuilds the steps from
   `artifacts/<ident>/job_events/*.json` and the result from `artifacts/<ident>/status` on every
   poll. Nothing lives only in memory, so a fresh adapter instance reads the same answer.
3. Each `playbook_on_task_start` is a step. `ok` and `skipped` are Success, `failed` (unless
   `ignore_errors`) and `unreachable` are Failed with Ansible's message as the job error.
4. Cancel drops a `cancel` file in the run directory; ansible-runner's cancel callback reads it.
5. Retry: the engine stores the failed step's title as `_resume_task`, and the runner adds
   `--start-at-task "<title>"`. Site playbooks are not resumed: `site.migrate` must take its
   backup again.

SSH: `StrictHostKeyChecking=accept-new` (the first connection to a new droplet records its key,
later ones must match), `ControlPersist=60s`, pipelining on.

## Controller setup

1. `bench setup requirements` installs `ansible-core` and `ansible-runner` (declared in
   `pyproject.toml`). Without them the adapter uses `UnavailableRunner`, and every SSH-backed
   call fails with "ansible-runner is not installed". Calls never become silent no-ops.
2. The worker's user needs the private key whose public half is the DigitalOcean SSH key
   `infra-control`. Default `~/.ssh/id_ed25519`; override with site config
   `infra_ssh_private_key: /path/to/key`.
3. Run directories accumulate under `sites/<site>/private/infra_ansible/`. They hold events and
   masked-at-display output; prune with a cron or keep them for audits (a retention job arrives
   with A4.2).

## Idempotence (plan 9.2)

```bash
python3 -m venv ~/venvs/infra-ansible-test
~/venvs/infra-ansible-test/bin/pip install "ansible-core>=2.17,<2.20" ansible-runner molecule "molecule-plugins[docker]" docker
~/venvs/infra-ansible-test/bin/ansible-galaxy collection install community.docker ansible.posix
cd ansible && PATH=~/venvs/infra-ansible-test/bin:$PATH molecule test
```

`molecule test` runs destroy, create, prepare, converge, **idempotence**, verify, destroy. `prepare` points the container at `mirrors.digitalocean.com` because `archive.ubuntu.com` did not answer from this controller host (2026-10-07); set `MOLECULE_APT_MIRROR` to use another. The idempotence
step fails if the second converge reports any `changed`. The collections are needed by Molecule's
Docker driver only; the roles themselves use `ansible.builtin` modules, and a unit test enforces
that.

Not covered in containers: swap and sysctl (kernel-level), and `bench init` (minutes of cloning
and asset builds). Both run on a real droplet in the Phase 2 exit gate.
