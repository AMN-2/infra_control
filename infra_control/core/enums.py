"""Unified enums (plan section 5, contracts/openapi.yaml). A contract test keeps them in sync.

These are the only status vocabularies that leave the backend. Provider-specific strings are
mapped to them inside `infra_control/providers/<name>/` and never reach this module.
"""

from __future__ import annotations

from enum import StrEnum


class Provider(StrEnum):
	DIGITALOCEAN = "digitalocean"
	FRAPPE_CLOUD = "frappe_cloud"


class Capability(StrEnum):
	SITE = "site"
	BENCH = "bench"
	SERVER = "server"
	SSH = "ssh"
	SNAPSHOT = "snapshot"
	SERVICE_CONTROL = "service_control"
	METRICS = "metrics"
	CUSTOM_PLAYBOOK = "custom_playbook"
	MANAGED_BACKUP = "managed_backup"
	MANAGED_UPDATE = "managed_update"


class ServerStatus(StrEnum):
	PROVISIONING = "Provisioning"
	ACTIVE = "Active"
	DEGRADED = "Degraded"
	DOWN = "Down"
	ARCHIVED = "Archived"


class SiteStatus(StrEnum):
	PENDING = "Pending"
	ACTIVE = "Active"
	MAINTENANCE = "Maintenance"
	SUSPENDED = "Suspended"
	BROKEN = "Broken"
	ARCHIVED = "Archived"


class JobStatus(StrEnum):
	QUEUED = "Queued"
	RUNNING = "Running"
	SUCCESS = "Success"
	FAILED = "Failed"
	CANCELLED = "Cancelled"


class StepStatus(StrEnum):
	QUEUED = "Queued"
	RUNNING = "Running"
	SUCCESS = "Success"
	FAILED = "Failed"
	CANCELLED = "Cancelled"
	SKIPPED = "Skipped"


class BulkStatus(StrEnum):
	QUEUED = "Queued"
	RUNNING = "Running"
	PAUSED = "Paused"
	HALTED = "Halted"
	SUCCESS = "Success"
	FAILED = "Failed"
	CANCELLED = "Cancelled"


class BulkPhase(StrEnum):
	BACKUP = "backup"
	CANARY = "canary"
	BATCHES = "batches"
	DONE = "done"


class BulkTargetStatus(StrEnum):
	PENDING = "Pending"
	RUNNING = "Running"
	SUCCESS = "Success"
	FAILED = "Failed"
	SKIPPED = "Skipped"


class AlertStatus(StrEnum):
	FIRING = "firing"
	ACKNOWLEDGED = "acknowledged"
	RESOLVED = "resolved"


class Severity(StrEnum):
	INFO = "info"
	WARNING = "warning"
	CRITICAL = "critical"


class Risk(StrEnum):
	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"


class TargetDoctype(StrEnum):
	SERVER = "Server"
	SITE = "Site"
	BENCH = "Bench"
	PROVIDER_ACCOUNT = "Provider Account"


class ServerRole(StrEnum):
	APP = "app"
	DB = "db"
	PROXY = "proxy"
	ALL = "all"


class MetricName(StrEnum):
	CPU = "cpu"
	RAM = "ram"
	DISK = "disk"
	LOAD1 = "load1"
	QUEUE_BACKLOG = "queue_backlog"


class Resolution(StrEnum):
	ONE_MINUTE = "1m"
	ONE_HOUR = "1h"
	ONE_DAY = "1d"


class FailurePolicy(StrEnum):
	HALT = "halt"
	CONTINUE = "continue"


class Operator(StrEnum):
	GT = "gt"
	GTE = "gte"
	LT = "lt"
	LTE = "lte"
	EQ = "eq"


class AlertChannel(StrEnum):
	TELEGRAM = "telegram"
	EMAIL = "email"


class BackupKind(StrEnum):
	DB = "db"
	FILES = "files"
	SNAPSHOT = "snapshot"


class AuditResult(StrEnum):
	SUCCESS = "success"
	FAILED = "failed"
	DENIED = "denied"


class TenantStatus(StrEnum):
	ACTIVE = "active"
	SUSPENDED = "suspended"


class UpdateState(StrEnum):
	"""Whether a bench app is behind its upstream branch (ADR 0009)."""

	UPDATE_AVAILABLE = "update_available"
	UP_TO_DATE = "up_to_date"
	UNKNOWN = "unknown"


class BackupFrequency(StrEnum):
	HOURLY = "hourly"
	DAILY = "daily"
	WEEKLY = "weekly"


class AlertRuleKind(StrEnum):
	METRIC = "metric"
	HEARTBEAT = "heartbeat"
	SSL_EXPIRY = "ssl_expiry"
	DRIFT = "drift"
	CONTRACT = "contract"


TERMINAL_JOB_STATUSES: frozenset[JobStatus] = frozenset(
	{JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.CANCELLED}
)
TERMINAL_BULK_STATUSES: frozenset[BulkStatus] = frozenset(
	{BulkStatus.SUCCESS, BulkStatus.FAILED, BulkStatus.CANCELLED}
)

# Plan section 4.2.
PROVIDER_CAPABILITIES: dict[Provider, frozenset[Capability]] = {
	Provider.DIGITALOCEAN: frozenset(
		{
			Capability.SITE,
			Capability.BENCH,
			Capability.SERVER,
			Capability.SSH,
			Capability.SNAPSHOT,
			Capability.SERVICE_CONTROL,
			Capability.METRICS,
			Capability.CUSTOM_PLAYBOOK,
		}
	),
	Provider.FRAPPE_CLOUD: frozenset(
		{Capability.SITE, Capability.BENCH, Capability.MANAGED_BACKUP, Capability.MANAGED_UPDATE}
	),
}

# Which fields each alert rule kind uses (contracts/openapi.yaml, AlertRule).
RULE_KIND_FIELDS: dict[AlertRuleKind, frozenset[str]] = {
	AlertRuleKind.METRIC: frozenset({"metric", "operator", "threshold", "for_minutes"}),
	AlertRuleKind.HEARTBEAT: frozenset({"for_minutes"}),
	AlertRuleKind.SSL_EXPIRY: frozenset({"threshold"}),
	AlertRuleKind.DRIFT: frozenset(),
	AlertRuleKind.CONTRACT: frozenset(),
}
RULE_KIND_TARGET: dict[AlertRuleKind, TargetDoctype] = {
	AlertRuleKind.METRIC: TargetDoctype.SERVER,
	AlertRuleKind.HEARTBEAT: TargetDoctype.SERVER,
	AlertRuleKind.SSL_EXPIRY: TargetDoctype.SITE,
	AlertRuleKind.DRIFT: TargetDoctype.PROVIDER_ACCOUNT,
	AlertRuleKind.CONTRACT: TargetDoctype.PROVIDER_ACCOUNT,
}
