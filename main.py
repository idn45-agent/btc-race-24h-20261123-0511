"""cbBTC dip-buy bot for make.fun btc-race-24h-20261123-0511.

Strategy: sit in cash, wait for a sharp fall from the recent high, buy the
whole equity once the fall pauses (latest close above the previous close,
or immediately on a very deep fall), and sell on recovery, on a hard stop,
or on a trailing retracement from the post-entry peak. No new entries near
the end of the window, so a fresh position is never forced to flatten
before it can work. A drawdown guard halts entries past 10% equity
drawdown and closes an open position past 15%.

Costs: a full-size round trip pays ~26 bps (4 bps fee + 2 bps slippage +
constant-product price impact), so every trade must catch a move larger
than that. Deterministic: no clock, no network, no randomness, no
environment reads; the only state is the bar history and the entry record.

Speaks agent-fun/bars-replay/v1 via the vendored kit shim (vendor/).
Run: python3 -P -s main.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars  # noqa: E402

SYMBOL = "CBBTC"
BPS = 10_000

# --- strategy parameters (swept offline on the dev window) ---
LOOKBACK = 110
DROP_BPS = 100
DEEP_BPS = 150
RECOVER_BPS = 100
STOP_BPS = 150
ARM_BPS = 50
TRAIL_BPS = 80
HALT_DD_BPS = 1000
EXIT_DD_BPS = 1500
NO_ENTRY_LAST_BARS = 120
TOTAL_BARS = 1440
MAX_SLIP_BPS = 120


class Bot:
    """Keeps the bar history and the open-trade record across batches."""

    def __init__(self):
        self.closes = []          # close prices (int, price_scale 5) in order
        self.entry_price = None   # fill price of the open buy, or None
        self.peak_since_entry = None
        self.peak_equity = None   # highest equity seen, in quote units

    def on_batch(self, state, batch):
        if state.warming_up:
            return []
        close = state.close(SYMBOL)
        if close is None:
            return []
        self.closes.append(close)

        # Fold this batch's fills in: a filled buy sets the entry price.
        for fill in batch.get("fills") or []:
            if fill.get("symbol") != SYMBOL or fill.get("status") != "filled":
                continue
            if fill.get("side") == "buy":
                self.entry_price = int(fill["price"])
                self.peak_since_entry = int(fill["price"])
            elif fill.get("side") == "sell":
                self.entry_price = None
                self.peak_since_entry = None

        # Track peak equity for the drawdown guard.
        if self.peak_equity is None or state.equity > self.peak_equity:
            self.peak_equity = state.equity
        drawdown_bps = (
            (self.peak_equity - state.equity) * BPS // self.peak_equity
            if self.peak_equity
            else 0
        )

        holding = state.positions.get(SYMBOL)
        if holding is not None and holding.qty > 0:
            return self._maybe_exit(state, holding, close, drawdown_bps)
        return self._maybe_enter(state, close, drawdown_bps)

    def _maybe_exit(self, state, holding, close, drawdown_bps):
        entry = self.entry_price
        if entry is None:
            # Position exists but we never saw its fill (e.g. a replay
            # quirk): fall back to the position's cost basis.
            # value = qty * price // 10**7, so price = cost * 10**7 // qty.
            entry = holding.cost * 10 ** 7 // max(holding.qty, 1)
        if self.peak_since_entry is None:
            self.peak_since_entry = close
        elif close > self.peak_since_entry:
            self.peak_since_entry = close

        sell = False
        if drawdown_bps >= EXIT_DD_BPS:
            sell = True  # drawdown guard: get out
        elif close * BPS <= entry * (BPS - STOP_BPS):
            sell = True  # hard stop below the entry
        elif close * BPS >= entry * (BPS + RECOVER_BPS):
            sell = True  # recovered to target
        elif (
            self.peak_since_entry * BPS >= entry * (BPS + ARM_BPS)
            and close * BPS <= self.peak_since_entry * (BPS - TRAIL_BPS)
        ):
            sell = True  # trailed back from the post-entry peak
        if not sell:
            return []
        return [
            {
                "side": "sell",
                "symbol": SYMBOL,
                "qty": holding.qty,
                "max_slippage_bps": MAX_SLIP_BPS,
            }
        ]

    def _maybe_enter(self, state, close, drawdown_bps):
        if drawdown_bps >= HALT_DD_BPS:
            return []  # drawdown guard: no new entries
        if len(self.closes) < LOOKBACK:
            return []
        if state.seq >= TOTAL_BARS - NO_ENTRY_LAST_BARS:
            return []  # too late in the window for a new trade
        if state.cash <= 0:
            return []
        window = self.closes[-LOOKBACK:]
        recent_high = max(window)
        # Buy only on a fresh sharp fall from the recent high.
        if close * BPS > recent_high * (BPS - DROP_BPS):
            return []
        # ...and only once the fall has paused: the latest close must be
        # above the previous close, so we do not catch a knife mid-fall --
        # unless the fall is very deep (>= DEEP_BPS), where waiting costs
        # more than the extra knife risk.
        deep = close * BPS <= recent_high * (BPS - DEEP_BPS)
        if not deep and (len(self.closes) < 2 or close <= self.closes[-2]):
            return []
        return [
            {
                "side": "buy",
                "symbol": SYMBOL,
                "notional_quote_units": state.cash,
                "max_slippage_bps": MAX_SLIP_BPS,
            }
        ]


makefun_bars.run(Bot().on_batch)
