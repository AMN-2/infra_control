app_name = "infra_control"
app_title = "Infra Control"
app_publisher = "SmartChoice IQ"
app_description = (
	"Infrastructure orchestrator for servers, benches and sites on DigitalOcean and Frappe Cloud"
)
app_email = "amen562aff@gmail.com"
app_license = "mit"

# The Vue SPA (owned by Agent B) is served at /infra. Wiring is added in Phase 1 (A1.4 / B1.2).
# website_route_rules = [{"from_route": "/infra/<path:app_path>", "to_route": "infra"}]

# Roles and fixtures are added in Phase 1 (A1.1).
# fixtures = ["Role"]

# Scheduled tasks are added in Phase 1 (crash recovery) and Phase 3 (collector, rollups, alerts).
# scheduler_events = {
# 	"cron": {
# 		"* * * * *": [
# 			"infra_control.monitoring.collector.collect_all",
# 			"infra_control.monitoring.alerts.evaluate_rules",
# 			"infra_control.job_engine.recovery.fail_stale_jobs",
# 		],
# 	},
# 	"hourly": ["infra_control.monitoring.drift.sync_all_providers"],
# 	"daily": ["infra_control.providers.frappe_cloud.contract_test.run"],
# }
