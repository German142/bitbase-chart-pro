---
description: Build a share-ready chart for a crypto pair (levels, patterns, scenarios, optional Elliott count)
argument-hint: "<SYMBOL> [interval] [@watermark-handle] [elliott]"
---

Create a chart for: $ARGUMENTS

Use the `bitbase-chart` skill from this plugin:
1. Parse the arguments: symbol (e.g. BTCUSDT, SUIUSDT), interval (default 1h, or 5m for intraday requests), an optional `@handle` for the watermark, and `elliott` if a wave count is wanted.
2. Fetch real candles, find the swings, pick the levels, patterns and scenarios from the data.
3. Render the chart, check it for overlapping text, and show the PNG path.
4. Summarize the key levels and both scenarios in 3–5 short lines, and offer a short post caption.
