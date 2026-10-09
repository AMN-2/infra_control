"""Guard for `server.exec` (A3.9, the command runner): pure checks on an operator's command.

The command runs as the bench user on one server, as an audited job. The guard refuses the
handful of things that destroy a server or its data outright; everything else is the
operator's call, recorded with its output.
"""

from __future__ import annotations

import re

from infra_control.core.errors import ValidationError

MAX_COMMAND_LENGTH = 4000

# (pattern, reason) — matched case-insensitively against the whole command line.
DENYLIST: tuple[tuple[str, str], ...] = (
	(
		r"\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r)[a-z]*\s+(--[a-z-]+\s+)*(/|~|\$HOME|\*|\.)(\s|$)",
		"recursive delete of a root, home or working directory",
	),
	(r"\bmkfs(\.\w+)?\b", "filesystem creation"),
	(r"\bdd\s+.*\bof=/dev/", "raw write to a device"),
	(r">\s*/dev/(sd|vd|nvme|xvd)", "raw write to a device"),
	(r"\b(shutdown|poweroff|halt|reboot|init\s+[06])\b", "power control (use server.reboot)"),
	(r":\(\)\s*\{\s*:\|:&\s*\};:", "fork bomb"),
	(r"\bbench\s+drop-site\b", "site deletion"),
	(r"\bdrop\s+(database|schema)\b", "database deletion"),
	(r"\bchmod\s+(-R\s+)?[0-7]*777\s+/(\s|$)", "world-writable root"),
	(r"\buserdel\b|\bpasswd\s+root\b", "account changes"),
	(r"\biptables\s+-F\b|\bufw\s+disable\b", "firewall teardown"),
	(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba)?sh\b", "piping a download into a shell"),
)


def check_command(command: str) -> str:
	"""Return the trimmed command or raise ValidationError with the reason it is refused."""
	text = (command or "").strip()
	if not text:
		raise ValidationError("command is required", {"field": "command"})
	if len(text) > MAX_COMMAND_LENGTH:
		raise ValidationError(f"command is longer than {MAX_COMMAND_LENGTH} characters", {"field": "command"})
	if "\x00" in text:
		raise ValidationError("command contains a NUL byte", {"field": "command"})
	for pattern, reason in DENYLIST:
		if re.search(pattern, text, flags=re.IGNORECASE):
			raise ValidationError(f"command refused: {reason}", {"field": "command", "reason": reason})
	return text
