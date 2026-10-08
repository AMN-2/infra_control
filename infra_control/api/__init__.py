"""Whitelisted endpoints only, thin (plan section 8). Conventions (docs/QUESTIONS.md Q5):

- The payload is written directly into `frappe.local.response`, so bodies have no `message`
  wrapper; `http_status_code` carries the status.
- Every `InfraError` becomes `{ "error": { code, message, details } }` with its HTTP status.
  Unexpected exceptions become `internal_error` (500) after being logged with a traceback.
- Handlers never touch providers; mutations go through `infra_control.job_engine.engine`.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from typing import Any, ParamSpec

import frappe

from infra_control.core.errors import InfraError, InternalError, RateLimited, ValidationError
from infra_control.core.permissions import INFRA_VIEWER, require_role
from infra_control.job_engine.masking import mask_secrets

P = ParamSpec("P")
Handler = Callable[P, dict[str, Any]]

# Keys Frappe seeds into the response that must not leak into contract bodies.
_FRAPPE_RESPONSE_KEYS = ("docs", "message", "exc", "exc_type", "_server_messages")


def api(
	*, methods: Iterable[str] = ("GET",), role: str = INFRA_VIEWER
) -> Callable[[Handler[P]], Callable[P, None]]:
	"""Decorator: whitelist + role check + contract-shaped success and error bodies."""

	def decorate(fn: Handler[P]) -> Callable[P, None]:
		@functools.wraps(fn)
		def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
			response = frappe.local.response
			for key in _FRAPPE_RESPONSE_KEYS:
				response.pop(key, None)
			try:
				require_role(role)
				payload = fn(*args, **kwargs)
				response.update(payload)
				response["http_status_code"] = 200
			except InfraError as err:
				frappe.db.rollback()
				_write_error(response, err)
			except Exception as exc:  # the contract promises an envelope for every failure
				frappe.db.rollback()
				frappe.log_error(title=f"infra_control.api {fn.__name__}", message=frappe.get_traceback())
				_write_error(response, InternalError(mask_secrets(str(exc)) or "Internal error"))

		whitelisted: Callable[P, None] = frappe.whitelist(methods=list(methods))(wrapper)
		# Frappe wraps the function with request-time argument validation; tests call `.handler`.
		whitelisted.handler = wrapper  # type: ignore[attr-defined]
		return whitelisted

	return decorate


def _write_error(response: Any, err: InfraError) -> None:
	response.update(err.as_payload())
	response["http_status_code"] = err.http_status
	if isinstance(err, RateLimited):
		frappe.local.response_headers = getattr(frappe.local, "response_headers", None) or {}
		frappe.local.response_headers["Retry-After"] = str(err.retry_after)


# ----- parameter helpers ------------------------------------------------------------------
def enum_param(name: str, value: Any, allowed: Iterable[str]) -> str | None:
	if value in (None, ""):
		return None
	allowed = list(allowed)
	if value not in allowed:
		raise ValidationError(f"{name} must be one of {', '.join(allowed)}", {"field": name})
	return str(value)


def int_param(name: str, value: Any, *, default: int, minimum: int, maximum: int) -> int:
	if value in (None, ""):
		return default
	try:
		out = int(value)
	except (TypeError, ValueError):
		raise ValidationError(f"{name} must be an integer", {"field": name}) from None
	if not minimum <= out <= maximum:
		raise ValidationError(f"{name} must be between {minimum} and {maximum}", {"field": name})
	return out


def str_param(name: str, value: Any, *, required: bool = False) -> str | None:
	if value in (None, ""):
		if required:
			raise ValidationError(f"{name} is required", {"field": name})
		return None
	return str(value)


def bool_param(name: str, value: Any, *, default: bool) -> bool:
	if value in (None, ""):
		return default
	if isinstance(value, bool):
		return value
	if isinstance(value, int):
		return bool(value)
	token = str(value).strip().lower()
	if token in ("1", "true", "yes", "on"):
		return True
	if token in ("0", "false", "no", "off"):
		return False
	raise ValidationError(f"{name} must be a boolean", {"field": name})


def list_param(name: str, value: Any) -> list[Any]:
	if value in (None, ""):
		return []
	if isinstance(value, str):
		import json

		try:
			value = json.loads(value)
		except ValueError:
			raise ValidationError(f"{name} must be a JSON array", {"field": name}) from None
	if not isinstance(value, list):
		raise ValidationError(f"{name} must be an array", {"field": name})
	return value


def dict_param(name: str, value: Any) -> dict[str, Any]:
	if value in (None, ""):
		return {}
	if isinstance(value, str):
		import json

		try:
			value = json.loads(value)
		except ValueError:
			raise ValidationError(f"{name} must be a JSON object", {"field": name}) from None
	if not isinstance(value, dict):
		raise ValidationError(f"{name} must be an object", {"field": name})
	return value
