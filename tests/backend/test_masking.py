"""Security requirement 4: no secret in job output or logs, with seeded fake secrets."""

from __future__ import annotations

import pytest

from infra_control.job_engine.masking import MASK, mask_params, mask_secrets, secret_values

FAKE_DO_TOKEN = "dop_v1_" + "ab12" * 16
FAKE_PASSWORD = "S3cr3t-Passw0rd!"
SCHEMA = {
	"properties": {
		"admin_password": {"type": "string", "format": "password", "writeOnly": True},
		"domain": {"type": "string"},
	}
}


@pytest.mark.parametrize(
	"text",
	[
		f"curl -H 'Authorization: Bearer {FAKE_DO_TOKEN}' https://api.digitalocean.com",
		f"token={FAKE_DO_TOKEN}",
		f"DO_TOKEN: {FAKE_DO_TOKEN}",
		f"mysql -u root -p{FAKE_PASSWORD}",
		f'{{"password": "{FAKE_PASSWORD}"}}',
		f"admin_password={FAKE_PASSWORD}",
		f"https://user:{FAKE_PASSWORD}@db.internal/x",
		"-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXkt\n-----END OPENSSH PRIVATE KEY-----",
		"X-Press-Team: team-abc",
		"api_key = 'abcdef0123456789'",
	],
)
def test_seeded_secrets_never_survive(text: str) -> None:
	masked = mask_secrets(text, [FAKE_DO_TOKEN, FAKE_PASSWORD])
	for secret in (FAKE_DO_TOKEN, FAKE_PASSWORD, "b3BlbnNzaC1rZXkt", "team-abc", "abcdef0123456789"):
		assert secret not in masked, masked
	assert MASK in masked


def test_keys_are_kept_and_values_replaced() -> None:
	assert mask_secrets("db_password=hunter22 host=db") == "db_password=********  host=db".replace("  ", " ")
	assert mask_secrets("Authorization: token key:secret") == "Authorization: token ********"
	assert mask_secrets("https://u:p@h/") == "https://u:********@h/"


def test_unknown_shapes_untouched_and_short_values_ignored() -> None:
	text = "TASK [base : Create frappe user] changed: [app-03]"
	assert mask_secrets(text, ["ab"]) == text
	assert mask_secrets("") == ""


def test_known_values_replaced_before_shapes_even_without_a_key() -> None:
	assert mask_secrets(f"log line {FAKE_PASSWORD} end", [FAKE_PASSWORD]) == f"log line {MASK} end"


def test_secret_values_and_mask_params_from_schema() -> None:
	params = {"admin_password": FAKE_PASSWORD, "domain": "erp.client-d.iq"}
	assert secret_values(params, SCHEMA) == [FAKE_PASSWORD]
	assert mask_params(params, SCHEMA) == {"admin_password": MASK, "domain": "erp.client-d.iq"}
	assert mask_params(None, SCHEMA) == {}
	assert secret_values(params, None) == []
