#!/usr/bin/env python3
"""Fetch OHLC candles for a futures pair and save them in the plugin's data format.

Sources:
  bitbase  public endpoint https://www.bitbase.com/fapi/market/v1/public/q/kline
           (often sits behind a Cloudflare browser check; the script detects that)
  binance  public endpoint https://api.binance.com/api/v3/klines (fallback)

Usage:
  fetch.py SUIUSDT --interval 1h --limit 300 --out data.json
  fetch.py BTCUSDT --interval 5m --since "2026-09-30 08:00" --source binance
  fetch.py SUIUSDT --import browser.json --out data.json   # convert a browser export (see SKILL.md)

Data format written:
  {"source", "symbol", "interval", "step_ms", "t0", "rows": [[o, h, l, c], ...]}
"""
import argparse, json, sys, time, datetime as dt, urllib.request, urllib.error

STEPS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000, "1h": 3_600_000,
         "4h": 14_400_000, "1d": 86_400_000}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) bitbase-chart-pro/1.0"}


def norm_symbol(sym):
    s = sym.lower().replace("-", "_").replace("/", "_")
    if "_" not in s and s.endswith("usdt"):
        s = s[:-4] + "_usdt"
    return s  # e.g. sui_usdt


def http_get(url):
    """urllib with certifi if available; falls back to curl (fixes missing CA certs on python.org builds)."""
    import ssl, subprocess
    try:
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            return r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, ssl.SSLError):
        out = subprocess.run(["curl", "-s", "--max-time", "20", "-A", UA["User-Agent"], url],
                             capture_output=True, text=True)
        if out.returncode != 0 or not out.stdout:
            raise RuntimeError(f"request failed: {url}")
        return out.stdout


def http_json(url):
    body = http_get(url)
    if body.lstrip().startswith("<"):
        raise RuntimeError("got HTML instead of JSON (probably a Cloudflare browser check)")
    return json.loads(body)


def from_bitbase(sym, interval, limit):
    url = (f"https://www.bitbase.com/fapi/market/v1/public/q/kline?endTime={int(time.time() * 1000)}"
           f"&limit={limit}&symbol={norm_symbol(sym)}&interval={interval}")
    data = http_json(url)
    res = sorted(data["result"], key=lambda k: k["t"])
    return [(int(k["t"]), float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"])) for k in res]


def from_binance(sym, interval, limit):
    s = norm_symbol(sym).replace("_", "").upper()
    data = http_json(f"https://api.binance.com/api/v3/klines?symbol={s}&interval={interval}&limit={limit}")
    return [(int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4])) for k in data]


def import_browser(path):
    """Accepts the compact export from SKILL.md: {"t0", "step_ms", "m", "d": "o,h,l,c;o,h,l,c"}
    or a raw Bitbase kline response {"result": [{"t","o","h","l","c"}, ...]}."""
    raw = json.load(open(path))
    if "result" in raw:
        res = sorted(raw["result"], key=lambda k: k["t"])
        return [(int(k["t"]), float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"])) for k in res], raw.get("step_ms"), raw.get("symbol")
    m = raw.get("m", 1); step = raw["step_ms"]; out = []
    for i, c in enumerate(raw["d"].split(";")):
        o, h, l, cl = (int(x) / m for x in c.split(","))
        out.append((raw["t0"] + i * step, o, h, l, cl))
    return out, step, raw.get("symbol")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?", help="e.g. BTCUSDT, sui_usdt, SOL-USDT")
    ap.add_argument("--interval", default="1h", choices=sorted(STEPS))
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--since", help='keep candles from this local time, "YYYY-MM-DD HH:MM"')
    ap.add_argument("--source", default="auto", choices=["auto", "bitbase", "binance"])
    ap.add_argument("--import", dest="imp", help="convert a browser export instead of fetching")
    ap.add_argument("--out", default="data.json")
    a = ap.parse_args()

    source = a.source
    if a.imp:
        candles, step, sym = import_browser(a.imp)
        a.symbol = a.symbol or sym
        source = "bitbase"; interval = next((k for k, v in STEPS.items() if v == step), a.interval)
    else:
        if not a.symbol:
            sys.exit("symbol required (or use --import)")
        interval = a.interval; candles = None
        if a.source in ("auto", "bitbase"):
            try:
                candles = from_bitbase(a.symbol, interval, a.limit); source = "bitbase"
            except Exception as e:
                if a.source == "bitbase":
                    sys.exit(f"Bitbase fetch failed: {e}\nUse the browser export described in SKILL.md, then --import.")
                print(f"[info] Bitbase unavailable ({e}); falling back to Binance", file=sys.stderr)
        if candles is None:
            candles = from_binance(a.symbol, interval, a.limit); source = "binance"

    if a.since:
        cut = dt.datetime.strptime(a.since, "%Y-%m-%d %H:%M").timestamp() * 1000
        candles = [c for c in candles if c[0] >= cut]
    if not candles:
        sys.exit("no candles returned")
    out = {"source": source, "symbol": norm_symbol(a.symbol).replace("_", "").upper() if a.symbol else "UNKNOWN", "interval": interval,
           "step_ms": STEPS[interval], "t0": candles[0][0], "rows": [list(c[1:]) for c in candles]}
    json.dump(out, open(a.out, "w"))
    first = dt.datetime.fromtimestamp(candles[0][0] / 1000); last = dt.datetime.fromtimestamp(candles[-1][0] / 1000)
    print(f"saved {len(candles)} candles ({source}, {interval}) {first:%Y-%m-%d %H:%M} → {last:%Y-%m-%d %H:%M}"
          f" · last close {candles[-1][4]} → {a.out}")


if __name__ == "__main__":
    main()
