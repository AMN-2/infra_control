"""DigitalOcean Spaces (S3-compatible) for off-site backups. Thin wrapper around boto3.

Backups are stored under `<site>/<YYYYMMDD_HHMMSS>-<file>`; `Backup.location` records
`spaces://<bucket>/<key>` and never a signed URL (contract).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from infra_control.core.errors import ProviderError

SCHEME = "spaces://"


@dataclass(frozen=True)
class SpacesConfig:
	bucket: str
	region: str
	key: str = field(repr=False)
	secret: str = field(repr=False)

	@property
	def endpoint(self) -> str:
		return f"https://{self.region}.digitaloceanspaces.com"


@dataclass(frozen=True)
class StoredObject:
	key: str
	size_bytes: int
	last_modified: Any

	@property
	def size_mb(self) -> float:
		return round(self.size_bytes / (1024 * 1024), 2)


def location(bucket: str, key: str) -> str:
	return f"{SCHEME}{bucket}/{key}"


def parse_location(value: str) -> tuple[str, str]:
	if not value.startswith(SCHEME) or "/" not in value[len(SCHEME) :]:
		raise ProviderError("Not a Spaces location", {"location": value})
	bucket, key = value[len(SCHEME) :].split("/", 1)
	return bucket, key


class SpacesClient:
	def __init__(self, config: SpacesConfig, client: Any | None = None) -> None:
		self.config = config
		self._s3: Any = client or boto3.client(
			"s3",
			region_name=config.region,
			endpoint_url=config.endpoint,
			aws_access_key_id=config.key,
			aws_secret_access_key=config.secret,
			config=Config(
				retries={"max_attempts": 5, "mode": "standard"}, connect_timeout=10, read_timeout=120
			),
		)

	def upload(self, path: Path | str, key: str) -> str:
		try:
			self._s3.upload_file(str(path), self.config.bucket, key)
		except (BotoCoreError, ClientError) as exc:
			raise ProviderError("Spaces upload failed", {"key": key, "error": str(exc)}) from exc
		return location(self.config.bucket, key)

	def download(self, key: str, path: Path | str) -> None:
		try:
			self._s3.download_file(self.config.bucket, key, str(path))
		except (BotoCoreError, ClientError) as exc:
			raise ProviderError("Spaces download failed", {"key": key, "error": str(exc)}) from exc

	def list(self, prefix: str = "") -> list[StoredObject]:
		out: list[StoredObject] = []
		try:
			paginator = self._s3.get_paginator("list_objects_v2")
			for page in paginator.paginate(Bucket=self.config.bucket, Prefix=prefix):
				for obj in page.get("Contents") or []:
					out.append(
						StoredObject(str(obj["Key"]), int(obj.get("Size", 0)), obj.get("LastModified"))
					)
		except (BotoCoreError, ClientError) as exc:
			raise ProviderError("Spaces listing failed", {"prefix": prefix, "error": str(exc)}) from exc
		return out

	def delete(self, key: str) -> None:
		try:
			self._s3.delete_object(Bucket=self.config.bucket, Key=key)
		except (BotoCoreError, ClientError) as exc:
			raise ProviderError("Spaces delete failed", {"key": key, "error": str(exc)}) from exc

	def exists(self, key: str) -> bool:
		try:
			self._s3.head_object(Bucket=self.config.bucket, Key=key)
		except ClientError as exc:
			code = str(exc.response.get("Error", {}).get("Code", ""))
			if code in ("404", "NoSuchKey", "NotFound"):
				return False
			raise ProviderError("Spaces head failed", {"key": key, "error": str(exc)}) from exc
		except BotoCoreError as exc:
			raise ProviderError("Spaces head failed", {"key": key, "error": str(exc)}) from exc
		return True


PRESIGN_SECONDS = 6 * 3600
"""Lifetime of the upload/download URLs handed to a server: long enough for a large backup,
short enough that a leaked URL is useless the next day. The keys never leave the controller."""


def _presign(client: SpacesClient, method: str, key: str, expires: int) -> str:
	try:
		url: Any = client._s3.generate_presigned_url(
			method, Params={"Bucket": client.config.bucket, "Key": key}, ExpiresIn=expires
		)
	except (BotoCoreError, ClientError) as exc:
		raise ProviderError("Spaces presign failed", {"key": key, "error": str(exc)}) from exc
	return str(url)


def presign_put(client: SpacesClient, key: str, expires: int = PRESIGN_SECONDS) -> str:
	return _presign(client, "put_object", key, expires)


def presign_get(client: SpacesClient, key: str, expires: int = PRESIGN_SECONDS) -> str:
	return _presign(client, "get_object", key, expires)


def object_size(client: SpacesClient, key: str) -> int | None:
	"""Size in bytes, or None when the object does not exist."""
	try:
		head: Any = client._s3.head_object(Bucket=client.config.bucket, Key=key)
	except ClientError as exc:
		code = str(exc.response.get("Error", {}).get("Code", ""))
		if code in ("404", "NoSuchKey", "NotFound"):
			return None
		raise ProviderError("Spaces head failed", {"key": key, "error": str(exc)}) from exc
	except BotoCoreError as exc:
		raise ProviderError("Spaces head failed", {"key": key, "error": str(exc)}) from exc
	return int(head.get("ContentLength", 0))
