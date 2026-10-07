### Infra Control

Infrastructure orchestrator for SmartChoice IQ hosting: servers, benches and sites on
DigitalOcean and Frappe Cloud, behind one audited job engine and one mission-control UI.

Read `AGENTS.md` and `ORCHESTRATOR_IMPLEMENTATION_PLAN.md` before contributing.

### Layout

```
contracts/        OpenAPI 3.1 spec, realtime event schemas, mock server (binding for both agents)
infra_control/    Frappe app: api/, core/, job_engine/, providers/, monitoring/, bulk/
ansible/          Roles and playbooks run by the job engine on DigitalOcean servers
frontend/         Vue 3 SPA served at /infra
tests/backend/    pytest unit + contract tests;  tests/frontend/  vitest + Playwright
docs/             providers/, runbooks/, design/, adr/, QUESTIONS.md
```

### Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench --site <control-plane-site> install-app infra_control
```

The control plane runs on its own dedicated site and droplet. Do not install it on a site that
hosts client workloads.

### Development

```bash
pip install -e ".[dev]"          # ruff, mypy, pytest, contract validators
ruff check . && ruff format --check .
mypy --strict infra_control
pytest tests/backend
```

`pre-commit install` enables ruff on commit. CI runs the same checks plus a path-ownership guard.

### License

mit
