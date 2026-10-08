#!/usr/bin/env python3
"""Runs on a managed server (ansible.builtin.script): lists every bench and its sites as JSON.

Read-only. Stdlib only, Python 3.8+ (whatever Ubuntu ships). Output:

{"benches": [{"path": "/home/frappe/frappe-bench", "frappe_version": "15.98.1",
              "apps": [{"app": "frappe", "version": "15.98.1", "branch": "version-15"}],
              "sites": [{"domain": "x.iq", "maintenance_mode": false, "db_name": "_abc"}]}]}
"""

import glob
import json
import os
import re
import sys

HOME_GLOBS = ("/home/*/*", "/opt/*")


def read(path, limit=65536):
	try:
		with open(path, encoding="utf-8", errors="replace") as f:
			return f.read(limit)
	except OSError:
		return ""


def app_version(app_dir, app):
	m = re.search(
		r'^__version__\s*=\s*["\']([^"\']+)["\']', read(os.path.join(app_dir, app, "__init__.py")), re.M
	)
	return m.group(1) if m else None


def app_branch(app_dir):
	head = read(os.path.join(app_dir, ".git", "HEAD")).strip()
	if head.startswith("ref: refs/heads/"):
		return head[len("ref: refs/heads/") :]
	return head[:12] or None  # detached: the commit


def apps_of(bench):
	names = [
		line.strip() for line in read(os.path.join(bench, "sites", "apps.txt")).splitlines() if line.strip()
	]
	if not names:
		names = sorted(
			d
			for d in os.listdir(os.path.join(bench, "apps"))
			if os.path.isdir(os.path.join(bench, "apps", d, d))
		)
	out = []
	for app in names:
		app_dir = os.path.join(bench, "apps", app)
		if not os.path.isdir(app_dir):
			continue
		out.append({"app": app, "version": app_version(app_dir, app), "branch": app_branch(app_dir)})
	return out


def sites_of(bench):
	out = []
	sites_dir = os.path.join(bench, "sites")
	for entry in sorted(os.listdir(sites_dir)) if os.path.isdir(sites_dir) else []:
		cfg_path = os.path.join(sites_dir, entry, "site_config.json")
		if not os.path.isfile(cfg_path):
			continue
		try:
			cfg = json.loads(read(cfg_path) or "{}")
		except ValueError:
			cfg = {}
		out.append(
			{
				"domain": entry,
				"maintenance_mode": bool(cfg.get("maintenance_mode")),
				"db_name": cfg.get("db_name"),
			}
		)
	return out


def main():
	benches = []
	seen = set()
	for pattern in HOME_GLOBS:
		for candidate in sorted(glob.glob(pattern)):
			path = os.path.realpath(candidate)
			if path in seen or not os.path.isdir(os.path.join(path, "apps", "frappe")):
				continue
			seen.add(path)
			apps = apps_of(path)
			frappe_version = next((a["version"] for a in apps if a["app"] == "frappe"), None)
			benches.append(
				{"path": path, "frappe_version": frappe_version, "apps": apps, "sites": sites_of(path)}
			)
	json.dump({"benches": benches}, sys.stdout)
	return 0


if __name__ == "__main__":
	sys.exit(main())
