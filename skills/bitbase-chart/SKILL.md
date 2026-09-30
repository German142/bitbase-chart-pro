---
name: bitbase-chart
description: Build clean, share-ready crypto trading charts from real Bitbase futures candles (Binance fallback) with support/resistance, trendlines, order-book walls, Elliott wave counts, scenario projections and a tiled watermark. Use when the user asks for a chart, a technical analysis picture, support/resistance or scenarios for a coin (BTC, SOL, SUI, ...), an Elliott wave count, or a chart to post on X/Telegram.
---

# Bitbase Chart Pro

Produce a professional chart image for a crypto perpetual pair. Always use **real candle data**, never invented prices.
Requires `python3` with `matplotlib` (`pip install matplotlib`).

Scripts live in `${CLAUDE_SKILL_DIR}/scripts/`:
- `fetch.py`: download candles into `data.json`
- `swings.py`: list swing highs/lows so levels and wave counts come from the data
- `render.py`: draw the chart from a JSON config (layout rules are built in, see its docstring)

## 1. Get the data

Try the direct fetch first. Pick the interval to match the question: 1m/5m for intraday, 1h/4h for multi-day structure and Elliott counts.
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/fetch.py" SUIUSDT --interval 1h --limit 300 --out data.json
python3 "${CLAUDE_SKILL_DIR}/scripts/fetch.py" BTCUSDT --interval 5m --since "2026-09-30 08:00" --out data.json
```
Bitbase's public API usually sits behind a Cloudflare browser check. The script detects that and falls back to Binance, which prints very similar prices. The subtitle then says "Binance".

**Exact Bitbase prices.** If the user wants the chart to match Bitbase exactly and a browser tool is available, open `https://www.bitbase.com/futures/trade/btc_usdt` in the browser and run this in the page (same origin, so no Cloudflare issue). Replace the symbol, interval, limit and step in both places:
```js
const s='sui_usdt', iv='1h', step=3600000, m=10000;   // m: 10000 for prices < 20, 100 for < 1000, 1 for BTC-sized
const r=await (await fetch(`/fapi/market/v1/public/q/kline?endTime=${Date.now()}&limit=300&symbol=${s}&interval=${iv}`)).json();
const k=r.result.sort((a,b)=>a.t-b.t);
JSON.stringify({symbol:s,t0:k[0].t,step_ms:step,m,d:k.map(x=>[x.o,x.h,x.l,x.c].map(v=>Math.round(parseFloat(v)*m)).join(',')).join(';')})
```
Save the returned JSON string to `browser.json`, then run `fetch.py SUIUSDT --import browser.json --out data.json`.
Do not use headless browsers or other tricks to get past the Cloudflare check.

**Order-book walls (optional).** In the same page, `/fapi/market/v1/public/q/depth?symbol=sui_usdt&level=200` returns `{b:[...], a:[...]}` with price/qty entries. Bucket them by price, then take the largest buckets as bid walls (below price) and ask walls (above price).

## 2. Read the structure

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/swings.py" data.json --window 10        # big structure
python3 "${CLAUDE_SKILL_DIR}/scripts/swings.py" data.json --window 4 --since "2026-09-30 18:00"   # recent swings
```
Derive every level, trendline anchor and wave point from these pivots. Typical elements:
- **Support/resistance:** repeated swing lows/highs, the day high/low, and levels the user drew.
- **Trendlines/patterns:** two pivots per line. Name the pattern honestly: channel, wedge, triangle, flag.
- **Elliott:** label the impulse 0-1-2-3-4-5 and the correction A-B-C. Check the rules (wave 2 never below wave 0; wave 3 never the shortest; wave 4 does not overlap wave 1). State the invalidation level and give C targets (0.618 to 1.0 × A) or Fibonacci retracements.
- **Scenarios:** usually one main and one alternative, each with a trigger level and a target.

## 3. Write the config and render

Create `chart.json` (all keys are documented in `render.py`'s docstring; see `examples/` in the plugin repo):
```json
{
  "data": "data.json", "out": "chart.png",
  "title": "Falling Wedge: Scenarios",
  "watermark": "@userhandle",
  "levels": [{"price": 1.2114, "label": "DAY HIGH 1.2114", "color": "red"}],
  "trendlines": [{"from": ["2026-09-30 18:50", 1.2046], "to": ["2026-09-30 21:35", 1.1588], "legend": "Falling wedge"}],
  "walls": [{"from": 1.1625, "to": 1.1675, "side": "ask", "legend": "Ask wall 1.165"}],
  "scenarios": [
    {"legend": "Bullish: break 1.165 → 1.185", "color": "green", "path": [[6, 1.160], [10, 1.156], [24, 1.185]]},
    {"legend": "Bearish: lose 1.1426 → 1.125", "color": "red", "path": [[6, 1.144], [10, 1.148], [30, 1.126]]}
  ]
}
```
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/render.py" chart.json
```
Scenario `path` points are `[candles ahead of the last candle, price]`.

## 4. Quality check (always)

Open or view the PNG before handing it over:
- no text overlapping other text or tags. Shorten labels, move the legend (`legend_loc`) or adjust `ylim` if needed
- level tags fully visible on the right, NOW tag present, title not colliding with the ticker
- the lines really touch the pivots they claim to

Ask the user for their handle for the watermark if it is unknown. The watermark is tiled so it cannot simply be cropped out.

## 5. Optional post text

If the user wants a caption, keep it short and trader-style: ticker with `$`, prices with `$`, the key level, "Hold X → Y / Lose X → Z", few emojis. Do not promise returns. Never post anything publicly yourself; hand the text to the user.
