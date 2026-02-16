"""
Binance BTC/USDT real-time price feed.
Used for:
1. Confirmation signal: verify BTC direction matches Polymarket quote
2. Win/loss detection: check if BTC went up or down in a 5-min window
3. Terminal display: show BTC price + delta every second

Price-to-beat is taken from Binance 5m candle OPEN at window start (aligned with Polymarket window).
"""

import time
from datetime import datetime, timezone, timedelta
import httpx
from typing import Optional, Tuple

BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"
BINANCE_PRICE_URL = "https://api.binance.com/api/v3/ticker/price"


class BinanceFeed:
    """Lightweight BTC/USDT price tracker via Binance REST API."""

    def __init__(self):
        self.http = httpx.Client(timeout=5.0)
        self._cache_price: Optional[float] = None
        self._cache_ts: float = 0.0
        self._cache_ttl: float = 0.8  # refresh at most every 800ms
        # Window tracking: price at START of 5-min window (from Binance 5m candle open)
        self._window_start_price: Optional[float] = None
        self._window_id: Optional[str] = None  # e.g. "12:00-12:05"

    def get_btc_price(self) -> Optional[float]:
        """Get current BTC/USDT price (cached for 800ms to avoid rate limits)."""
        now = time.time()
        if self._cache_price and (now - self._cache_ts) < self._cache_ttl:
            return self._cache_price
        try:
            resp = self.http.get(
                BINANCE_PRICE_URL, params={"symbol": "BTCUSDT"}
            )
            resp.raise_for_status()
            price = float(resp.json()["price"])
            self._cache_price = price
            self._cache_ts = now
            return price
        except Exception:
            return self._cache_price  # return stale if API fails

    def set_window_start(self, window_id: str) -> Optional[float]:
        """
        Legacy: mark window by id, use current price (can be misaligned).
        Prefer set_window_from_end_datetime() for aligned price-to-beat.
        """
        if window_id == self._window_id:
            return self._window_start_price
        price = self.get_btc_price()
        if price:
            self._window_start_price = price
            self._window_id = window_id
        return self._window_start_price

    def set_window_from_end_datetime(self, window_end) -> Optional[float]:
        """
        Set price-to-beat from Binance 5m candle OPEN at window start.
        window_end = datetime (UTC) of end of 5-min window (e.g. 3:45 PM).
        Window start = window_end - 5 min → we fetch that candle's open = aligned Beat.
        """
        try:
            if hasattr(window_end, "timestamp"):
                end_ts = window_end.timestamp()
            else:
                return self._window_start_price
            window_start_ts = end_ts - 300  # 5 minutes before end
            start_ms = int(window_start_ts * 1000)
            window_id = str(window_end)
            if window_id == self._window_id and self._window_start_price is not None:
                return self._window_start_price
            resp = self.http.get(
                BINANCE_KLINE_URL,
                params={
                    "symbol": "BTCUSDT",
                    "interval": "5m",
                    "startTime": start_ms,
                    "limit": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if not data or not isinstance(data[0], (list, tuple)):
                # fallback to current price if kline not available yet
                price = self.get_btc_price()
                if price:
                    self._window_start_price = price
                    self._window_id = window_id
                return self._window_start_price
            # kline: [open_time, open, high, low, close, ...]
            open_price = float(data[0][1])
            self._window_start_price = open_price
            self._window_id = window_id
            return self._window_start_price
        except Exception:
            # fallback: use current price
            price = self.get_btc_price()
            if price:
                self._window_start_price = price
                if hasattr(window_end, "__str__"):
                    self._window_id = str(window_end)
            return self._window_start_price

    def get_window_start_price(self) -> Optional[float]:
        """Price to beat: BTC at start of current 5-min window."""
        return self._window_start_price

    def get_window_delta(self) -> Tuple[Optional[float], Optional[str]]:
        """
        Get BTC price change since window start.
        Returns (delta_dollars, direction) e.g. (+125.50, "UP") or (-80.30, "DOWN").
        """
        if self._window_start_price is None:
            return (None, None)
        current = self.get_btc_price()
        if current is None:
            return (None, None)
        delta = current - self._window_start_price
        direction = "UP" if delta >= 0 else "DOWN"
        return (delta, direction)

    def confirms_direction(self, polymarket_side: str, min_delta: float = 100.0) -> bool:
        """
        Check if Binance BTC direction confirms the Polymarket side.
        E.g. if polymarket_side="DOWN" and BTC has dropped → True.

        Also rejects trades where BTC delta is too small (< min_delta),
        because a tiny move can easily reverse in the remaining seconds.
        """
        delta, btc_direction = self.get_window_delta()
        if delta is None or btc_direction is None:
            return True  # if no data, don't block (fail open)
        # Delta too small → price is too close, could flip any second
        if abs(delta) < min_delta:
            return False
        # Direction must match
        return btc_direction == polymarket_side

    def close(self):
        try:
            self.http.close()
        except Exception:
            pass
