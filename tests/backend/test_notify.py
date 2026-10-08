"""A3.2: the Telegram notifier (mocked HTTP) and that a failing channel never raises."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import responses

from infra_control.core.enums import AlertStatus
from infra_control.monitoring import notify

ALERT = {
	"rule": "RULE-1",
	"rule_title": "Disk high",
	"severity": "critical",
	"target_doctype": "Server",
	"target_name": "SRV-0001",
	"message": "disk 92%",
}


class _Settings:
	def __init__(self, token: str | None, chat: str | None) -> None:
		self.telegram_bot_token = token
		self.telegram_chat_id = chat

	def get_password(self, field: str) -> Any:
		return self.telegram_bot_token


@pytest.fixture
def frappe_stub(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
	logged: list[str] = []
	stub = SimpleNamespace(
		_single=_Settings("bot-token-123", "chat-9"),
		get_single=lambda dt: stub._single,
		log_error=lambda title="", message="": logged.append(title),
		logged=logged,
	)
	monkeypatch.setattr(notify, "frappe", stub)
	return stub


@responses.activate
def test_telegram_sends_the_message(frappe_stub: SimpleNamespace) -> None:
	responses.post("https://api.telegram.org/botbot-token-123/sendMessage", json={"ok": True})
	result = notify.notify(ALERT, ["telegram"], AlertStatus.FIRING)
	assert result == {"telegram": True}
	body = responses.calls[0].request.body
	assert body is not None and b"SRV-0001" in body and b"chat-9" in body


@responses.activate
def test_telegram_retries_5xx_then_fails_without_raising(frappe_stub: SimpleNamespace) -> None:
	import infra_control.monitoring.notify as n

	monkey_sleep = []
	n.time.sleep = lambda s: monkey_sleep.append(s)  # type: ignore[assignment]
	for _ in range(3):
		responses.post("https://api.telegram.org/botbot-token-123/sendMessage", status=503)
	result = notify.notify(ALERT, ["telegram"], AlertStatus.FIRING)
	assert result == {"telegram": False}
	assert len(responses.calls) == 3


def test_unconfigured_telegram_is_not_a_failure_and_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
	stub = SimpleNamespace(
		get_single=lambda dt: _Settings(None, None),
		log_error=lambda title="", message="": None,
	)
	monkeypatch.setattr(notify, "frappe", stub)
	assert notify.notify(ALERT, ["telegram"], AlertStatus.FIRING) == {"telegram": False}


def test_an_exploding_channel_is_logged_not_raised(monkeypatch: pytest.MonkeyPatch) -> None:
	logged: list[str] = []
	stub = SimpleNamespace(
		get_single=lambda dt: (_ for _ in ()).throw(RuntimeError("boom")),
		log_error=lambda title="", message="": logged.append(title),
		get_traceback=lambda: "tb",
	)
	monkeypatch.setattr(notify, "frappe", stub)
	assert notify.notify(ALERT, ["telegram"], AlertStatus.FIRING) == {"telegram": False}
	assert logged and "telegram" in logged[0]
