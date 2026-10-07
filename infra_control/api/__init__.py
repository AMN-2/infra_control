"""Whitelisted REST endpoints: `/api/method/infra_control.api.<module>.<fn>`.

Handlers are thin. They validate input, check permissions and capabilities, write the
audit log and delegate to the job engine or read models. They never call a provider,
DigitalOcean, Press or SSH directly (plan section 3, core rule).
"""
