#!/usr/bin/env python3
"""Kindle-friendly e-ink dashboard for Trading Hub."""

import json
import os
import threading
import time
from datetime import datetime, time as wall_time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
UPSTREAM = os.environ.get("TRADING_HUB_URL", "http://192.168.0.217:5095").rstrip("/")
CUSTOM_PATH = os.environ.get("TRADING_HUB_STATS_PATH", "").strip()
CACHE_SECONDS = max(0, int(os.environ.get("STATS_CACHE_SECONDS", "15")))

# Common read-only status/summary routes. Set TRADING_HUB_STATS_PATH to the
# correct route in your trading_hubV2 deployment to avoid route discovery.
CANDIDATE_PATHS = [
    "/api/stats", "/api/dashboard", "/api/summary", "/api/v1/stats",
    "/stats", "/dashboard", "/summary", "/api/portfolio", "/portfolio",
]

_cache = {"at": 0.0, "data": None}
_cache_lock = threading.Lock()


def market_clock(zone_name, opening, closing):
    now = datetime.now(ZoneInfo(zone_name))
    local_time = now.time().replace(tzinfo=None)
    weekday = now.weekday() < 5
    opened = weekday and wall_time.fromisoformat(opening) <= local_time < wall_time.fromisoformat(closing)
    return {
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%a %d %b %Y"),
        "zone": zone_name,
        "status": "OPEN" if opened else "CLOSED",
        "hours": opening + "–" + closing,
    }


def _request_json(path):
    request = Request(UPSTREAM + path, headers={"Accept": "application/json", "User-Agent": "KindleTradingDesk/1.0"})
    with urlopen(request, timeout=0.75) as response:
        content_type = response.headers.get("Content-Type", "")
        body = response.read(2_000_000)
        if "json" not in content_type.lower() and not body.lstrip().startswith((b"{", b"[")):
            raise ValueError("Endpoint did not return JSON")
        return json.loads(body.decode("utf-8"))


def fetch_stats():
    with _cache_lock:
        if _cache["data"] is not None and time.time() - _cache["at"] < CACHE_SECONDS:
            return _cache["data"]

    paths = [CUSTOM_PATH] if CUSTOM_PATH else CANDIDATE_PATHS
    result = {"ok": False, "source": UPSTREAM, "path": "", "stats": [], "error": "No stats endpoint found"}
    errors = []
    for path in paths:
        if not path.startswith("/"):
            path = "/" + path
        try:
            payload = _request_json(path)
            if isinstance(payload, dict) and payload.get("ok") is False and len(payload) <= 3:
                errors.append(path + " returned an error")
                continue
            stats = flatten_stats(payload)
            result = {
                "ok": True,
                "source": UPSTREAM,
                "path": path,
                "stats": stats,
                "error": "" if stats else "The endpoint returned JSON, but no simple stats fields were found.",
            }
            break
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError) as exc:
            errors.append(path + ": " + str(exc))
    if not result["ok"]:
        result["error"] = "Could not load trading stats. " + (errors[-1] if errors else "Check the upstream URL and stats path.")
    with _cache_lock:
        _cache.update(at=time.time(), data=result)
    return result


def flatten_stats(payload):
    """Turn top-level/nested scalar JSON values into compact dashboard cards."""
    ignored = {"id", "uuid", "token", "secret", "password", "timestamp", "updated_at", "created_at", "api_key", "apikey", "credential", "credentials", "authorization", "auth"}
    values = []

    def visit(value, labels, depth=0):
        if len(values) >= 18 or depth > 3:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key)
                if key_text.lower() in ignored:
                    continue
                visit(child, labels + [key_text], depth + 1)
        elif isinstance(value, list):
            if value and all(not isinstance(item, (dict, list)) for item in value):
                values.append((" ".join(labels), str(len(value)) + " items"))
            elif value and isinstance(value[0], dict):
                for index, item in enumerate(value[:4]):
                    visit(item, labels + [str(index + 1)], depth + 1)
        elif value is not None:
            label = " / ".join(labels).replace("_", " ").replace("-", " ").strip()
            if label:
                if isinstance(value, float):
                    display = ("{:.2f}".format(value)).rstrip("0").rstrip(".")
                elif isinstance(value, bool):
                    display = "Yes" if value else "No"
                else:
                    display = str(value)
                if len(display) > 70:
                    display = display[:67] + "..."
                values.append((label, display))

    visit(payload, [])
    return values


def dashboard_data():
    return {
        "uk": market_clock("Europe/London", "08:00", "16:30"),
        "us": market_clock("America/New_York", "09:30", "16:00"),
        "stats": fetch_stats(),
        "refreshed": datetime.now().strftime("%H:%M:%S"),
    }


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300"><title>Trading Desk</title>
<style>
*{box-sizing:border-box} body{margin:0;background:#fff;color:#111;font-family:Arial,Helvetica,sans-serif;font-size:18px;line-height:1.35}
.wrap{max-width:1000px;margin:0 auto;padding:20px 24px}.top{display:flex;justify-content:space-between;align-items:baseline;border-bottom:3px solid #111;padding-bottom:10px}
h1{font-size:30px;letter-spacing:1px;text-transform:uppercase;margin:0}.updated{font-size:14px;color:#444}
.clocks{display:flex;gap:18px;margin:18px 0}.clock{flex:1;border:2px solid #111;padding:12px 16px;min-width:0}.clock-head{display:flex;justify-content:space-between;align-items:center;text-transform:uppercase;font-weight:bold;font-size:15px}.clock-time{font-size:38px;font-weight:bold;font-variant-numeric:tabular-nums;line-height:1.15;margin:5px 0}.clock-date{font-size:15px}.badge{border:1px solid #111;border-radius:2px;padding:2px 7px;font-size:12px}.section{display:flex;justify-content:space-between;align-items:baseline;border-bottom:2px solid #111;margin:22px 0 12px;padding-bottom:6px}.section h2{font-size:20px;text-transform:uppercase;margin:0}.source{font-size:12px;color:#444;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.card{border:1px solid #555;padding:10px 12px;min-height:76px;overflow:hidden}.label{text-transform:uppercase;color:#444;font-size:12px;letter-spacing:.4px;overflow-wrap:anywhere}.value{font-size:24px;font-weight:bold;margin-top:4px;overflow-wrap:anywhere}.message{border:1px dashed #555;padding:12px;margin:10px 0}.foot{font-size:12px;color:#444;margin-top:20px;border-top:1px solid #999;padding-top:8px}
@media(max-width:600px){.wrap{padding:12px}.clocks{gap:8px}.clock{padding:9px}.clock-time{font-size:29px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.top{align-items:flex-start;display:block}.updated{margin-top:4px}}
</style></head><body><div class="wrap">
<div class="top"><h1>Trading Desk</h1><div class="updated">Updated <span id="updated">—</span></div></div>
<div class="clocks">
<section class="clock"><div class="clock-head"><span>London · UK</span><span class="badge" id="uk-status">—</span></div><div class="clock-time" id="uk-time">--:--:--</div><div class="clock-date" id="uk-date">Loading…</div><div class="clock-date">LSE regular hours <span id="uk-hours">08:00–16:30</span></div></section>
<section class="clock"><div class="clock-head"><span>New York · US</span><span class="badge" id="us-status">—</span></div><div class="clock-time" id="us-time">--:--:--</div><div class="clock-date" id="us-date">Loading…</div><div class="clock-date">NYSE / Nasdaq regular hours <span id="us-hours">09:30–16:00</span></div></section>
</div>
<div class="section"><h2>Trading Hub stats</h2><span class="source" id="source">Connecting…</span></div>
<div id="stats" class="grid"><div class="message">Loading stats from Trading Hub…</div></div>
<div class="foot">Market status uses weekday regular-session hours and local daylight-saving time. Exchange holidays are not included. Reloads automatically every 30 seconds.</div>
</div><script>
(function(){
function text(id,value){var el=document.getElementById(id);if(el){el.textContent=value||'';}}
function load(){var xhr=new XMLHttpRequest();xhr.open('GET','/api/dashboard',true);xhr.timeout=8000;xhr.onreadystatechange=function(){if(xhr.readyState!==4)return;if(xhr.status<200||xhr.status>=300){text('source','Dashboard connection error');return;}try{var d=JSON.parse(xhr.responseText);['uk','us'].forEach(function(k){var c=d[k];text(k+'-time',c.time);text(k+'-date',c.date);text(k+'-status',c.status);text(k+'-hours',c.hours);});text('updated',d.refreshed);var s=d.stats;text('source',s.source+(s.path?' · '+s.path:''));var root=document.getElementById('stats');while(root.firstChild)root.removeChild(root.firstChild);if(!s.ok||!s.stats.length){var msg=document.createElement('div');msg.className='message';msg.textContent=s.error||'No stats available.';root.appendChild(msg);return;}for(var i=0;i<s.stats.length;i++){var item=s.stats[i],card=document.createElement('div'),label=document.createElement('div'),value=document.createElement('div');card.className='card';label.className='label';value.className='value';label.textContent=item[0];value.textContent=item[1];card.appendChild(label);card.appendChild(value);root.appendChild(card);}}catch(e){text('source','Invalid dashboard response');}};xhr.ontimeout=function(){text('source','Trading Hub request timed out');};xhr.send();}
load();window.setInterval(load,30000);
}());
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/dashboard":
            body = json.dumps(dashboard_data(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.split("?", 1)[0] in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.split("?", 1)[0] == "/health":
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    print("Kindle Trading Desk listening on %s:%s; Trading Hub: %s" % (HOST, PORT, UPSTREAM), flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
