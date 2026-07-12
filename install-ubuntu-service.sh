#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="nourish"
APP_DIR="$(cd "${1:-$PWD}" && pwd)"
DOCKER_BIN="$(command -v docker || true)"

if [[ -z "$DOCKER_BIN" ]]; then
  echo "Docker is required. Install Docker Engine and the Docker Compose plugin first." >&2
  exit 1
fi

if ! "$DOCKER_BIN" compose version >/dev/null 2>&1; then
  echo "The Docker Compose plugin is required." >&2
  exit 1
fi

if [[ ! -f "$APP_DIR/docker-compose.yml" ]]; then
  echo "No docker-compose.yml found in $APP_DIR." >&2
  exit 1
fi

sudo tee "/etc/systemd/system/$SERVICE_NAME.service" >/dev/null <<EOF
[Unit]
Description=Nourish nutrition tracker
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$DOCKER_BIN compose -f $APP_DIR/docker-compose.yml up --remove-orphans
ExecStop=$DOCKER_BIN compose -f $APP_DIR/docker-compose.yml down
Restart=on-failure
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager
