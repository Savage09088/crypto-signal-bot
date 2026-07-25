"""
Crypto Signal Bot — main entry point.

Watches BTC, ETH, SOL (fixed) + dynamically detected top movers (CoinGecko),
computes a Buy Strength / Sell Strength score per coin from RSI, MACD, EMA
cross, Bollinger position, and volume-confirmed moves, and sends an
Email + WhatsApp alert whenever a "heavy" signal crosses the threshold.

Designed to run every few minutes via GitHub Actions (see
.github/workflows/crypto-signals.yml) — no server required.
"""
import json
import os
import time
from datetime import datetime, timezone

from data_sources import get_klines_with_fallback, get_top_movers
from indicators import compute_scores
from alerts import send_alert
from dashboard import write_dashboard

STATE_FILE = "state.json"

FIXED_WATCHLIST = ["BTC", "ETH", "SOL"]
INTERVAL_BINANCE = os.environ.get("INTERVAL_BINANCE", "15m")
INTERVAL_BYBIT = os.environ.get("INTERVAL_BYBIT", "15")
CANDLE_LIMIT = int(os.environ.get("CANDLE_LIMIT", "100"))

BUY_ALERT_THRESHOLD = float(os.environ.get("BUY_ALERT_THRESHOLD", "70"))
SELL_ALERT_THRESHOLD = float(os.environ.get("SELL_ALERT_THRESHOLD", "70"))
COOLDOWN_MINUTES = float(os.environ.get("COOLDOWN_MINUTES", "60"))
TOP_MOVERS_COUNT = int(os.environ.get("TOP_MOVERS_COUNT", "8"))
EXCLUDE_SYMBOLS = {"USDT", "USDC", "DAI", "FDUSD", "TUSD"}  # stablecoins are never useful signals


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def in_cooldown(state: dict, symbol: str, direction: str) -> bool:
    key = f"{symbol}:{direction}"
    last = state.get(key)
    if not last:
        return False
    elapsed_min = (time.time() - last) / 60
    return elapsed_min < COOLDOWN_MINUTES


def mark_alerted(state: dict, symbol: str, direction: str):
    state[f"{symbol}:{direction}"] = time.time()


def build_watchlist() -> list[str]:
    movers = get_top_movers(top_n=TOP_MOVERS_COUNT)
    movers = [m for m in movers if m not in EXCLUDE_SYMBOLS]
    combined = list(dict.fromkeys(FIXED_WATCHLIST + movers))  # de-dup, preserve order
    return combined


def format_alert(symbol: str, direction: str, score: float, metrics: dict, source: str) -> tuple[str, str]:
    emoji = "🟢📈" if direction == "BUY" else "🔴📉"
    subject = f"{emoji} {symbol} HEAVY {direction} SIGNAL — strength {score}/100"
    body = (
        f"{symbol}/USDT — {direction} strength: {score}/100\n"
        f"Price: ${metrics['last_price']:.6g}  ({metrics['pct_change']:+.2f}% last candle)\n"
        f"Source: {source}\n\n"
        f"RSI(14): {metrics['rsi']}\n"
        f"MACD hist: {metrics['macd_hist']} "
        f"(cross_up={metrics['macd_cross_up']}, cross_down={metrics['macd_cross_down']})\n"
        f"EMA20>EMA50: {metrics['ema_bull']} "
        f"(cross_up={metrics['ema_cross_up']}, cross_down={metrics['ema_cross_down']})\n"
        f"Bollinger position (0=lower,1=upper): {metrics['bb_pos']}\n"
        f"Volume ratio vs 20-period avg: {metrics['volume_ratio']}x\n\n"
        f"Time (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Not financial advice — automated technical signal only."
    )
    return subject, body


def run():
    state = load_state()
    watchlist = build_watchlist()
    print(f"[run] watchlist: {watchlist}")

    results = []
    for symbol in watchlist:
        df, source = get_klines_with_fallback(symbol, INTERVAL_BINANCE, INTERVAL_BYBIT, CANDLE_LIMIT)
        if df is None or len(df) < 55:
            print(f"[run] {symbol}: insufficient data, skipping")
            continue
        try:
            metrics = compute_scores(df)
        except Exception as e:
            print(f"[run] {symbol}: scoring failed: {e}")
            continue

        results.append((symbol, source, metrics))
        print(
            f"[run] {symbol} ({source}) buy={metrics['buy_strength']} "
            f"sell={metrics['sell_strength']} rsi={metrics['rsi']} price={metrics['last_price']}"
        )

        if metrics["buy_strength"] >= BUY_ALERT_THRESHOLD and not in_cooldown(state, symbol, "BUY"):
            subject, body = format_alert(symbol, "BUY", metrics["buy_strength"], metrics, source)
            send_alert(subject, body)
            mark_alerted(state, symbol, "BUY")

        if metrics["sell_strength"] >= SELL_ALERT_THRESHOLD and not in_cooldown(state, symbol, "SELL"):
            subject, body = format_alert(symbol, "SELL", metrics["sell_strength"], metrics, source)
            send_alert(subject, body)
            mark_alerted(state, symbol, "SELL")

    save_state(state)
    write_dashboard(results)

    # Optional: print a summary table to the Action logs for quick manual checking
    print("\n[summary] symbol | buy | sell | rsi | price")
    for symbol, source, m in sorted(results, key=lambda r: max(r[2]["buy_strength"], r[2]["sell_strength"]), reverse=True):
        print(f"  {symbol:<6} | {m['buy_strength']:>5} | {m['sell_strength']:>5} | {m['rsi']:>5} | {m['last_price']}")


if __name__ == "__main__":
    run()
