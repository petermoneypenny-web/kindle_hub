# Kindle Trading Desk

A minimal black-and-white dashboard for the jailbroken Kindle Paperwhite 3. The landscape-first screen shows London and New York time, LSE/NYSE weekday session status, open trade count, and daily net P&L only. It polls once per minute to reduce e-ink flashing.

## QNAP deployment

The dashboard uses **host networking** because, on this QNAP, a bridge-networked container could not reach the Trading Desk V2 service through either the NAS LAN address or the Docker gateway. Host networking lets it request `http://127.0.0.1:5095/api/status` directly. The Compose file therefore intentionally has no `ports:` section; the app binds port 5000 on the NAS itself.

1. Stop the old clock container that uses port 5000. Keep it until the dashboard has been tested.
2. In this directory, run:

   ```sh
   docker compose up -d --build --force-recreate
   ```

3. Check `docker compose logs --tail=40` and open `http://192.168.0.217:5000` on a computer or Kindle. `/health` reports dashboard health; `/api/dashboard` returns the displayed data.

The service uses `restart: unless-stopped`, so it restarts after a NAS reboot unless deliberately stopped. Trading Hub V2's `/api/status` supplies `open_positions_count` and `net_daily_pnl` (USD). The dashboard does not make trading requests.

## Updating a QNAP without Git

This repository's Kindle deployment can be updated by downloading the ZIP for the current branch and extracting its root files over the existing deployment directory. For the active Arena branch, from the NAS shell:

```sh
cd /share/Container/kindle_hub
curl -fL 'https://github.com/petermoneypenny-web/kindle_hub/archive/refs/heads/arena/6df88ada-kindle-hub.zip' -o /tmp/kindle_hub.zip
unzip -o -j /tmp/kindle_hub.zip -d /share/Container/kindle_hub
docker compose up -d --build --force-recreate
```

This overwrites the app files and Compose file but leaves unrelated files in the directory alone. If `unzip` is not installed, download the branch ZIP on a computer and extract/upload the project files with QNAP File Station.

## Kindle display

Open `http://192.168.0.217:5000` in the Kindle's built-in browser and bookmark it. Rotate the Kindle to landscape using its screen-orientation control if available. The page fills the browser viewport; Kindle browser toolbars and the device sleep/screensaver are controlled by Kindle firmware/jailbreak settings, not by this web app. Use only a keep-awake or kiosk extension confirmed compatible with the device's firmware. The browser refreshes the data every 60 seconds; a five-minute page-refresh meta tag is a fallback if JavaScript pauses.

## Display details and limitations

- London uses `Europe/London`; New York uses `America/New_York`, with daylight-saving changes handled by IANA time zones.
- Regular weekday hours shown are LSE 08:00–16:30 UK time and NYSE 09:30–16:00 US Eastern time. Exchange holidays and early closes are not included in the open/closed badge.
- P&L is displayed in USD, using Trading Desk V2's `net_daily_pnl` field.
- The page uses plain HTML, CSS, and XMLHttpRequest for compatibility with older Kindle browsers; no JavaScript framework or build process is required.

## Local run

Requires Python 3.9+ and timezone data:

```sh
python app.py
```

Configure `TRADING_HUB_URL`, `TRADING_HUB_STATS_PATH`, `PORT`, and `STATS_CACHE_SECONDS` with environment variables if running outside the supplied QNAP Compose setup.
