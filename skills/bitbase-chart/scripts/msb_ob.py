#!/usr/bin/env python3
"""Market Structure Break + Order Block (MSB-OB) from a data file written by fetch.py.

Usage:  msb_ob.py data.json [--len 9] [--fib 0.273] [--all]

This is an independent implementation of the idea behind the popular "Market Structure Break & Order Block"
TradingView indicator (inputs: ZigZag Length 9, Fib Factor for breakout confirmation 0.273). It is NOT the
original Pine source, so signals can differ slightly from TradingView.

Logic
  1. ZigZag: trend flips to down when a candle makes the lowest low of the last <len> candles, and to up when it
     makes the highest high. At every flip the extreme of the finished leg becomes a swing high / swing low.
  2. Market structure break (MSB): with the latest swing high h0 and swing low l0,
       bullish MSB  = a candle CLOSES above  h0 + fib * (h0 - l0)   (while the structure was not bullish yet)
       bearish MSB  = a candle CLOSES below  l0 - fib * (h0 - l0)   (while the structure was not bearish yet)
     fib 0.273 is the 1.273 extension of the last swing range, which filters out tiny wick breaks.
  3. Order block (OB): the last opposite candle at/before the swing that started the impulse
       bullish OB  (Bu-OB) = last bearish candle at the swing low  -> demand zone (green)
       bearish OB  (Be-OB) = last bullish candle at the swing high -> supply zone (red)
     An OB is mitigated when a candle closes through it; mitigated OBs are hidden unless --all / show_mitigated.
This is a tool for reading structure, not a trading signal."""
import argparse, json, datetime as dt


def load(path):
    d = json.load(open(path))
    return [(dt.datetime.fromtimestamp((d["t0"] + i * d["step_ms"]) / 1000), *r) for i, r in enumerate(d["rows"])], d


def zigzag(rows, length=9):
    """Return pivots [(idx, price, 'H'|'L', known_at)], oldest first. known_at is the candle where the flip confirmed the swing."""
    hs = [r[2] for r in rows]; ls = [r[3] for r in rows]
    trend = 1; since = 0; pivots = []
    for i in range(len(rows)):
        a = max(0, i - length + 1)
        to_up = hs[i] >= max(hs[a:i + 1]); to_down = ls[i] <= min(ls[a:i + 1])
        flip = -1 if (trend == 1 and to_down) else 1 if (trend == -1 and to_up) else 0
        if flip == -1:      # up-leg finished -> swing high
            j = max(range(since, i + 1), key=lambda k: hs[k]); pivots.append((j, hs[j], "H", i))
        elif flip == 1:     # down-leg finished -> swing low
            j = min(range(since, i + 1), key=lambda k: ls[k]); pivots.append((j, ls[j], "L", i))
        if flip:
            trend = flip; since = i
    return pivots


def _ob_candle(rows, idx, bullish, look=5):
    """Last bearish (bullish OB) / bullish (bearish OB) candle at or just before the swing candle."""
    for k in range(idx, max(-1, idx - look - 1), -1):
        t, o, h, l, c = rows[k]
        if (bullish and c < o) or (not bullish and c > o):
            return k
    return idx


def detect(rows, length=9, fib=0.273):
    """Return dict(pivots, msb=[...], obs=[...]).
    msb: {"idx" break bar, "from" pivot bar, "price" broken level, "side" "bull"|"bear"}
    obs: {"idx" OB candle, "low", "high", "side", "msb_idx", "mitigated_idx" or None}"""
    pivots = zigzag(rows, length)
    msb, obs = [], []
    market = 0; h0 = l0 = None; p = 0
    for i in range(len(rows)):
        while p < len(pivots) and pivots[p][3] <= i:      # swing is known from the flip candle on (no look-ahead)
            idx, price, kind, _ = pivots[p]
            if kind == "H":
                h0 = (idx, price)
            else:
                l0 = (idx, price)
            p += 1
        if h0 is None or l0 is None:
            continue
        rng = abs(h0[1] - l0[1]); close = rows[i][4]
        if market != 1 and close > h0[1] + fib * rng and i > h0[0]:
            market = 1; msb.append({"idx": i, "from": h0[0], "price": h0[1], "side": "bull"})
            k = _ob_candle(rows, l0[0], True)
            obs.append({"idx": k, "low": rows[k][3], "high": rows[k][2], "side": "bull", "msb_idx": i, "mitigated_idx": None})
        elif market != -1 and close < l0[1] - fib * rng and i > l0[0]:
            market = -1; msb.append({"idx": i, "from": l0[0], "price": l0[1], "side": "bear"})
            k = _ob_candle(rows, h0[0], False)
            obs.append({"idx": k, "low": rows[k][3], "high": rows[k][2], "side": "bear", "msb_idx": i, "mitigated_idx": None})
    for ob in obs:  # mitigation: a close through the block after the break
        for j in range(ob["msb_idx"] + 1, len(rows)):
            c = rows[j][4]
            if (ob["side"] == "bull" and c < ob["low"]) or (ob["side"] == "bear" and c > ob["high"]):
                ob["mitigated_idx"] = j; break
    return {"pivots": pivots, "msb": msb, "obs": obs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data"); ap.add_argument("--len", type=int, default=9); ap.add_argument("--fib", type=float, default=0.273)
    ap.add_argument("--all", action="store_true", help="also list mitigated order blocks")
    a = ap.parse_args()
    rows, d = load(a.data)
    r = detect(rows, a.len, a.fib)
    print(f"{d['symbol']} {d['interval']} · {len(rows)} candles · ZigZag {a.len} · fib {a.fib}")
    print(f"{len(r['pivots'])} swings · {len(r['msb'])} market structure breaks · {len(r['obs'])} order blocks")
    for m in r["msb"]:
        print(f"MSB {m['side'].upper():4} {rows[m['idx']][0]:%Y-%m-%d %H:%M}  broke {m['price']}")
    for ob in r["obs"]:
        state = "active" if ob["mitigated_idx"] is None else f"mitigated {rows[ob['mitigated_idx']][0]:%Y-%m-%d %H:%M}"
        if ob["mitigated_idx"] is None or a.all:
            lab = "Bu-OB" if ob["side"] == "bull" else "Be-OB"
            print(f"{lab} {rows[ob['idx']][0]:%Y-%m-%d %H:%M}  {ob['low']} - {ob['high']}  ({state})")


if __name__ == "__main__":
    main()
