#!/usr/bin/env bash
# One-time provisioning for a blank Ubuntu 22.04/24.04 VM that will host
# this app and run a self-hosted GitHub Actions runner. Run as a normal
# sudo-capable user (not root), e.g.:
#   curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/scripts/setup-vm.sh | bash
# or copy it up and run `bash setup-vm.sh` after `scp`.
#
# What it does:
#   1. Installs Docker Engine + the Compose plugin (docker compose v2).
#   2. Adds the current user to the `docker` group.
#   3. Opens only SSH (22), HTTP (80), and HTTPS (443) publicly via ufw.
#      The backend API is never exposed directly — nginx (the frontend
#      container) reverse-proxies /api/ to it over the internal Docker
#      network (see frontend/nginx.conf), so no separate port needs
#      opening, here or in any cloud-level security group in front of this
#      VM. NOTE: if this VM sits behind a floating IP / cloud security
#      group (common on OpenStack, Hetzner Cloud, etc.), 443 needs opening
#      there too, separately from this ufw rule — ufw only controls the
#      VM's own OS firewall, not that outer layer.
#   4. Generates a self-signed TLS cert (once — skipped if it already
#      exists) at /etc/kinderkreis/ssl, bind-mounted into the frontend
#      container by docker-compose.prod.yml. No domain yet to get a real
#      Let's Encrypt certificate for; see README "Deploying to production"
#      for upgrading this once there is one.
#   5. Prints the next manual step: registering the GitHub Actions runner
#      (requires a short-lived token from the GitHub UI, so it can't be
#      scripted unattended).
set -euo pipefail

echo "==> Updating apt and installing prerequisites"
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg ufw openssl

echo "==> Installing Docker Engine + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  echo "    docker already installed, skipping"
fi

echo "==> Adding $USER to the docker group (log out/in — or 'newgrp docker' — for this to take effect)"
sudo usermod -aG docker "$USER"

echo "==> Configuring firewall (ufw)"
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose

echo "==> Generating self-signed TLS cert (skipped if already present)"
if [ ! -f /etc/kinderkreis/ssl/selfsigned.crt ]; then
  sudo mkdir -p /etc/kinderkreis/ssl
  sudo openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
    -keyout /etc/kinderkreis/ssl/selfsigned.key \
    -out /etc/kinderkreis/ssl/selfsigned.crt \
    -subj "/CN=kinderkreis-demo"
  # World-readable: nginx runs as its own user *inside* the container, whose
  # uid won't match anything on the host, so it needs "other" read access to
  # see these through the bind mount. Not a real secrecy concern for a
  # self-signed cert either way.
  sudo chmod 644 /etc/kinderkreis/ssl/selfsigned.key /etc/kinderkreis/ssl/selfsigned.crt
else
  echo "    /etc/kinderkreis/ssl/selfsigned.crt already exists, skipping"
fi

cat <<'EOF'

==> Docker + firewall are set up. Next: register the GitHub Actions runner.

This step needs a short-lived token from GitHub, so it isn't scripted here:

  1. On GitHub: repo -> Settings -> Actions -> Runners -> "New self-hosted
     runner" -> Linux/x64. GitHub shows you the exact download/config
     commands with the current version and a one-time token filled in.
  2. Run those commands on this VM, but when prompted for labels, add
     `kinderkreis-prod` (matches .github/workflows/deploy.yml's
     `runs-on: [self-hosted, linux, kinderkreis-prod]`), e.g.:

       ./config.sh --url https://github.com/<owner>/<repo> \
         --token <TOKEN> --labels kinderkreis-prod

  3. Install it as a service so it survives reboots and keeps running:

       sudo ./svc.sh install
       sudo ./svc.sh start

  4. Log out and back in (or run `newgrp docker`) so the runner's shell
     picks up docker-group membership before the first deploy runs.

Then add these repo secrets (Settings -> Secrets and variables -> Actions):
  SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, FROM_EMAIL, FROM_NAME,
  ADMIN_USERNAME, ADMIN_PASSWORD, ALLOWED_ORIGINS (= http://<VM_PUBLIC_IP>)

Push to main (or run the workflow manually) and it will build + deploy.
EOF
