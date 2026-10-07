"""Typed errors that map 1:1 to the contract's `ErrorCode` and HTTP status.

API handlers never build error bodies by hand: they raise one of these and the API layer
(A1.4) renders `{ "error": { code, message, details } }` with `http_status`.
"""

from __future__ import annotations

from typing import Any

from infra_control.core.enums import Capability


class InfraError(Exception):
	code: str = "internal_error"
	http_status: int = 500

	def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
		super().__init__(message)
		self.message = message
		self.details: dict[str, Any] = details or {}

	def as_payload(self) -> dict[str, Any]:
		return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class ValidationError(InfraError):
	code = "validation_error"
	http_status = 400


class ConfirmationRequired(InfraError):
	code = "confirmation_required"
	http_status = 400

	def __init__(self, expected: str, message: str | None = None) -> None:
		super().__init__(message or "Confirmation required", {"expected": expected})


class InvalidCursor(InfraError):
	code = "invalid_cursor"
	http_status = 400


class PermissionDenied(InfraError):
	code = "permission_denied"
	http_status = 403


class NotFound(InfraError):
	code = "not_found"
	http_status = 404

	def __init__(self, doctype: str, name: str) -> None:
		super().__init__(f"{doctype} {name} not found", {"doctype": doctype, "name": name})


class NotSupported(InfraError):
	"""Plan section 4.3: capability check before every provider call (HTTP 409)."""

	code = "capability_missing"
	http_status = 409

	def __init__(self, capability: Capability | str, provider: str | None = None) -> None:
		cap = str(capability)
		where = f"Provider {provider}" if provider else "Provider"
		super().__init__(f"{where} lacks capability {cap}", {"capability": cap, "provider": provider})


class InvalidState(InfraError):
	code = "invalid_state"
	http_status = 409


class RateLimited(InfraError):
	code = "rate_limited"
	http_status = 429

	def __init__(self, retry_after: int, message: str = "Too many requests") -> None:
		super().__init__(message, {"retry_after": retry_after})
		self.retry_after = retry_after


class ProviderError(InfraError):
	code = "provider_error"
	http_status = 502


class InternalError(InfraError):
	code = "internal_error"
	http_status = 500


ERROR_CLASSES: tuple[type[InfraError], ...] = (
	ValidationError,
	PermissionDenied,
	NotFound,
	ConfirmationRequired,
	NotSupported,
	InvalidState,
	InvalidCursor,
	RateLimited,
	ProviderError,
	InternalError,
)
