#!/usr/bin/env python3
"""Minimal, landscape-first Kindle dashboard for Trading Desk V2."""

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
STATS_PATH = os.environ.get("TRADING_HUB_STATS_PATH", "/api/status").strip() or "/api/status"
CACHE_SECONDS = max(0, int(os.environ.get("STATS_CACHE_SECONDS", "10")))

_cache = {"at": 0.0, "data": None}
_cache_lock = threading.Lock()


def market_clock(zone_name, opening, closing):
    now = datetime.now(ZoneInfo(zone_name))
    local_time = now.time().replace(tzinfo=None)
    is_open = now.weekday() < 5 and wall_time.fromisoformat(opening) <= local_time < wall_time.fromisoformat(closing)
    return {
        "time": now.strftime("%H:%M"),
        "status": "OPEN" if is_open else "CLOSED",
    }


def _read_json(path):
    if not path.startswith("/"):
        path = "/" + path
    request = Request(
        UPSTREAM + path,
        headers={"Accept": "application/json", "User-Agent": "KindleTradingDesk/1.0"},
    )
    with urlopen(request, timeout=3) as response:
        body = response.read(1_000_000)
        if "json" not in response.headers.get("Content-Type", "").lower() and not body.lstrip().startswith(b"{"):
            raise ValueError("Trading Hub stats endpoint did not return JSON")
        return json.loads(body.decode("utf-8"))


def fetch_stats():
    with _cache_lock:
        if _cache["data"] is not None and time.time() - _cache["at"] < CACHE_SECONDS:
            return _cache["data"]

    try:
        payload = _read_json(STATS_PATH)
        if not isinstance(payload, dict):
            raise ValueError("Trading Hub status response was not a JSON object")

        open_trades = payload.get("open_positions_count")
        if open_trades is None:
            positions = payload.get("open_positions", {})
            open_trades = len(positions) if isinstance(positions, (dict, list)) else 0

        net_pnl = payload.get("net_daily_pnl")
        if net_pnl is None:
            net_pnl = (payload.get("daily_realized_pnl") or 0) + (payload.get("daily_unrealized_pnl") or 0)

        result = {
            "ok": True,
            "open_trades": int(open_trades or 0),
            "net_daily_pnl": float(net_pnl or 0),
            "error": "",
        }
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, OSError, TypeError) as exc:
        result = {
            "ok": False,
            "open_trades": None,
            "net_daily_pnl": None,
            "error": "Trading Hub unavailable: " + str(exc),
        }

    with _cache_lock:
        _cache.update(at=time.time(), data=result)
    return result


def dashboard_data():
    return {
        "uk": market_clock("Europe/London", "08:00", "16:30"),
        "us": market_clock("America/New_York", "09:30", "16:00"),
        "stats": fetch_stats(),
    }


PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<meta http-equiv="refresh" content="300">
<title>Trading Desk</title>
<style>
*{box-sizing:border-box}
html,body{width:100%;height:100%;margin:0;background:#fff;color:#000}
body{font-family:Arial,Helvetica,sans-serif;-webkit-text-size-adjust:none}
.screen{width:100%;height:100%;height:100vh;padding:2.5vh 3vw;display:flex;flex-direction:column;overflow:hidden}
.title{height:5vh;min-height:24px;text-align:center;font-size:2.2vh;font-weight:bold;letter-spacing:.25em;text-transform:uppercase}
.clocks{height:57vh;display:flex;flex-direction:row;border-bottom:3px solid #000}
.clock{width:50%;height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 1vw}
.clock+ .clock{border-left:2px solid #000}
.market{font-size:3.3vh;font-weight:bold;letter-spacing:.12em;text-transform:uppercase}
.time{font-size:16vh;font-size:16vw;font-weight:bold;line-height:1;white-space:nowrap;font-variant-numeric:tabular-nums;margin:2vh 0}
.state{font-size:2.8vh;font-weight:bold;letter-spacing:.14em;text-transform:uppercase;border:2px solid #000;padding:.35em .8em}
.metrics{height:32vh;display:flex;flex-direction:row;padding-top:2vh}
.metric{width:50%;height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}
.metric+ .metric{border-left:2px solid #000}
.label{font-size:3vh;font-weight:bold;letter-spacing:.13em;text-transform:uppercase}
.value{font-size:13vh;font-weight:bold;line-height:1.05;margin-top:1vh;font-variant-numeric:tabular-nums;white-space:nowrap}.pnl-value{font-size:9vh}
.error{display:none;text-align:center;font-size:2vh;font-weight:bold;margin-top:1vh}
@media screen and (orientation:landscape){.time{font-size:16vh;font-size:16vw}}
@media screen and (orientation:portrait){.screen{padding:1.5vh 3vw}.title{height:4vh}.clocks{height:55vh;flex-direction:column}.clock{width:100%;height:50%}.clock+ .clock{border-left:0;border-top:2px solid #000}.time{font-size:11vh;font-size:20vw;margin:1vh 0}.market{font-size:2.6vh}.state{font-size:2vh}.metrics{height:35vh;padding-top:1vh}.label{font-size:2.3vh}.value{font-size:8vh}.pnl-value{font-size:5vh}}
</style>
</head>
<body>
<div class="screen">
  <div class="title">Trading Desk</div>
  <div class="clocks">
    <section class="clock">
      <div class="market">London · UK</div>
      <div class="time" id="uk-time">--:--</div>
      <div class="state" id="uk-state">—</div>
    </section>
    <section class="clock">
      <div class="market">New York · US</div>
      <div class="time" id="us-time">--:--</div>
      <div class="state" id="us-state">—</div>
    </section>
  </div>
  <div class="metrics">
    <section class="metric">
      <div class="label">Open trades</div>
      <div class="value" id="open-trades">—</div>
    </section>
    <section class="metric">
      <div class="label">Daily net P&amp;L · USD</div>
      <div class="value pnl-value" id="pnl">—</div>
    </section>
  </div>
  <div class="error" id="error"></div>
</div>
<script>
(function(){
  function setText(id,value){var el=document.getElementById(id);if(el){el.textContent=value;}}
  function money(value){var amount=Math.abs(value).toFixed(2);return (value<0?'-':'')+'$'+amount;}
  function refresh(){
    var xhr=new XMLHttpRequest();
    xhr.open('GET','/api/dashboard',true);
    xhr.timeout=7000;
    xhr.onreadystatechange=function(){
      if(xhr.readyState!==4){return;}
      if(xhr.status<200||xhr.status>=300){setText('error','Dashboard connection error');return;}
      try{
        var d=JSON.parse(xhr.responseText);
        setText('uk-time',d.uk.time);setText('uk-state','LSE '+d.uk.status);
        setText('us-time',d.us.time);setText('us-state','NYSE '+d.us.status);
        if(d.stats.ok){
          setText('open-trades',String(d.stats.open_trades));
          setText('pnl',money(d.stats.net_daily_pnl));
          setText('error','');document.getElementById('error').style.display='none';
        }else{
          setText('open-trades','—');setText('pnl','—');
          setText('error',d.stats.error);document.getElementById('error').style.display='block';
        }
      }catch(e){setText('error','Invalid dashboard response');document.getElementById('error').style.display='block';}
    };
    xhr.ontimeout=function(){setText('error','Dashboard request timed out');document.getElementById('error').style.display='block';};
    xhr.send();
  }
  refresh();window.setInterval(refresh,60000);
}());
</script>
</body>
</html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/dashboard":
            body = json.dumps(dashboard_data(), ensure_ascii=True).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        elif path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            content_type = "text/html; charset=utf-8"
        elif path == "/health":
            body = b'{"ok":true}'
            content_type = "application/json"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


if __name__ == "__main__":
    print("Kindle Trading Desk listening on %s:%s; Trading Hub: %s%s" % (HOST, PORT, UPSTREAM, STATS_PATH), flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
