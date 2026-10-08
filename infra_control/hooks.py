app_name = "infra_control"
app_title = "Infra Control"
app_publisher = "SmartChoice IQ"
app_description = (
	"Infrastructure orchestrator for servers, benches and sites on DigitalOcean and Frappe Cloud"
)
app_email = "amen562aff@gmail.com"
app_license = "mit"

# The Vue SPA (owned by Agent B) is served at /infra by infra_control/www/infra.{py,html}.
# Every sub-path renders the same page so the SPA router owns /infra/* (Q-B2, SPA fallback).
website_route_rules = [{"from_route": "/infra/<path:app_path>", "to_route": "infra"}]

# Roles (Infra Admin / Operator / Viewer) and the built-in alert rules are created in code so the
# install is idempotent (A1.1).
after_install = "infra_control.install.after_install"
after_migrate = "infra_control.install.after_migrate"

# Infra users land on /infra after login unless they asked for another page (core/login.py).
on_session_creation = ["infra_control.core.login.on_session_creation"]

# Crash recovery runs every minute (A1.2). Phase 3 adds the collector, alert engine and drift sync:
# 	"* * * * *": [..., "infra_control.monitoring.collector.collect_all",
# 	              "infra_control.monitoring.alerts.evaluate_rules"],
# 	"hourly": ["infra_control.monitoring.drift.sync_all_providers"],
# 	"daily": ["infra_control.providers.frappe_cloud.contract_test.run"],
scheduler_events = {
	"cron": {
		"* * * * *": [
			"infra_control.job_engine.recovery.run",
			# Metric collector (A3.1): one Server Metric per managed server, per minute.
			"infra_control.monitoring.collector.collect_all",
			# Alert engine (A3.2): evaluate every enabled rule, fire/resolve and notify.
			"infra_control.monitoring.alerts.evaluate_rules",
		],
	},
	"hourly": [
		# inventory.sync on every enabled Provider Account (A2.5, plan 9.2: hourly, feeds drift).
		"infra_control.inventory.schedule.sync_all_providers",
		# Roll 1m metrics up to 1h and 1d (A3.1).
		"infra_control.monitoring.rollup.run_rollups",
	],
	"daily": [
		# Metric retention: 1m 7 days, 1h 90 days, 1d 2 years (A3.1).
		"infra_control.monitoring.rollup.purge_old_metrics",
	],
}
