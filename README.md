# Nourish

## Docker deployment

1. Install Docker Engine with the Docker Compose plugin on the server.
2. Clone this repository and change into its directory.
3. Optionally export `FDC_API_KEY` for USDA text search and `NOURISH_PORT` to use a port other than `8080`.
4. Run `docker compose up -d --build`.

Open `http://SERVER_IP:8080`. The API is only available through the web container at `/api`.

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
