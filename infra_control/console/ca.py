"""SSH certificate authority for the web console (ADR 0007).

Like Frappe Cloud: managed servers trust one CA public key (`TrustedUserCAKeys`), and every
console session gets a fresh key pair signed into a certificate that is valid for minutes,
names the operator in its identity, and is deleted when the session ends. No long-lived key
is ever handed to a browser, and the server's auth log records who opened each session.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from infra_control.core.errors import InternalError

DEFAULT_CA_DIR = "~/.infra-control/ssh_ca"
CERT_VALIDITY = "+10m"
PRINCIPAL = "frappe"


def ca_dir() -> Path:
	return Path(os.path.expanduser(os.environ.get("INFRA_CONSOLE_CA_DIR", DEFAULT_CA_DIR)))


def _run(argv: list[str]) -> None:
	# argv is built by this module only (fixed ssh-keygen flags, paths under the CA directory).
	result = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)  # noqa: S603
	if result.returncode != 0:
		raise InternalError(f"{argv[0]} failed: {result.stderr.strip()[:300]}")


def ensure_ca(directory: Path | None = None) -> Path:
	"""Create the CA key pair once (ed25519, no passphrase, 0600) and return the private key path."""
	d = directory or ca_dir()
	d.mkdir(parents=True, exist_ok=True, mode=0o700)
	key = d / "ca"
	if not key.exists():
		_run(
			[
				"/usr/bin/ssh-keygen",
				"-q",
				"-t",
				"ed25519",
				"-N",
				"",
				"-C",
				"infra-control console CA",
				"-f",
				str(key),
			]
		)
		key.chmod(0o600)
	return key


def public_key(directory: Path | None = None) -> str:
	"""The CA public key line that managed servers trust."""
	return (ensure_ca(directory).with_suffix(".pub")).read_text().strip()


@dataclass(frozen=True)
class IssuedCertificate:
	key_path: Path
	cert_path: Path
	identity: str
	serial: int
	valid_for: str


def identity_for(user: str, server: str, now: float | None = None) -> str:
	"""Pure: the certificate identity (shows up in the server's auth log and `ssh-keygen -L`)."""
	stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now or time.time()))
	return f"console:{user}:{server}:{stamp}"


def sign_args(
	ca_key: Path,
	pub_key: Path,
	identity: str,
	serial: int,
	principal: str = PRINCIPAL,
	validity: str = CERT_VALIDITY,
) -> list[str]:
	"""Pure: the ssh-keygen invocation that turns an ephemeral public key into a user certificate."""
	return [
		"/usr/bin/ssh-keygen",
		"-q",
		"-s",
		str(ca_key),
		"-I",
		identity,
		"-n",
		principal,
		"-V",
		validity,
		"-z",
		str(serial),
		str(pub_key),
	]


def issue(
	user: str, server: str, work_dir: Path, *, directory: Path | None = None, validity: str = CERT_VALIDITY
) -> IssuedCertificate:
	"""Fresh key pair + certificate for one session, written under `work_dir` (0600)."""
	ca_key = ensure_ca(directory)
	work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
	serial = secrets.randbits(63)
	identity = identity_for(user, server)
	key = work_dir / f"session-{serial:x}"
	_run(["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", identity, "-f", str(key)])
	key.chmod(0o600)
	_run(sign_args(ca_key, key.with_suffix(".pub"), identity, serial, validity=validity))
	cert = Path(str(key) + "-cert.pub")
	if not cert.exists():
		raise InternalError("ssh-keygen produced no certificate")
	return IssuedCertificate(
		key_path=key, cert_path=cert, identity=identity, serial=serial, valid_for=validity
	)
