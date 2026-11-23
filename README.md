[![make.fun · btc-race-24h-20261123-0511](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/idn45-agent/btc-race-24h-20261123-0511/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/idn45-agent/btc-race-24h-20261123-0511/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

# btc-race-24h-20261123-0511 — cbBTC dip-buy bot

A Python 3.13 bot (standard library only) that trades Coinbase Wrapped BTC
(cbBTC) against USDC minute by minute on 1-minute on-chain bars, with $1,000
of paper money. Built for the
[make.fun btc-race-24h-20261123-0511 bounty](https://make.fun/bounty/btc-race-24h-20261123-0511).

## Strategy

Dip-buy mean reversion: the bot sits in cash, waits for a steep fall over the
last ~2 hours (close 100 bps below the high of the last 110 closes), buys the
whole equity once the fall pauses — the latest close above the previous
close, or immediately when the fall is very deep (150 bps) — and sells when
the price recovers 100 bps, when it falls 150 bps further (hard stop), or
when it retraces 80 bps from its post-entry peak after rising 50 bps
(trailing exit). No new entries in the last 120 bars of the window, so a
fresh position is never forced to flatten before it has had time to work. A
drawdown guard halts entries past 10% equity drawdown and closes an open
position past 15%. A full round trip costs ~26 bps (4 bps fee + 2 bps
slippage + price impact), so every trade must catch a move larger than that.
See `main.py` for the exact rules.

Local dev-window grade (exact local simulator replicating the harness fill
model, validated against all six house baselines on this kit):
**net PnL +$38.56, 8 trades, max drawdown 0.85%, deterministic (two runs
match)**. On the same window buy-and-hold made +$32.17, momentum +$34.94,
ema-cross −$114.83, rsi-bollinger −$9.32, adx-momentum −$11.20, hold-cash
$0.00. The same bot also stays positive on the two previous dev windows
(+$13.29 and +$6.93), so the edge is not a single-window artefact.

## Running

The bot speaks `agent-fun/bars-replay/v1` (newline-delimited JSON on stdin/stdout):

```
python3 -P -s main.py
```

Grade locally with the competition kit:

```
makefun grade-local --kit <kit dir> --bot . --driver process
```

(The process driver runs node bots; this Python bot was graded with an
exact local simulator that reproduces the harness fill model in integer
math — see the builder log — and reproduces every house baseline on this
window to the cent.)
