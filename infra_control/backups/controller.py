"""Controller self-backup off DigitalOcean (A4.2, security requirement 11): every day the
controller's own site is backed up (`bench backup --with-files`) and the files are uploaded to
an S3-compatible bucket outside DigitalOcean, configured on `Infra Settings` (off-site
endpoint, bucket, key, secret, retention days). Nothing runs when it is not configured; the
security posture reports both the configuration and the age of the newest upload."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import now_datetime

PREFIX = "controller"


@dataclass(frozen=True)
class OffsiteConfig:
	endpoint_url: str
	bucket: str
	region: str
	key: str = field(repr=False)
	secret: str = field(repr=False)
	retain_days: int = 30


def load_offsite_config() -> OffsiteConfig | None:
	doc: Any = frappe.get_doc("Infra Settings")
	if not (doc.get("offsite_endpoint_url") and doc.get("offsite_bucket")):
		return None
	return OffsiteConfig(
		endpoint_url=str(doc.offsite_endpoint_url).rstrip("/"),
		bucket=str(doc.offsite_bucket),
		region=str(doc.get("offsite_region") or "auto"),
		key=str(doc.get_password("offsite_key") or ""),
		secret=str(doc.get_password("offsite_secret") or ""),
		retain_days=int(doc.get("offsite_retain_days") or 30),
	)


def s3_client(config: OffsiteConfig) -> Any:
	import boto3

	return boto3.client(
		"s3",
		endpoint_url=config.endpoint_url,
		region_name=config.region,
		aws_access_key_id=config.key,
		aws_secret_access_key=config.secret,
	)


def backup_argv(site: str) -> list[str]:
	"""Pure: the bench command that writes the controller site's backup."""
	return ["bench", "--site", site, "backup", "--with-files"]


def backup_dir(site: str) -> Path:
	return Path(frappe.get_site_path("private", "backups"))


def newest_files(directory: Path, since: datetime) -> list[Path]:
	"""Pure given the directory: backup files written after `since` (the run that just finished)."""
	return sorted(
		p
		for p in directory.glob("*")
		if p.is_file() and datetime.fromtimestamp(p.stat().st_mtime, UTC) >= since
	)


def keys_to_prune(keys: list[tuple[str, datetime]], now: datetime, retain_days: int) -> list[str]:
	"""Pure: object keys older than the retention window."""
	cutoff = now - timedelta(days=max(1, retain_days))
	return [k for k, ts in keys if ts < cutoff]


def run_daily() -> dict[str, Any]:
	"""Scheduler: back up the controller site and ship it off-site; prune by age."""
	config = load_offsite_config()
	if config is None:
		return {"skipped": "offsite backup not configured"}
	site = str(frappe.local.site)
	started = datetime.now(UTC) - timedelta(seconds=5)
	bench_root = Path(frappe.utils.get_bench_path())
	# argv comes from backup_argv (fixed bench command; the site name is this controller's own).
	result = subprocess.run(  # noqa: S603
		backup_argv(site), cwd=bench_root, capture_output=True, text=True, timeout=3600, check=False
	)
	if result.returncode != 0:
		frappe.db.set_value("Infra Settings", None, {"offsite_last_error": result.stderr[-500:]})
		frappe.log_error(title="controller backup failed", message=result.stderr[-2000:])
		return {"uploaded": 0, "error": "bench backup failed"}
	client = s3_client(config)
	uploaded = 0
	stamp = started.strftime("%Y%m%d")
	for path in newest_files(backup_dir(site), started):
		client.upload_file(str(path), config.bucket, f"{PREFIX}/{site}/{stamp}/{path.name}")
		uploaded += 1
		os.unlink(path)
	listing = client.list_objects_v2(Bucket=config.bucket, Prefix=f"{PREFIX}/{site}/")
	keys = [(str(o["Key"]), o["LastModified"]) for o in listing.get("Contents", [])]
	pruned = 0
	for key in keys_to_prune(keys, datetime.now(UTC), config.retain_days):
		client.delete_object(Bucket=config.bucket, Key=key)
		pruned += 1
	frappe.db.set_value(
		"Infra Settings", None, {"offsite_last_run": now_datetime(), "offsite_last_error": None}
	)
	frappe.db.commit()
	return {"uploaded": uploaded, "pruned": pruned}
