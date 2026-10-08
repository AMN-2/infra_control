"""Alert notifiers (A3.2): Telegram and email. Message formatting is pure; sending is isolated
so a failed channel never breaks the alert engine (the Alert is already recorded; a delivery
failure is logged).

Telegram uses the Bot API with the bot token and chat id from `Infra Settings`; the HTTP call
has a timeout and bounded retries. Email uses Frappe's `sendmail`.
"""

from __future__ import annotations

import time
from typing import Any

import frappe
import requests

from infra_control.core.enums import AlertChannel, AlertStatus, Severity

TELEGRAM_API = "https://api.telegram.org"
TIMEOUT_SECONDS = 15.0
MAX_ATTEMPTS = 3

SEVERITY_MARK = {Severity.INFO: "ℹ️", Severity.WARNING: "⚠️", Severity.CRITICAL: "\U0001f534"}  # noqa: RUF001


def format_message(alert: dict[str, Any], status: AlertStatus) -> str:
	"""One human line for a fired or resolved alert. Plain text (no secrets)."""
	mark = SEVERITY_MARK.get(Severity(str(alert["severity"])), "")
	verb = "RESOLVED" if status is AlertStatus.RESOLVED else str(alert["severity"]).upper()
	target = f"{alert['target_doctype']} {alert['target_name']}"
	head = f"{mark} [{verb}] {alert.get('rule_title') or alert['rule']}"
	return f"{head}\n{target}\n{alert.get('message') or ''}".strip()


def notify(alert: dict[str, Any], channels: list[str], status: AlertStatus) -> dict[str, bool]:
	"""Send to each channel. Returns {channel: delivered}. Never raises."""
	text = format_message(alert, status)
	out: dict[str, bool] = {}
	for channel in channels:
		try:
			if channel == AlertChannel.TELEGRAM:
				out[channel] = _telegram(text)
			elif channel == AlertChannel.EMAIL:
				out[channel] = _email(alert, text, status)
			else:
				out[channel] = False
		except Exception:
			frappe.log_error(title=f"alert {channel} notify failed", message=frappe.get_traceback())
			out[channel] = False
	return out


def _settings() -> Any:
	return frappe.get_single("Infra Settings")


def _telegram(text: str) -> bool:
	settings = _settings()
	token = settings.get_password("telegram_bot_token") if settings.telegram_bot_token else None
	chat_id = settings.telegram_chat_id
	if not token or not chat_id:
		return False  # not configured; the Alert is still recorded
	url = f"{TELEGRAM_API}/bot{token}/sendMessage"
	for attempt in range(1, MAX_ATTEMPTS + 1):
		try:
			resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=TIMEOUT_SECONDS)
		except requests.RequestException:
			if attempt == MAX_ATTEMPTS:
				raise
			time.sleep(attempt)
			continue
		if resp.status_code < 500:
			return bool(resp.ok)
		time.sleep(attempt)
	return False


def _email(alert: dict[str, Any], text: str, status: AlertStatus) -> bool:
	recipients = _recipients()
	if not recipients:
		return False
	subject = f"[infra] {str(alert['severity']).upper()}: {alert.get('rule_title') or alert['rule']}"
	frappe.sendmail(recipients=recipients, subject=subject, message=text.replace("\n", "<br>"), now=True)
	return True


def _recipients() -> list[str]:
	"""Infra Admins with an email address receive alert email."""
	admins = frappe.get_all("Has Role", filters={"role": "Infra Admin", "parenttype": "User"}, pluck="parent")
	emails = [
		e
		for e in frappe.get_all("User", filters={"name": ["in", admins], "enabled": 1}, pluck="email")
		if e and "@" in e
	]
	return emails
