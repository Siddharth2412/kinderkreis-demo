#!/usr/bin/env bash
set -euo pipefail

echo "==> Updating apt and installing prerequisites"
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg ufw

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
sudo ufw --force enable
sudo ufw status verbose

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
