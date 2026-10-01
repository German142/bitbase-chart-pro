#!/usr/bin/env python3
"""Render a share-ready trading chart from a data file (fetch.py) and a chart config (JSON).

Usage:  render.py config.json

Layout rules (built in, so text never overlaps):
  * price levels are drawn as tags OUTSIDE the plot on the right edge, plus a gold "NOW" tag
  * scenarios are listed in a legend box (not as text next to the arrows)
  * projections live in their own shaded area to the right of the last candle
  * the title is placed after the measured width of the ticker
  * an optional watermark (your handle) is tiled diagonally across the whole chart

Config keys (all optional unless marked):
  data*            path to data.json from fetch.py
  out              output PNG (default chart.png)
  ticker           e.g. "$SUI" (default from symbol)
  title*           headline, e.g. "Falling Wedge: Scenarios"
  subtitle         default "<SYMBOL> Perp · <source> · <interval> · last <close>"
  price_format     python format, e.g. "{:.4f}" or "{:,.0f}" (auto if missing)
  ylim             [low, high] (auto with padding if missing)
  projection_bars  empty candles reserved on the right (default 60)
  x_label_format   strftime for x ticks (auto: %H:%M intraday, %d.%m otherwise)
  watermark        e.g. "@yourhandle" (tiled 9x, 7% opacity) - omit for none
  handle           shown top right (defaults to watermark)
  levels           [{"price", "label", "color"}]
  zones            [{"from", "to", "color", "legend", "projection_only": true}]
  walls            [{"from", "to", "side": "bid"|"ask", "legend"}]   order-book walls as bands
  trendlines       [{"from": ["YYYY-MM-DD HH:MM", price], "to": [...], "extend_to": "last"|"projection"|"none",
                     "color", "legend"}]
  waves            [{"time", "price", "label", "color", "position": "up"|"down", "degree": "(1)"}]
  scenarios        [{"legend", "color", "style": "dashed"|"dotted"|"solid", "path": [[bars_ahead, price], ...]}]
  legend_loc       matplotlib legend location (default "upper left")
  theme            "dark" (default, detailed trading look) or "light" (clean TradingView-style look for posting)
  ghost            sketched scenario candles in the projection area (a story, not a forecast):
                   {"path": [close, close, ...] one per future bar, "color", "label": "SCENARIO (not a prediction)", "seed"}
  zones[].label    inline label drawn at the right edge of the zone (used instead of the legend on big-picture charts)
Colors: green, red, orange, gold, white, grey, purple, blue, teal or any hex.
"""
import json, sys, datetime as dt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Patch
from matplotlib.lines import Line2D

THEMES = {
    "dark": dict(BG="#0b0f14", PANEL="#10161d", GRID="#1a222c", TXT="#e6edf3", MUT="#8b949e", UP="#26a69a", DN="#ef5350",
                 TAGTXT="#0b0f14", EDGE="#2a3441", WM="#ffffff", WM_ALPHA=0.07,
                 NAMED={"green": "#2ecc71", "red": "#ff5c5c", "orange": "#ff9f43", "gold": "#f0b90b", "white": "#e6edf3",
                        "grey": "#8b949e", "gray": "#8b949e", "purple": "#b146c2", "blue": "#5b8cff", "teal": "#26a69a",
                        "amber": "#ffb454"}),
    # clean TradingView-style look for posting: light background, green/black candles, soft zones
    "light": dict(BG="#f4f6fa", PANEL="#eceff5", GRID="#dde2ea", TXT="#1e222d", MUT="#787b86", UP="#089981", DN="#1e222d",
                  TAGTXT="#ffffff", EDGE="#c9cfd9", WM="#1e222d", WM_ALPHA=0.06,
                  NAMED={"green": "#089981", "red": "#f23645", "orange": "#ff9800", "gold": "#b8860b", "white": "#1e222d",
                         "grey": "#787b86", "gray": "#787b86", "purple": "#9c27b0", "blue": "#2962ff", "teal": "#089981",
                         "amber": "#e69500"}),
}
STYLES = {"dashed": "--", "dotted": ":", "solid": "-"}


def auto_fmt(price):
    return "{:,.0f}" if price >= 1000 else "{:.2f}" if price >= 20 else "{:.4f}"


def main(path):
    cfg = json.load(open(path))
    th = THEMES.get(cfg.get("theme", "dark"), THEMES["dark"])
    BG, PANEL, GRID, TXT, MUT, UP, DN, NAMED = (th[k] for k in ("BG", "PANEL", "GRID", "TXT", "MUT", "UP", "DN", "NAMED"))
    col = lambda c, d=TXT: NAMED.get(c, c) if c else d
    d = json.load(open(cfg["data"]))
    rows = [(dt.datetime.fromtimestamp((d["t0"] + i * d["step_ms"]) / 1000), *r) for i, r in enumerate(d["rows"])]
    n = len(rows); last = rows[-1]; T0 = rows[0][0]; step_h = d["step_ms"] / 3_600_000
    fmt = cfg.get("price_format") or auto_fmt(last[4])
    proj = cfg.get("projection_bars", 60); xmax = n + proj

    def xi(s):
        return (dt.datetime.strptime(s, "%Y-%m-%d %H:%M") - T0).total_seconds() / 3600 / step_h

    prices = [r[2] for r in rows] + [r[3] for r in rows]
    prices += list(cfg.get("ghost", {}).get("path", []))
    for sc in cfg.get("scenarios", []):
        prices += [p for _, p in sc["path"]]
    for lv in cfg.get("levels", []):
        prices.append(lv["price"])
    if "ylim" in cfg:
        lo, hi = cfg["ylim"]
    else:
        pad = (max(prices) - min(prices)) * 0.08; lo, hi = min(prices) - pad, max(prices) + pad * 1.6
    rng = hi - lo

    fig = plt.figure(figsize=(16, 9), dpi=120); fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0.055, 0.075, 0.79, 0.765]); ax.set_facecolor(BG)
    ax.set_xlim(-3, xmax); ax.set_ylim(lo, hi)

    # projection area
    ax.add_patch(Rectangle((n + 1, lo), proj - 1, rng, color=PANEL, zorder=0))
    ax.axvline(n + 1, color=th["EDGE"], lw=1, zorder=1)
    ghost = cfg.get("ghost")
    ptxt = ghost.get("label", "SCENARIO (not a prediction)") if ghost else "PROJECTION"
    ax.text(n + proj / 2, hi - rng * 0.02, ptxt, color=col(ghost.get("color", "blue")) if ghost else MUT, fontsize=10.5,
            weight="bold", ha="center", va="top", alpha=0.9)

    # candles (dimmed when a wave count is drawn on top)
    alpha = 0.55 if cfg.get("waves") else 0.95
    bmin = rng / 1200
    for i, (t, o, h, l, c) in enumerate(rows):
        cc = UP if c >= o else DN
        ax.plot([i, i], [l, h], color=cc, lw=0.8, zorder=3, alpha=alpha)
        ax.add_patch(Rectangle((i - 0.35, min(o, c)), 0.7, max(abs(c - o), bmin), color=cc, zorder=3, alpha=alpha))

    # ghost candles: a sketched path through the projection area, drawn from the last close
    if ghost:
        import random
        rnd = random.Random(ghost.get("seed", 7)); gc = col(ghost.get("color", "blue")); c0 = last[4]
        for i, nc in enumerate(ghost["path"]):
            x = n + 2 + i; amp = ghost.get("wick", 0.035)
            gh = max(c0, nc) * (1 + rnd.uniform(amp * 0.4, amp)); gl = min(c0, nc) * (1 - rnd.uniform(amp * 0.4, amp))
            ax.plot([x, x], [gl, gh], color=gc, lw=0.9, alpha=0.7, zorder=3)
            ax.add_patch(Rectangle((x - 0.35, min(c0, nc)), 0.7, max(abs(nc - c0), bmin), fc=gc, ec=gc, alpha=0.5, zorder=3))
            c0 = nc

    handles = []
    # zones
    for z in cfg.get("zones", []):
        c = col(z.get("color"), NAMED["green"]); x0 = n + 1 if z.get("projection_only", True) else -3
        ax.add_patch(Rectangle((x0, z["from"]), xmax - x0, z["to"] - z["from"], color=c, alpha=0.16, zorder=2))
        for y in (z["from"], z["to"]):
            ax.plot([x0, xmax], [y, y], color=c, lw=1, alpha=0.6, zorder=2)
        if z.get("legend"):
            handles.append(Patch(facecolor=c, alpha=0.35, edgecolor=c, label=z["legend"]))
        if z.get("label"):
            ax.text(xmax - 0.8, (z["from"] + z["to"]) / 2, z["label"], color=c, fontsize=11, weight="bold", va="center",
                    ha="right", zorder=6, bbox=dict(boxstyle="round,pad=0.25", fc=BG, ec="none", alpha=0.9))
    # order-book walls
    for w in cfg.get("walls", []):
        c = NAMED["green"] if w.get("side") == "bid" else NAMED["red"]
        ax.axhspan(w["from"], w["to"], color=c, alpha=0.18, zorder=1)
        if w.get("legend"):
            handles.append(Patch(facecolor=c, alpha=0.35, edgecolor=c, label=w["legend"]))
    # trendlines
    for tl in cfg.get("trendlines", []):
        (ta, pa), (tb, pb) = tl["from"], tl["to"]; xa, xb = xi(ta), xi(tb)
        slope = (pb - pa) / (xb - xa)
        end = {"last": n - 1, "projection": n + proj * 0.25, "none": xb}.get(tl.get("extend_to", "last"), n - 1)
        c = col(tl.get("color"), NAMED["blue"])
        ax.plot([xa, end], [pa, pa + slope * (end - xa)], color=c, lw=2.2, zorder=5)
        if tl.get("legend") and not any(h.get_label() == tl["legend"] for h in handles):
            handles.append(Line2D([0], [0], color=c, lw=2.2, label=tl["legend"]))
    # waves
    waves = cfg.get("waves", [])
    if waves:
        pts = [(xi(w["time"]), w["price"], w) for w in waves]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=NAMED["white"], lw=2.2, alpha=0.9, zorder=5)
        off = rng * 0.045
        for x, y, w in pts:
            c = col(w.get("color")); up = w.get("position", "up") == "up"; yy = y + off if up else y - off
            ax.scatter([x], [y], s=28, color=c, zorder=6, edgecolor=BG, linewidth=1)
            lab = str(w["label"])
            ax.text(x, yy, lab, color=c, fontsize=15, weight="bold", ha="center", va="center", zorder=8,
                    bbox=dict(boxstyle="circle,pad=0.32" if len(lab) == 1 else "round,pad=0.3", fc=BG, ec=c, lw=2))
            if w.get("degree"):
                ax.text(x, yy + (off if up else -off) * 0.95, w["degree"], color=NAMED["gold"], fontsize=14,
                        weight="bold", ha="center", va="center", zorder=8)
    # levels as tags outside the plot
    # tags that sit too close are pushed apart (top to bottom), the line stays at the real price
    tags = sorted(cfg.get("levels", []) + [{"price": last[4], "label": f"NOW {fmt.format(last[4])}", "color": "gold", "now": True}],
                  key=lambda t: -t["price"])
    ax_h_pt = 0.765 * 9 * 72; gap = 19 * rng / ax_h_pt; prev = None
    for lv in tags:
        y = lv["price"] if prev is None else min(lv["price"], prev - gap); prev = y
        dy = (y - lv["price"]) / rng * ax_h_pt
        c = col(lv.get("color"), NAMED["grey"])
        ax.axhline(lv["price"], color=c, lw=1.0, ls=(0, (4, 3)), alpha=0.7, zorder=1)
        ax.annotate(f" {lv['label']} ", xy=(1.0, lv["price"]), xycoords=("axes fraction", "data"), xytext=(6, dy),
                    textcoords="offset points", color=th["TAGTXT"], fontsize=10, weight="bold", va="center", ha="left",
                    bbox=dict(boxstyle="round,pad=0.35", fc=c, ec="none"), annotation_clip=False)
    # scenarios (listed first in the legend, in config order)
    scen = []
    for sc in cfg.get("scenarios", []):
        c = col(sc.get("color"), NAMED["green"]); ls = STYLES.get(sc.get("style", "dashed"), "--")
        xs = [n - 1] + [n + dx for dx, _ in sc["path"]]; ys = [last[4]] + [p for _, p in sc["path"]]
        ax.plot(xs[:-1], ys[:-1], color=c, lw=2.6, ls=ls, zorder=7)
        ax.add_patch(FancyArrowPatch((xs[-2], ys[-2]), (xs[-1], ys[-1]), arrowstyle="-|>", mutation_scale=22,
                                     color=c, lw=2.6, linestyle=ls, zorder=7))
        if sc.get("legend"):
            scen.append(Line2D([0], [0], color=c, lw=2.6, ls=ls, label=sc["legend"]))
    handles = scen + handles
    if handles:
        leg = ax.legend(handles=handles, loc=cfg.get("legend_loc", "upper left"), fontsize=11.5, frameon=True,
                        facecolor=PANEL, edgecolor=th["EDGE"], labelcolor=TXT, borderpad=0.9, handlelength=2.6)
        leg.set_zorder(20)

    # axes
    span_h = n * step_h
    xfmt = cfg.get("x_label_format") or ("%H:%M" if span_h <= 36 else "%d.%m" if span_h <= 24 * 60 else "%b %Y")
    every = max(1, round((span_h / 8) / step_h))
    ticks = list(range(0, n, every))
    if 36 < span_h <= 24 * 60:  # multi-day: one tick on each midnight instead of drifting through the day
        ticks = [i for i, r in enumerate(rows) if r[0].hour == 0 and r[0].minute == 0] or ticks
    elif span_h > 24 * 60:  # multi-month: first candle of a month (every 6 months beyond ~2 years)
        months = (1, 7) if span_h > 24 * 700 else (1, 4, 7, 10) if span_h > 24 * 365 else range(1, 13)
        ticks = [i for i, r in enumerate(rows) if r[0].month in months and (i == 0 or rows[i - 1][0].month != r[0].month)] or ticks
    ax.set_xticks(ticks); ax.set_xticklabels([rows[i][0].strftime(xfmt) for i in ticks], color=MUT, fontsize=11)
    ax.tick_params(axis="y", colors=MUT, labelsize=10.5)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fmt.format(v)))
    ax.grid(color=GRID, lw=0.7); [sp.set_visible(False) for sp in ax.spines.values()]

    sym = d.get("symbol", "").upper()
    ticker = cfg.get("ticker") or "$" + sym.replace("_", "").replace("USDT", "")
    tk = fig.text(0.055, 0.935, ticker, color=NAMED["gold"] if cfg.get("theme", "dark") == "dark" else UP, fontsize=30, weight="bold", va="center")
    fig.canvas.draw()
    xt = fig.transFigure.inverted().transform(tk.get_window_extent().get_points())[1][0] + 0.012
    fig.text(xt, 0.935, cfg["title"], color=TXT, fontsize=30, weight="bold", va="center")
    sub = cfg.get("subtitle") or f"{sym.replace('_', '')} Perp · {d.get('source', '').title()} · {d.get('interval')} · last {fmt.format(last[4])}"
    fig.text(0.055, 0.885, sub, color=MUT, fontsize=13.5, va="center")
    wm = cfg.get("watermark"); handle = cfg.get("handle", wm)
    if handle:
        fig.text(0.965, 0.935, handle, color=MUT, fontsize=16, ha="right", weight="bold", va="center")
    if wm:
        for gx in (0.14, 0.40, 0.66):
            for gy in (0.20, 0.47, 0.74):
                fig.text(gx + (0.13 if gy == 0.47 else 0), gy, wm, color=th["WM"], alpha=th["WM_ALPHA"], fontsize=30,
                         weight="bold", rotation=22, ha="center", va="center", zorder=50)
    out = cfg.get("out", "chart.png")
    fig.savefig(out, facecolor=BG); plt.close(fig)
    print(f"saved {out} · {n} candles · last {fmt.format(last[4])}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
