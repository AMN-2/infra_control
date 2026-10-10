#!/usr/bin/env bash
# Prepare an EXISTING DigitalOcean server so the controller can manage it. Run as root ON THAT SERVER:
#
#   sudo CONTROLLER_PUBKEY='ssh-ed25519 AAAA... infra-control@ops.example.com' \
#        CONTROLLER_IP=203.0.113.10 ./onboard-server.sh
#
# Mirrors what cloud_init.yaml does for servers the controller provisions itself
# (infra_control/providers/digitalocean/cloud_init.yaml): a `frappe` sudo user with the
# controller's key, python3 for Ansible, key-only SSH, no root login. It does NOT touch an
# existing bench, nginx or MariaDB. Idempotent.
#
# Afterwards, in DigitalOcean (docs/runbooks/production_install.md, section 4):
#   tag the droplet `infra-control` and `role:all`, attach it to the `infra-control-managed`
#   firewall (SSH only from CONTROLLER_IP), then run inventory.sync and server.trust_ca.
set -euo pipefail
: "${CONTROLLER_PUBKEY:?the controller's ~/.ssh/id_ed25519.pub line}"
: "${CONTROLLER_IP:?the controller's public IP}"
SSH_USER=${SSH_USER:-frappe}
KEEP_SSH_FROM=${KEEP_SSH_FROM:-}   # optional extra CIDR allowed to SSH (your office) when ufw is managed here
MANAGE_UFW=${MANAGE_UFW:-0}        # 1 = restrict port 22 with ufw too (the DO firewall normally does this)
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 2; }

export DEBIAN_FRONTEND=noninteractive
apt-get update -q >/dev/null && apt-get install -y -q python3 python3-apt sudo >/dev/null

id "$SSH_USER" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$SSH_USER"
usermod -aG sudo "$SSH_USER"
echo "$SSH_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-infra-control && chmod 440 /etc/sudoers.d/90-infra-control
install -d -m 700 -o "$SSH_USER" -g "$SSH_USER" "/home/$SSH_USER/.ssh"
touch "/home/$SSH_USER/.ssh/authorized_keys"
grep -qF "$CONTROLLER_PUBKEY" "/home/$SSH_USER/.ssh/authorized_keys" || echo "$CONTROLLER_PUBKEY" >> "/home/$SSH_USER/.ssh/authorized_keys"
chown "$SSH_USER:$SSH_USER" "/home/$SSH_USER/.ssh/authorized_keys" && chmod 600 "/home/$SSH_USER/.ssh/authorized_keys"

cat > /etc/ssh/sshd_config.d/90-infra-control.conf <<'SSHD'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
X11Forwarding no
SSHD
sshd -t && { systemctl restart ssh 2>/dev/null || systemctl restart sshd; }

if [ "$MANAGE_UFW" = 1 ]; then
	apt-get install -y -q ufw >/dev/null
	ufw allow from "$CONTROLLER_IP" to any port 22 proto tcp >/dev/null
	[ -n "$KEEP_SSH_FROM" ] && ufw allow from "$KEEP_SSH_FROM" to any port 22 proto tcp >/dev/null
	ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
	ufw --force enable >/dev/null
fi
touch /var/lib/infra-control-onboarded

cat <<DONE
onboarded: user $SSH_USER has the controller key; root login and passwords are off.
Now in DigitalOcean: tag this droplet "infra-control" + "role:all", attach the firewall
"infra-control-managed" (created by the controller on its first provision, or by hand:
SSH from $CONTROLLER_IP/32 only, HTTP/HTTPS from anywhere), then on the controller run
inventory.sync for the account and server.trust_ca on the new Server record.
DONE
