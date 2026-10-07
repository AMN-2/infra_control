"""Roles (plan section 5) and the checks API handlers run before touching anything."""

from __future__ import annotations

from collections.abc import Iterable

import frappe

from infra_control.core.enums import Risk
from infra_control.core.errors import PermissionDenied

INFRA_ADMIN = "Infra Admin"
INFRA_OPERATOR = "Infra Operator"
INFRA_VIEWER = "Infra Viewer"
ROLES: tuple[str, ...] = (INFRA_ADMIN, INFRA_OPERATOR, INFRA_VIEWER)

# The least role that may run a playbook of this risk.
RISK_ROLE: dict[Risk, str] = {
	Risk.LOW: INFRA_OPERATOR,
	Risk.MEDIUM: INFRA_OPERATOR,
	Risk.HIGH: INFRA_ADMIN,
}

# Role hierarchy: a role implies every role to its right.
_IMPLIES: dict[str, frozenset[str]] = {
	INFRA_ADMIN: frozenset(ROLES),
	INFRA_OPERATOR: frozenset({INFRA_OPERATOR, INFRA_VIEWER}),
	INFRA_VIEWER: frozenset({INFRA_VIEWER}),
}


def effective_roles(roles: Iterable[str]) -> frozenset[str]:
	"""Infra roles the given role list grants, honouring the hierarchy. Administrator gets all."""
	out: set[str] = set()
	for role in roles:
		if role == "Administrator":
			return frozenset(ROLES)
		out |= _IMPLIES.get(role, frozenset())
	return frozenset(out)


def user_roles(user: str | None = None) -> frozenset[str]:
	user = user or frappe.session.user
	roles: list[str] = list(frappe.get_roles(user))
	if user == "Administrator":
		roles.append("Administrator")
	return effective_roles(roles)


def has_role(role: str, user: str | None = None) -> bool:
	return role in user_roles(user)


def require_role(role: str, user: str | None = None) -> None:
	"""Raise `PermissionDenied` (403, `permission_denied`) unless the user holds `role` or higher."""
	held = user_roles(user)
	if role not in held:
		current = next((r for r in ROLES if r in held), "no Infra role")
		raise PermissionDenied(
			f"Role {current} cannot do this; {role} required",
			{"role": current, "required": role},
		)


def require_risk(risk: Risk | str, user: str | None = None) -> None:
	"""High-risk playbooks need Infra Admin; low and medium need Infra Operator (plan section 5)."""
	require_role(RISK_ROLE[Risk(risk)], user)
