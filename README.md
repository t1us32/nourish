# Nourish

## Docker deployment

1. Install Docker Engine with the Docker Compose plugin on the server.
2. Clone this repository and change into its directory.
3. Optionally export `FDC_API_KEY` for USDA text search.
4. Run `docker compose up -d --build`.

Open `https://resonmusic.pp.ua` for the deployed VPS stack. The API is only available through the web container at `/api`.

## HTTPS

The Compose stack serves `https://resonmusic.pp.ua` through Caddy on port `443`. Point that domain's DNS A record to this server and allow inbound TCP port `443`. Port `80` remains untouched because it is used by another service.

## Ubuntu system service

From the checked-out repository, run:

```bash
chmod +x install-ubuntu-service.sh
./install-ubuntu-service.sh /absolute/path/to/nourish
```

The installer uses `sudo` to create and start `nourish.service`. Manage it with `sudo systemctl status|restart|stop nourish`.

To provide the optional USDA key to the service, create `/etc/systemd/system/nourish.service.d/environment.conf` containing:

```ini
[Service]
Environment=FDC_API_KEY=your-key
```

Then run `sudo systemctl daemon-reload && sudo systemctl restart nourish`.
