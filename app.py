from flask import Flask, render_template, redirect, url_for, request
from datetime import datetime
import math

from data.bist import (
    get_bist100_symbols,
    get_stock_data,
    load_all_stocks,
    load_intraday_stocks,
    get_intraday_stock_data,
)
from data.indicators import add_indicators
from strategy.scorer import score_stock

app = Flask(__name__)

SETUP_PRIORITY = {"A+": 0, "A": 1, "B": 2, "C": 3, "NORMAL": 4}
INTRADAY_MIN_DAILY_SETUP = {"B", "A", "A+"}
INTRADAY_TRIGGER_SCORE = 4

last_results = []
last_scan_time = None
last_intraday_time = None


def clean_number(value, default=0.0):
    try:
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return default
        return value
    except (TypeError, ValueError):
        return default


def setup_sort_key(item):
    return (SETUP_PRIORITY.get(item.get("setup", "NORMAL"), 99), -item["total"])


def analyze_symbol(symbol):
    df = get_stock_data(symbol)
    if df is None or df.empty or len(df) < 50:
        return None

    analysis = score_stock(add_indicators(df.copy()))
    return {
        "symbol": symbol.replace(".IS", ""),
        "total": analysis["total"],
        "max": analysis["max"],
        "decision": analysis["setup_decision"],
        "setup": analysis["setup"],
        "setup_label": analysis["setup_label"],
        "setup_description": analysis["setup_description"],
        "support": clean_number(analysis["support"]),
        "resistance": clean_number(analysis["resistance"]),
        "atr": clean_number(analysis["atr"]),
        "stop": clean_number(analysis["stop"]),
        "rr": clean_number(analysis["rr"]),
        "volume_ratio": clean_number(analysis["volume_ratio"]),
        "ema50_distance": clean_number(analysis["ema50_distance"]),
        "trend": analysis["trend"],
        "momentum": analysis["momentum"],
        "volume": analysis["volume"],
        "comments": analysis["comments"],
    }


def run_scan(refresh=True):
    global last_results, last_scan_time
    stocks = get_bist100_symbols()
    load_all_stocks(stocks, refresh=refresh)

    results = []
    for symbol in stocks:
        try:
            item = analyze_symbol(symbol)
            if item:
                results.append(item)
        except Exception as exc:
            print(f"{symbol} analiz hatası: {exc}")

    results.sort(key=setup_sort_key)
    last_results = results
    last_scan_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    return results


def analyze_intraday(symbol, daily_item):
    if daily_item["setup"] not in INTRADAY_MIN_DAILY_SETUP:
        return None

    df = get_intraday_stock_data(f"{symbol}.IS")
    if df is None or df.empty or len(df) < 50:
        return None

    df = add_indicators(df.copy())
    last = df.iloc[-1]

    checks = {
        "EMA9 > EMA21": clean_number(last.get("EMA9")) > clean_number(last.get("EMA21")),
        "MACD Alış": clean_number(last.get("MACD")) > clean_number(last.get("MACD_SIGNAL")),
        "RSI 50-70": 50 <= clean_number(last.get("RSI")) <= 70,
        "Stochastic Alış": clean_number(last.get("STOCH_K")) > clean_number(last.get("STOCH_D")),
        "15dk Hacim > MA20": clean_number(last.get("Volume")) > clean_number(last.get("VOLUME_MA20")),
        "Fiyat > EMA21": clean_number(last.get("Close")) > clean_number(last.get("EMA21")),
    }
    score = sum(bool(v) for v in checks.values())
    if score < INTRADAY_TRIGGER_SCORE:
        return {"available": True, "score": score, "max": 6, "checks": checks,
                "price": clean_number(last.get("Close")),
                "rsi": clean_number(last.get("RSI")),
                "volume_ratio": (clean_number(last.get("Volume")) / clean_number(last.get("VOLUME_MA20"), 1)
                                 if clean_number(last.get("VOLUME_MA20")) > 0 else None),
                "ema21": clean_number(last.get("EMA21")),
                "ema50": clean_number(last.get("EMA50")),
                "bar_time": str(df.index[-1])}

    ma20 = clean_number(last.get("VOLUME_MA20"))
    volume = clean_number(last.get("Volume"))
    return {
        "available": True,
        "score": score,
        "max": 6,
        "checks": checks,
        "price": clean_number(last.get("Close")),
        "rsi": clean_number(last.get("RSI")),
        "volume_ratio": volume / ma20 if ma20 > 0 else None,
        "ema21": clean_number(last.get("EMA21")),
        "ema50": clean_number(last.get("EMA50")),
        "bar_time": str(df.index[-1]),
    }


def enrich_intraday(results):
    global last_intraday_time
    candidates = [x for x in results if x["setup"] in INTRADAY_MIN_DAILY_SETUP]
    if candidates:
        load_intraday_stocks([f"{x['symbol']}.IS" for x in candidates], period="5d", interval="15m")
    by_symbol = {}
    for item in candidates:
        try:
            trigger = analyze_intraday(item["symbol"], item)
            if trigger:
                by_symbol[item["symbol"]] = trigger
        except Exception as exc:
            print(f"{item['symbol']} 15dk hata: {exc}")
    last_intraday_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    return by_symbol


def summary(results):
    counts = {key: 0 for key in SETUP_PRIORITY}
    for item in results:
        counts[item["setup"]] = counts.get(item["setup"], 0) + 1
    return counts


def get_item(symbol):
    symbol = symbol.upper().replace(".IS", "")
    for item in last_results:
        if item["symbol"] == symbol:
            return item
    return None


@app.route("/")
def index():
    if not last_results:
        return render_template("index.html", results=[], counts=summary([]), last_scan_time=None,
                               intraday={}, last_intraday_time=None)
    intraday = enrich_intraday(last_results)
    return render_template("index.html", results=last_results, counts=summary(last_results),
                           last_scan_time=last_scan_time, intraday=intraday,
                           last_intraday_time=last_intraday_time)


@app.route("/scan")
def scan():
    results = run_scan(refresh=True)
    intraday = enrich_intraday(results)
    return render_template("index.html", results=results, counts=summary(results),
                           last_scan_time=last_scan_time, intraday=intraday,
                           last_intraday_time=last_intraday_time)


@app.route("/stock/<symbol>")
def stock(symbol):
    item = get_item(symbol)
    if item is None:
        run_scan(refresh=True)
        item = get_item(symbol)
    if item is None:
        return redirect(url_for("index"))

    df = get_stock_data(f"{item['symbol']}.IS")
    chart = []
    if df is not None and not df.empty:
        work = add_indicators(df.copy()).tail(180)
        for idx, row in work.iterrows():
            chart.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": clean_number(row.get("Open")),
                "high": clean_number(row.get("High")),
                "low": clean_number(row.get("Low")),
                "close": clean_number(row.get("Close")),
                "ema9": clean_number(row.get("EMA9")),
                "ema21": clean_number(row.get("EMA21")),
                "ema50": clean_number(row.get("EMA50")),
                "ema200": clean_number(row.get("EMA200")),
            })

    intraday = {}
    if item["setup"] in INTRADAY_MIN_DAILY_SETUP:
        load_intraday_stocks([f"{item['symbol']}.IS"], period="5d", interval="15m")
        intraday = analyze_intraday(item["symbol"], item) or {}

    return render_template("stock.html", item=item, chart=chart, intraday=intraday,
                           generated_at=datetime.now().strftime("%d.%m.%Y %H:%M:%S"))


@app.route("/api/scan")
def api_scan():
    results = run_scan(refresh=True)
    intraday = enrich_intraday(results)
    return {
        "scan_time": last_scan_time,
        "intraday_time": last_intraday_time,
        "counts": summary(results),
        "results": results,
        "intraday": intraday,
    }


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
