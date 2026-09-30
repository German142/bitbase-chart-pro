#!/usr/bin/env python3
"""List swing highs/lows (pivots) from a data file written by fetch.py.

Usage:  swings.py data.json [--window 10] [--since "YYYY-MM-DD HH:MM"]
A candle is a swing high/low when it is the highest high / lowest low within +-window candles.
Use a larger window for the big structure (Elliott counts), a smaller one for intraday levels."""
import argparse, json, datetime as dt


def load(path):
    d = json.load(open(path))
    return [(dt.datetime.fromtimestamp((d["t0"] + i * d["step_ms"]) / 1000), *r) for i, r in enumerate(d["rows"])], d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--window", type=int, default=10)
    ap.add_argument("--since")
    a = ap.parse_args()
    rows, d = load(a.data)
    since = dt.datetime.strptime(a.since, "%Y-%m-%d %H:%M") if a.since else None
    w = a.window
    print(f"{d['symbol']} {d['interval']} · {len(rows)} candles · last close {rows[-1][4]}")
    print(f"range high {max(r[2] for r in rows)} · range low {min(r[3] for r in rows)}")
    for i, (t, o, h, l, c) in enumerate(rows):
        if since and t < since:
            continue
        win = rows[max(0, i - w): i + w + 1]
        if h == max(r[2] for r in win):
            print(f"HIGH {t:%Y-%m-%d %H:%M}  {h}")
        if l == min(r[3] for r in win):
            print(f"LOW  {t:%Y-%m-%d %H:%M}  {l}")


if __name__ == "__main__":
    main()
