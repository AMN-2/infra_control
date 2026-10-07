/* eslint-disable */
// GENERATED from contracts/events by scripts/gen-events.mjs. Do not edit.

/**
 * Emitted whenever an Infra Job changes status or progress. Terminal statuses (Success, Failed, Cancelled) are emitted exactly once.
 */
export interface JobUpdated {
	/**
	 * Infra Job name
	 */
	job: string;
	status: "Queued" | "Running" | "Success" | "Failed" | "Cancelled";
	progress: number;
}
/**
 * Emitted when a step of a job is created or changes status. Steps are ordered by idx.
 */
export interface JobStep {
	job: string;
	idx: number;
	title: string;
	status: "Queued" | "Running" | "Success" | "Failed" | "Cancelled" | "Skipped";
}
/**
 * One masked output chunk for a step. Chunks arrive in order per (job, idx); the client appends them. Max 4 KB per event.
 */
export interface JobLog {
	job: string;
	idx: number;
	chunk: string;
}
/**
 * Emitted after every target of a bulk operation reaches a terminal state and on every status change.
 */
export interface BulkUpdated {
	bulk: string;
	status: "Queued" | "Running" | "Paused" | "Halted" | "Success" | "Failed" | "Cancelled";
	done: number;
	total: number;
	/**
	 * 0 = canary
	 */
	current_batch: number;
}
/**
 * Emitted once per collector run (every minute) per server. cpu, ram and disk are percentages.
 */
export interface ServerHeartbeat {
	server: string;
	status: "Provisioning" | "Active" | "Degraded" | "Down" | "Archived";
	cpu: number;
	ram: number;
	disk: number;
	ts: string;
}
/**
 * Emitted once when an alert starts firing.
 */
export interface AlertFired {
	alert: string;
	rule: string;
	target: {
		target_doctype: "Server" | "Site" | "Bench" | "Provider Account";
		target_name: string;
	};
	severity: "info" | "warning" | "critical";
}
/**
 * Emitted once when a firing or acknowledged alert resolves.
 */
export interface AlertResolved {
	alert: string;
	rule: string;
	target: {
		target_doctype: "Server" | "Site" | "Bench" | "Provider Account";
		target_name: string;
	};
	severity: "info" | "warning" | "critical";
}
/**
 * Emitted when a Server, Bench or Site document is created, updated or deleted, including by inventory sync. Clients refetch the affected entity or the topology.
 */
export interface InventoryChanged {
	doctype: "Server" | "Bench" | "Site" | "Provider Account";
	name: string;
	change: "created" | "updated" | "deleted";
}

/** Event name -> payload type. */
export interface EventMap {
	"infra:job.updated": JobUpdated;
	"infra:job.step": JobStep;
	"infra:job.log": JobLog;
	"infra:bulk.updated": BulkUpdated;
	"infra:server.heartbeat": ServerHeartbeat;
	"infra:alert.fired": AlertFired;
	"infra:alert.resolved": AlertResolved;
	"infra:inventory.changed": InventoryChanged;
}

export type EventName = keyof EventMap;

/** JSON Schemas (2020-12) for runtime validation; identical to contracts/events. */
export const eventSchemas: Record<EventName, Record<string, unknown>> = {
	"infra:job.updated": {
		"$schema": "https://json-schema.org/draft/2020-12/schema",
		"title": "infra:job.updated",
		"description": "Emitted whenever an Infra Job changes status or progress. Terminal statuses (Success, Failed, Cancelled) are emitted exactly once.",
		"type": "object",
		"additionalProperties": false,
		"required": [
			"job",
			"status",
			"progress"
		],
		"properties": {
			"job": {
				"type": "string",
				"description": "Infra Job name"
			},
			"status": {
				"type": "string",
				"enum": [
					"Queued",
					"Running",
					"Success",
					"Failed",
					"Cancelled"
				]
			},
			"progress": {
				"type": "integer",
				"minimum": 0,
				"maximum": 100
			}
		}
	},
	"infra:job.step": {
		"$schema": "https://json-schema.org/draft/2020-12/schema",
		"title": "infra:job.step",
		"description": "Emitted when a step of a job is created or changes status. Steps are ordered by idx.",
		"type": "object",
		"additionalProperties": false,
		"required": [
			"job",
			"idx",
			"title",
			"status"
		],
		"properties": {
			"job": {
				"type": "string"
			},
			"idx": {
				"type": "integer",
				"minimum": 0
			},
			"title": {
				"type": "string"
			},
			"status": {
				"type": "string",
				"enum": [
					"Queued",
					"Running",
					"Success",
					"Failed",
					"Cancelled",
					"Skipped"
				]
			}
		}
	},
	"infra:job.log": {
		"$schema": "https://json-schema.org/draft/2020-12/schema",
		"title": "infra:job.log",
		"description": "One masked output chunk for a step. Chunks arrive in order per (job, idx); the client appends them. Max 4 KB per event.",
		"type": "object",
		"additionalProperties": false,
		"required": [
			"job",
			"idx",
			"chunk"
		],
		"properties": {
			"job": {
				"type": "string"
			},
			"idx": {
				"type": "integer",
				"minimum": 0
			},
			"chunk": {
				"type": "string",
				"maxLength": 4096
			}
		}
	},
	"infra:bulk.updated": {
		"$schema": "https://json-schema.org/draft/2020-12/schema",
		"title": "infra:bulk.updated",
		"description": "Emitted after every target of a bulk operation reaches a terminal state and on every status change.",
		"type": "object",
		"additionalProperties": false,
		"required": [
			"bulk",
			"status",
			"done",
			"total",
			"current_batch"
		],
		"properties": {
			"bulk": {
				"type": "string"
			},
			"status": {
				"type": "string",
				"enum": [
					"Queued",
					"Running",
					"Paused",
					"Halted",
					"Success",
					"Failed",
					"Cancelled"
				]
			},
			"done": {
				"type": "integer",
				"minimum": 0
			},
			"total": {
				"type": "integer",
				"minimum": 0
			},
			"current_batch": {
				"type": "integer",
				"minimum": 0,
				"description": "0 = canary"
			}
		}
	},
	"infra:server.heartbeat": {
		"$schema": "https://json-schema.org/draft/2020-12/schema",
		"title": "infra:server.heartbeat",
		"description": "Emitted once per collector run (every minute) per server. cpu, ram and disk are percentages.",
		"type": "object",
		"additionalProperties": false,
		"required": [
			"server",
			"status",
			"cpu",
			"ram",
			"disk",
			"ts"
		],
		"properties": {
			"server": {
				"type": "string"
			},
			"status": {
				"type": "string",
				"enum": [
					"Provisioning",
					"Active",
					"Degraded",
					"Down",
					"Archived"
				]
			},
			"cpu": {
				"type": "number",
				"minimum": 0,
				"maximum": 100
			},
			"ram": {
				"type": "number",
				"minimum": 0,
				"maximum": 100
			},
			"disk": {
				"type": "number",
				"minimum": 0,
				"maximum": 100
			},
			"ts": {
				"type": "string",
				"format": "date-time"
			}
		}
	},
	"infra:alert.fired": {
		"$schema": "https://json-schema.org/draft/2020-12/schema",
		"title": "infra:alert.fired",
		"description": "Emitted once when an alert starts firing.",
		"type": "object",
		"additionalProperties": false,
		"required": [
			"alert",
			"rule",
			"target",
			"severity"
		],
		"properties": {
			"alert": {
				"type": "string"
			},
			"rule": {
				"type": "string"
			},
			"target": {
				"type": "object",
				"additionalProperties": false,
				"required": [
					"target_doctype",
					"target_name"
				],
				"properties": {
					"target_doctype": {
						"type": "string",
						"enum": [
							"Server",
							"Site",
							"Bench",
							"Provider Account"
						]
					},
					"target_name": {
						"type": "string"
					}
				}
			},
			"severity": {
				"type": "string",
				"enum": [
					"info",
					"warning",
					"critical"
				]
			}
		}
	},
	"infra:alert.resolved": {
		"$schema": "https://json-schema.org/draft/2020-12/schema",
		"title": "infra:alert.resolved",
		"description": "Emitted once when a firing or acknowledged alert resolves.",
		"type": "object",
		"additionalProperties": false,
		"required": [
			"alert",
			"rule",
			"target",
			"severity"
		],
		"properties": {
			"alert": {
				"type": "string"
			},
			"rule": {
				"type": "string"
			},
			"target": {
				"type": "object",
				"additionalProperties": false,
				"required": [
					"target_doctype",
					"target_name"
				],
				"properties": {
					"target_doctype": {
						"type": "string",
						"enum": [
							"Server",
							"Site",
							"Bench",
							"Provider Account"
						]
					},
					"target_name": {
						"type": "string"
					}
				}
			},
			"severity": {
				"type": "string",
				"enum": [
					"info",
					"warning",
					"critical"
				]
			}
		}
	},
	"infra:inventory.changed": {
		"$schema": "https://json-schema.org/draft/2020-12/schema",
		"title": "infra:inventory.changed",
		"description": "Emitted when a Server, Bench or Site document is created, updated or deleted, including by inventory sync. Clients refetch the affected entity or the topology.",
		"type": "object",
		"additionalProperties": false,
		"required": [
			"doctype",
			"name",
			"change"
		],
		"properties": {
			"doctype": {
				"type": "string",
				"enum": [
					"Server",
					"Bench",
					"Site",
					"Provider Account"
				]
			},
			"name": {
				"type": "string"
			},
			"change": {
				"type": "string",
				"enum": [
					"created",
					"updated",
					"deleted"
				]
			}
		}
	}
};
