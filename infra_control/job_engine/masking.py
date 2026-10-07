"""`mask_secrets()`: every byte of job output passes through here before storage or emission.

Two layers: known secret *values* (provider tokens, write-only params) are replaced wherever they
appear, and well-known secret *shapes* (tokens, passwords in key=value form, Authorization
headers, private keys, credentials in URLs) are replaced even when the value is unknown.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

MASK = "********"
MIN_SECRET_LEN = 6

_SHAPES: tuple[re.Pattern[str], ...] = (
	re.compile(r"dop_v1_[0-9a-f]{64}"),  # DigitalOcean personal access token
	re.compile(r"(?i)\b(authorization)\s*:\s*(token|bearer|basic)\s+\S+", re.ASCII),
	re.compile(r"(?i)\b(x-press-team|x-frappe-csrf-token)\s*:\s*\S+"),
	re.compile(
		r"(?i)\b([a-z0-9_\-]*(password|passwd|pwd|secret|token|api_key|apikey|private_key)[a-z0-9_\-]*)\s*([=:])\s*(\"[^\"]*\"|'[^']*'|\S+)"
	),
	re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
	re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^/\s:@]+):([^@\s/]+)@"),  # scheme://user:pass@host
)

_KEEP_KEY = re.compile(
	r"(?i)^([a-z0-9_\-]*(password|passwd|pwd|secret|token|api_key|apikey|private_key)[a-z0-9_\-]*)(\s*[=:]\s*)"
)


def _mask_shape(match: re.Match[str]) -> str:
	text = match.group(0)
	key = _KEEP_KEY.match(text)
	if key:
		return f"{key.group(1)}{key.group(3)}{MASK}"
	if text.lower().startswith("authorization"):
		head = text.split(None, 2)
		return f"{head[0]} {head[1]} {MASK}" if len(head) == 3 else f"{head[0]} {MASK}"
	if "://" in text and text.endswith("@"):
		return f"{match.group(1)}:{MASK}@"
	return MASK


def mask_secrets(text: str, secrets: Iterable[str] = ()) -> str:
	"""Return `text` with known secret values and secret-shaped substrings replaced by `********`."""
	if not text:
		return text
	for secret in sorted({s for s in secrets if s and len(s) >= MIN_SECRET_LEN}, key=len, reverse=True):
		text = text.replace(secret, MASK)
	for pattern in _SHAPES:
		text = pattern.sub(_mask_shape, text)
	return text


def secret_values(params: dict[str, Any] | None, schema: dict[str, Any] | None) -> list[str]:
	"""Values of `params` whose schema property is `writeOnly` or `format: password`."""
	if not params or not schema:
		return []
	props = schema.get("properties", {}) if isinstance(schema, dict) else {}
	out: list[str] = []
	for key, value in params.items():
		prop = props.get(key, {})
		if isinstance(value, str) and (prop.get("writeOnly") or prop.get("format") == "password"):
			out.append(value)
	return out


def mask_params(params: dict[str, Any] | None, schema: dict[str, Any] | None) -> dict[str, Any]:
	"""Copy of `params` with write-only / password properties replaced by `********` (stored on the job)."""
	if not params:
		return {}
	props = schema.get("properties", {}) if isinstance(schema, dict) else {}
	return {
		k: (
			MASK
			if isinstance(v, str)
			and (props.get(k, {}).get("writeOnly") or props.get(k, {}).get("format") == "password")
			else v
		)
		for k, v in params.items()
	}
