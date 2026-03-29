"""
Multibagger Alpha Screener
Based on: Yartseva, A. (2025) "The Alchemy of Multibagger Stocks"
CAFE Working Paper No. 33, Birmingham City University

Scoring criteria (7 factors, 100 pts total):
  1. FCF/P ratio          - 25 pts  (most dominant predictor)
  2. B/M ratio            - 20 pts  (value effect)
  3. Market cap / Size    - 15 pts  (size effect, small = better)
  4. EBITDA margin        - 12 pts  (profitability)
  5. ROA                  - 10 pts  (dynamic profitability)
  6. Investment efficiency- 10 pts  (asset growth < EBITDA growth)
  7. 52-week position     -  8 pts  (entry point, near low = better)
"""

from flask import Flask, render_template, jsonify, request, Response
import yfinance as yf
import pandas as pd
import numpy as np
import json, os, time, threading
from datetime import datetime, timedelta
try:
    import requests as req_lib
except ImportError:
    req_lib = None

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC UNIVERSE FETCHING
# ─────────────────────────────────────────────────────────────────────────────
_universe_cache = None
_universe_cache_time = None
UNIVERSE_CACHE_HOURS = 24

def fetch_sp500():
    """Fetch S&P 500 tickers from Wikipedia."""
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        df = tables[0]
        return df["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception:
        return []

def fetch_nasdaq100():
    """Fetch NASDAQ-100 tickers from Wikipedia."""
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
        for t in tables:
            if "Ticker" in t.columns:
                return t["Ticker"].tolist()
            if "Symbol" in t.columns:
                return t["Symbol"].tolist()
        return []
    except Exception:
        return []

def fetch_russell2000_sample():
    """Return a curated Russell 2000 small/mid cap growth sample."""
    return [
        "SMCI","AXON","SAIA","AAON","TREX","NOVT","KTOS","HEI","MASI","IRTC",
        "NVCR","PTCT","RARE","FOLD","KRYS","SWAV","ACAD","HRMY","ITCI","NBIX",
        "SUPN","INCY","EXAS","NTRA","NEOG","OMCL","PRCT","IART","ALNY","IONS",
        "MGLN","CRVL","PRFT","NSIT","SLAB","ICFI","FCN","KFRC","RLI","CINF",
        "CELH","VITL","COKE","FIZZ","LANC","CHEF","SFM","WINA","CVCO","PATK",
        "HLLY","DORM","DECK","SKX","POOL","AAON","GNRC","AEIS","AIMC","FWRD",
        "GLOB","EXLS","WEX","PAYO","IIIV","PCTY","PAYC","EPAM","ONTO","ACLS",
        "SMTC","OSIS","MPWR","MRVL","ZEUS","KALU","CMC","STLD","RS","NUE",
        "HOLI","PSN","DRS","LDOS","SAIC","CACI","BAH","MANT","ICFI","FCN",
        "HUBB","XYL","ETN","PH","ROK","GNRC","ITW","EMR","HON","GE",
    ]

def get_universe():
    """Get combined universe with 24hr cache."""
    global _universe_cache, _universe_cache_time
    now = datetime.now()
    if (_universe_cache is not None and _universe_cache_time is not None and
            (now - _universe_cache_time).total_seconds() < UNIVERSE_CACHE_HOURS * 3600):
        return _universe_cache

    sp500    = fetch_sp500()
    ndq100   = fetch_nasdaq100()
    russell  = fetch_russell2000_sample()
    combined = list(dict.fromkeys(sp500 + ndq100 + russell))  # deduplicate, preserve order
    if len(combined) < 100:
        combined = DEFAULT_UNIVERSE  # fallback
    _universe_cache = combined
    _universe_cache_time = now
    return combined

# ─────────────────────────────────────────────────────────────────────────────
# STOCK UNIVERSE
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_UNIVERSE = [
    # Information Technology
    "AAPL","MSFT","NVDA","AVGO","AMD","MU","AMAT","KLAC","LRCX","MRVL",
    "MPWR","ONTO","ACLS","SMTC","OSIS","PCTY","PAYC","INTU","ADBE","CRM",
    "NOW","PANW","CRWD","ZS","FTNT","SNPS","CDNS","ANSS","PTC","EPAM",
    "GLOB","EXLS","WEX","PAYO","IIIV",
    # Industrials
    "GE","HON","CAT","DE","ITW","EMR","ETN","PH","ROK","XYL",
    "GNRC","HOLI","AEIS","AIMC","KTOS","HEI","TDG","AXON","SAIC","LDOS",
    "CACI","BAH","MANT","PSN","DRS","ICFI","FCN","HUBB","AAON","FWRD",
    # Consumer Discretionary
    "AMZN","TSLA","HD","MCD","NKE","LOW","SBUX","TJX","ROST","ULTA",
    "DECK","SKX","LULU","RH","TPX","DORM","GRMN","POOL","SCI","SFM",
    "WINA","CVCO","PATK","HLLY","FOX",
    # Health Care
    "LLY","UNH","ABBV","TMO","DHR","MDT","ISRG","VRTX","REGN","BIIB",
    "ALNY","IONS","INCY","EXAS","NTRA","MASI","IART","OMCL","NEOG","PRCT",
    "ACAD","HRMY","ITCI","NBIX","SUPN",
    # Financials
    "BRK-B","JPM","BAC","WFC","GS","MS","CB","PGR","TRV","AIG",
    "CINF","RLI","KFRC","HCI","UPCIC",
    # Consumer Staples
    "WMT","COST","PG","KO","PEP","MO","PM","STZ","CELH","VITL",
    "COKE","FIZZ","LANC","CHEF","DINO",
    # Materials
    "NEM","FCX","APD","ECL","NUE","RS","CMC","STLD","ZEUS","KALU",
    # Communication Services
    "GOOGL","META","NFLX","DIS","CHTR","TMUS","T",
    # Real Estate
    "AMT","PLD","EQIX","PSA","EXR",
    # Energy
    "XOM","CVX","EOG","DVN","FANG","OXY",
    # Small/Mid cap growth focus
    "CELH","TREX","NOVT","AAON","MGLN","CRVL","PRFT","NSIT","SLAB",
    "SWAV","IRTC","NVCR","PTCT","RARE","FOLD","KRYS","ITCI","ACAD",
]
# Deduplicate
DEFAULT_UNIVERSE = list(dict.fromkeys(DEFAULT_UNIVERSE))

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_TTL = 6 * 3600  # 6 hours

# ─────────────────────────────────────────────────────────────────────────────
# SCORING ENGINE  (Yartseva 2025)
# ─────────────────────────────────────────────────────────────────────────────
def score_stock(info: dict) -> tuple:
    """
    Returns (total_score, signal, breakdown_dict, red_flags_list)
    """
    score = 0
    breakdown = {}
    red_flags = []

    market_cap = info.get("marketCap") or 0
    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0

    # ── 1. FCF/P  (25 pts) ──────────────────────────────────────────────────
    fcf = info.get("freeCashflow") or 0
    if market_cap > 0 and fcf != 0:
        fcf_p = fcf / market_cap
        if   fcf_p >= 0.12: pts = 25
        elif fcf_p >= 0.08: pts = 21
        elif fcf_p >= 0.05: pts = 16
        elif fcf_p >= 0.02: pts = 9
        elif fcf_p >  0:    pts = 4
        else:
            pts = 0
            red_flags.append("FCF 為負")
    else:
        fcf_p = None
        pts = 0
    score += pts
    breakdown["fcf_p"] = {"value": fcf_p, "pts": pts, "max": 25}

    # ── 2. B/M ratio  (20 pts) ──────────────────────────────────────────────
    book_val = info.get("bookValue") or 0
    if price > 0 and book_val != 0:
        bm = book_val / price
        if   bm >= 1.0:  pts = 20
        elif bm >= 0.6:  pts = 16
        elif bm >= 0.4:  pts = 11   # paper threshold
        elif bm >= 0.2:  pts = 6
        elif bm >  0:    pts = 2
        else:
            pts = 0
            red_flags.append("負股東權益")
    else:
        bm = None
        pts = 0
    score += pts
    breakdown["bm"] = {"value": bm, "pts": pts, "max": 20}

    # ── 3. Market Cap / Size  (15 pts) ──────────────────────────────────────
    if market_cap > 0:
        cap_m = market_cap / 1e6
        if   cap_m < 300:   pts = 15
        elif cap_m < 700:   pts = 13
        elif cap_m < 1500:  pts = 10
        elif cap_m < 5000:  pts = 6
        elif cap_m < 15000: pts = 3
        else:               pts = 0
    else:
        cap_m = None
        pts = 0
    score += pts
    breakdown["market_cap"] = {"value": market_cap, "pts": pts, "max": 15}

    # ── 4. EBITDA Margin  (12 pts) ──────────────────────────────────────────
    ebitda = info.get("ebitda") or 0
    revenue = info.get("totalRevenue") or 0
    if revenue > 0 and ebitda != 0:
        ebitda_m = ebitda / revenue
        if   ebitda_m >= 0.25: pts = 12
        elif ebitda_m >= 0.15: pts = 10
        elif ebitda_m >= 0.08: pts = 7
        elif ebitda_m >= 0.02: pts = 4
        elif ebitda_m >  0:    pts = 1
        else:
            pts = 0
            red_flags.append("EBITDA 為負")
    else:
        ebitda_m = None
        pts = 0
    score += pts
    breakdown["ebitda_margin"] = {"value": ebitda_m, "pts": pts, "max": 12}

    # ── 5. ROA  (10 pts) ────────────────────────────────────────────────────
    roa = info.get("returnOnAssets")
    if roa is not None:
        if   roa >= 0.15: pts = 10
        elif roa >= 0.08: pts = 8
        elif roa >= 0.04: pts = 5
        elif roa >= 0.01: pts = 2
        elif roa >= 0:    pts = 1
        else:
            pts = 0
            red_flags.append("ROA 為負")
    else:
        pts = 0
    score += pts
    breakdown["roa"] = {"value": roa, "pts": pts, "max": 10}

    # ── 6. Investment Efficiency  (10 pts) ──────────────────────────────────
    asset_growth  = info.get("_asset_growth")
    ebitda_growth = info.get("_ebitda_growth")
    if asset_growth is not None:
        if asset_growth < -0.10:
            pts = 0
            red_flags.append("資產持續收縮")
        elif ebitda_growth is not None:
            if asset_growth <= ebitda_growth:   # EBITDA supports investment
                pts = 10
            elif asset_growth <= ebitda_growth * 1.5:
                pts = 5
            else:
                pts = 2
                red_flags.append("資本支出超越EBITDA成長")
        else:
            pts = 5   # neutral
    else:
        pts = 5       # neutral
    score += pts
    breakdown["inv_eff"] = {"value": asset_growth, "pts": pts, "max": 10,
                            "ebitda_growth": ebitda_growth}

    # ── 7. 52-Week Position  (8 pts) ────────────────────────────────────────
    hi52 = info.get("fiftyTwoWeekHigh") or 0
    lo52 = info.get("fiftyTwoWeekLow") or 0
    if hi52 > lo52 and price > 0:
        pos = (price - lo52) / (hi52 - lo52) * 100
        if   pos < 20:  pts = 8
        elif pos < 35:  pts = 6
        elif pos < 50:  pts = 4
        elif pos < 70:  pts = 2
        else:
            pts = 0
            red_flags.append("靠近52週高點")
    else:
        pos = None
        pts = 0
    score += pts
    breakdown["price_pos"] = {"value": pos, "pts": pts, "max": 8}

    # ── Signal ───────────────────────────────────────────────────────────────
    if   score >= 78: signal = "STRONG BUY"
    elif score >= 62: signal = "BUY"
    elif score >= 46: signal = "WATCH"
    elif score >= 30: signal = "NEUTRAL"
    else:             signal = "AVOID"

    return score, signal, breakdown, red_flags


# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCHING WITH CACHE
# ─────────────────────────────────────────────────────────────────────────────
def cache_path(ticker):
    return os.path.join(CACHE_DIR, f"{ticker.replace('-','_')}.json")

def load_cache(ticker):
    fp = cache_path(ticker)
    if not os.path.exists(fp):
        return None
    if time.time() - os.path.getmtime(fp) > CACHE_TTL:
        return None
    try:
        with open(fp) as f:
            return json.load(f)
    except:
        return None

def save_cache(ticker, data):
    try:
        with open(cache_path(ticker), "w") as f:
            json.dump(data, f)
    except:
        pass

def fetch_one(ticker: str) -> dict | None:
    cached = load_cache(ticker)
    if cached:
        return cached

    try:
        stk = yf.Ticker(ticker)
        info = stk.info or {}
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            return None

        # ── Try to get historical asset/EBITDA growth ────────────────────
        try:
            bs = stk.balance_sheet
            if bs is not None and not bs.empty and bs.shape[1] >= 2:
                asset_rows = [r for r in bs.index if "Total Assets" in str(r)
                              or "totalAssets" in str(r).lower()]
                if asset_rows:
                    av = bs.loc[asset_rows[0]].dropna()
                    if len(av) >= 2 and abs(av.iloc[1]) > 0:
                        info["_asset_growth"] = float(
                            (av.iloc[0] - av.iloc[1]) / abs(av.iloc[1]))
        except:
            pass

        try:
            inc = stk.financials
            if inc is not None and not inc.empty and inc.shape[1] >= 2:
                ebitda_rows = [r for r in inc.index
                               if "EBITDA" in str(r).upper()]
                if not ebitda_rows:
                    ebitda_rows = [r for r in inc.index
                                   if "Operating" in str(r)]
                if ebitda_rows:
                    ev = inc.loc[ebitda_rows[0]].dropna()
                    if len(ev) >= 2 and abs(ev.iloc[1]) > 0:
                        info["_ebitda_growth"] = float(
                            (ev.iloc[0] - ev.iloc[1]) / abs(ev.iloc[1]))
        except:
            pass

        score, signal, breakdown, red_flags = score_one(info)

        result = {
            "ticker":       ticker,
            "name":         info.get("shortName", ticker),
            "sector":       info.get("sector", "N/A"),
            "industry":     info.get("industry", "N/A"),
            "price":        info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap":   info.get("marketCap"),
            "score":        score,
            "signal":       signal,
            "breakdown":    breakdown,
            "red_flags":    red_flags,
            "pe":           info.get("trailingPE"),
            "pb":           info.get("priceToBook"),
            "ps":           info.get("priceToSalesTrailing12Months"),
            "roe":          info.get("returnOnEquity"),
            "revenue":      info.get("totalRevenue"),
            "fcf":          info.get("freeCashflow"),
            "ebitda":       info.get("ebitda"),
            "hi52":         info.get("fiftyTwoWeekHigh"),
            "lo52":         info.get("fiftyTwoWeekLow"),
            "fetched_at":   datetime.now().isoformat(),
        }
        save_cache(ticker, result)
        return result
    except Exception as e:
        return None


def score_one(info):
    return score_stock(info)


# ─────────────────────────────────────────────────────────────────────────────
# FED RATE REGIME
# ─────────────────────────────────────────────────────────────────────────────
def get_fed_regime():
    """
    Fetch 3-month T-bill (^IRX) to detect rate trend.
    Paper: rising rates → -8 to -12% headwind on multibagger returns.
    """
    try:
        irx = yf.Ticker("^IRX")
        hist = irx.history(period="6mo", interval="1mo")
        if hist.empty:
            return None
        rates = hist["Close"].dropna().values
        if len(rates) < 3:
            return None
        trend = "rising" if rates[-1] > rates[-3] * 1.05 else (
                "falling" if rates[-1] < rates[-3] * 0.95 else "stable")
        return {
            "current_rate": round(float(rates[-1]), 2),
            "rate_3m_ago":  round(float(rates[-3]), 2),
            "trend":        trend,
            "headwind_pct": -10 if trend == "rising" else 0,
        }
    except:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST
# ─────────────────────────────────────────────────────────────────────────────
def run_backtest(tickers: list, lookback_years: int = 1):
    """
    Simple backtest:
      1. Use current scores to rank stocks.
      2. Simulate a portfolio of top-N stocks held for lookback_years.
      3. Compare to SPY.
    Returns monthly portfolio vs SPY series + stats.
    """
    end   = datetime.today()
    start = end - timedelta(days=365 * lookback_years)

    # Load cached scores
    results = []
    for t in tickers:
        c = load_cache(t)
        if c and c.get("score") is not None:
            results.append(c)

    if not results:
        return {"error": "請先執行選股器以載入資料"}

    results.sort(key=lambda x: x["score"], reverse=True)
    top20 = [r["ticker"] for r in results[:20]]

    # Fetch historical prices
    spy_hist  = yf.download("SPY", start=start, end=end,
                            progress=False, auto_adjust=True)
    if spy_hist.empty:
        return {"error": "無法下載 SPY 資料"}

    spy_ret = spy_hist["Close"].resample("ME").last().pct_change().dropna()
    spy_cum = (1 + spy_ret).cumprod()

    port_returns_list = []
    valid_tickers = []
    win_loss = []

    for t in top20:
        try:
            h = yf.download(t, start=start, end=end,
                            progress=False, auto_adjust=True)
            if h.empty or len(h) < 5:
                continue
            pr = h["Close"].resample("ME").last().pct_change().dropna()
            port_returns_list.append(pr)
            valid_tickers.append(t)
            # 1-year total return
            total_start = h["Close"].iloc[0]
            total_end   = h["Close"].iloc[-1]
            stock_ret   = (total_end - total_start) / total_start
            spy_total   = float(spy_cum.iloc[-1]) - 1
            win_loss.append({
                "ticker": t,
                "return": round(float(stock_ret) * 100, 1),
                "spy_return": round(spy_total * 100, 1),
                "beat": stock_ret > spy_total,
                "score": next((r["score"] for r in results if r["ticker"] == t), 0),
            })
        except:
            continue

    if not port_returns_list:
        return {"error": "無法下載個股資料"}

    port_df   = pd.concat(port_returns_list, axis=1).mean(axis=1).dropna()
    port_cum  = (1 + port_df).cumprod()
    spy_align = spy_cum.reindex(port_cum.index, method="ffill")

    def sharpe(rets):
        if rets.std() == 0:
            return 0
        return float((rets.mean() / rets.std()) * np.sqrt(12))

    win_rate = sum(1 for w in win_loss if w["beat"]) / len(win_loss) * 100 if win_loss else 0
    port_total = float(port_cum.iloc[-1]) - 1 if not port_cum.empty else 0
    spy_total  = float(spy_cum.iloc[-1])  - 1 if not spy_cum.empty else 0

    # Build monthly series for chart
    dates       = [d.strftime("%Y-%m") for d in port_cum.index]
    port_series = [round((v - 1) * 100, 2) for v in port_cum.values]
    spy_series  = [round((float(spy_align.loc[d]) - 1) * 100, 2)
                   if d in spy_align.index else None for d in port_cum.index]

    return {
        "win_rate":       round(win_rate, 1),
        "port_return":    round(port_total * 100, 1),
        "spy_return":     round(spy_total * 100, 1),
        "alpha":          round((port_total - spy_total) * 100, 1),
        "sharpe":         round(sharpe(port_df), 2),
        "n_stocks":       len(valid_tickers),
        "tickers_used":   valid_tickers,
        "dates":          dates,
        "port_series":    port_series,
        "spy_series":     spy_series,
        "stock_details":  sorted(win_loss, key=lambda x: x["return"], reverse=True),
    }


# ─────────────────────────────────────────────────────────────────────────────
# FLASK ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/universe")
def api_universe():
    return jsonify(get_universe())

@app.route("/api/universe/count")
def api_universe_count():
    u = get_universe()
    return jsonify({"count": len(u), "sources": ["S&P 500", "NASDAQ 100", "Russell 2000 精選"]})

@app.route("/api/screen", methods=["POST"])
def api_screen():
    """Screen a list of tickers. Returns results as JSON."""
    data    = request.json or {}
    tickers = data.get("tickers", None)
    if not tickers:
        tickers = get_universe()
    tickers = [t.strip().upper() for t in tickers if t.strip()]

    results = []
    errors  = []
    for t in tickers:
        r = fetch_one(t)
        if r:
            results.append(r)
        else:
            errors.append(t)
        time.sleep(0.08)   # polite rate-limiting

    results.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"results": results, "errors": errors,
                    "screened_at": datetime.now().isoformat()})

@app.route("/api/screen/stream", methods=["POST"])
def api_screen_stream():
    """SSE endpoint – streams one stock result at a time."""
    data    = request.json or {}
    tickers = data.get("tickers", None)
    if not tickers:
        tickers = get_universe()
    tickers = [t.strip().upper() for t in tickers if t.strip()]

    def generate():
        for i, t in enumerate(tickers):
            r = fetch_one(t)
            payload = json.dumps({
                "index":   i,
                "total":   len(tickers),
                "ticker":  t,
                "result":  r,
            })
            yield f"data: {payload}\n\n"
            time.sleep(0.08)
        yield "data: {\"done\": true}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})

@app.route("/api/stock/<ticker>")
def api_stock(ticker):
    """Detailed data for one stock."""
    r = fetch_one(ticker.upper())
    if not r:
        return jsonify({"error": "找不到資料"}), 404
    return jsonify(r)

@app.route("/api/backtest", methods=["POST"])
def api_backtest():
    data    = request.json or {}
    tickers = data.get("tickers", None)
    if not tickers:
        tickers = get_universe()
    years   = int(data.get("years", 1))
    years   = max(1, min(years, 3))
    bt      = run_backtest(tickers, years)
    return jsonify(bt)

@app.route("/api/macro")
def api_macro():
    regime  = get_fed_regime()
    sp500   = yf.Ticker("^GSPC").fast_info
    vix     = yf.Ticker("^VIX").fast_info
    try:
        sp_price  = round(sp500.last_price, 2)
        vix_price = round(vix.last_price, 2)
    except:
        sp_price  = None
        vix_price = None

    return jsonify({
        "sp500":      sp_price,
        "vix":        vix_price,
        "fed_regime": regime,
        "timestamp":  datetime.now().isoformat(),
    })

@app.route("/api/clear_cache", methods=["POST"])
def api_clear_cache():
    removed = 0
    for f in os.listdir(CACHE_DIR):
        if f.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, f))
            removed += 1
    return jsonify({"removed": removed})


if __name__ == "__main__":
    print("=" * 60)
    print("  Multibagger Alpha Screener")
    print("  Based on Yartseva (2025) CAFE Working Paper #33")
    print("  http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=False, port=5000, threaded=True)
