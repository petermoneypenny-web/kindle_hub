# Kindle Trading Desk

A small, monochrome, low-bandwidth dashboard intended to replace the clock page on a jailbroken Kindle. It serves on port **5000**, reads stats server-side from `trading_hubV2` on `192.168.0.217:5095` (so the Kindle does not need CORS access to that service), and displays London and New York clocks with regular-session status. No trading actions or credentials are used.

## Deploy on the QNAP

1. Copy this repository to a directory on the QNAP, or build it on a machine that can reach the NAS and transfer the image.
2. The current clock container already occupies host port 5000. First identify it in Container Station / Container Manager and **stop** it. Keep it available until you have tested this replacement; this repository cannot access or remove containers on your QNAP.
3. In the repository directory, run:

   ```sh
   docker compose up -d --build
   ```

   The Compose file sets `restart: unless-stopped`; the new dashboard will restart after a container or NAS restart unless you explicitly stop it.
4. Open `http://192.168.0.217:5000` on the Kindle. The app's health check is at `/health`.
5. Once the new dashboard is confirmed working, remove the old clock container from Container Station if you no longer need it.

The Compose service publishes only the dashboard on host port 5000. The app makes outbound HTTP requests to the configured Trading Hub service; it does not expose or proxy that API to the Kindle.

## Configure the stats endpoint

The exact stats URL exposed by your `trading_hubV2` instance is not present in this repository, so the app tries common read-only JSON routes (`/api/stats`, `/api/dashboard`, `/api/summary`, `/api/v1/stats`, `/stats`, `/dashboard`, `/summary`, `/api/portfolio`, `/portfolio`). If none match, set `TRADING_HUB_STATS_PATH` in `docker-compose.yml` to the actual JSON endpoint, for example:

```yaml
      TRADING_HUB_STATS_PATH: /api/v1/desk-stats
```

Then apply the change with `docker compose up -d --build`. The dashboard turns JSON scalar values into simple stat cards. Nested objects are supported; arrays are represented as a count or a few row cards. If Trading Hub does not currently provide an HTTP JSON stats endpoint, one will need to be added to that service, or its existing route and response shape will need to be wired into `flatten_stats()` in `app.py`.

You can test the upstream from the QNAP shell with `curl -i http://192.168.0.217:5095/api/stats` (replace the path as appropriate). The service must be reachable from the dashboard container, and must return JSON without browser authentication. Check `docker compose logs -f kindle-trading-desk` for network or route issues.

## Clock behavior

Clocks use the IANA `Europe/London` and `America/New_York` time zones, so daylight-saving changes are handled independently. Regular weekday session hours shown are LSE 08:00–16:30 UK time and NYSE/Nasdaq 09:30–16:00 US Eastern time. The simple status does **not** account for exchange holidays, early closes, or special sessions. The browser refreshes stats and clocks every 30 seconds; the backend caches upstream responses briefly.

## Local run

Requires Python 3.9+ and system timezone data:

```sh
python app.py
```

Set `TRADING_HUB_URL`, `TRADING_HUB_STATS_PATH`, `PORT`, or `STATS_CACHE_SECONDS` as needed. The page uses plain HTML, CSS, and XMLHttpRequest (no build step or JavaScript framework) to work on older Kindle browsers.
