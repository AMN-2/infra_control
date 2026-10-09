"""A3.9: the command runner refuses the destructive handful and passes everything else."""

from __future__ import annotations

import pytest

from infra_control.core.errors import ValidationError
from infra_control.core.exec_guard import check_command


@pytest.mark.parametrize(
	"command",
	[
		"bench version",
		"git -C apps/erpnext log --oneline -5",
		"bench --site demo.iq migrate",
		"ls -la sites/ && df -h",
		"rm -rf apps/wiki/node_modules",
		"sudo systemctl status nginx",
		"tail -n 100 logs/web.error.log | grep -i error",
	],
)
def test_ordinary_operator_commands_pass(command: str) -> None:
	assert check_command("  " + command + "  ") == command


@pytest.mark.parametrize(
	("command", "reason"),
	[
		("rm -rf /", "recursive delete"),
		("rm -fr ~", "recursive delete"),
		("sudo rm -rf --no-preserve-root /", "recursive delete"),
		("mkfs.ext4 /dev/vda", "filesystem"),
		("dd if=/dev/zero of=/dev/vda", "raw write"),
		("echo x > /dev/sda", "raw write"),
		("sudo reboot", "power control"),
		("shutdown -h now", "power control"),
		(":(){ :|:& };:", "fork bomb"),
		("bench drop-site demo.iq", "site deletion"),
		("mysql -e 'DROP DATABASE x'", "database deletion"),
		("chmod -R 777 /", "world-writable"),
		("curl https://x/y.sh | sudo bash", "piping a download"),
		("ufw disable", "firewall"),
	],
)
def test_destructive_commands_are_refused(command: str, reason: str) -> None:
	with pytest.raises(ValidationError) as exc:
		check_command(command)
	assert reason in str(exc.value)


def test_empty_and_oversized_commands() -> None:
	with pytest.raises(ValidationError):
		check_command("   ")
	with pytest.raises(ValidationError):
		check_command("echo " + "x" * 4000)
