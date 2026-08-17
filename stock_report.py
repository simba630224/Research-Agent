"""Daily Taiwan/US large-cap stock research digest -> Google Sheets.

Market-data feeds are delayed/variable. All output is informational, not investment advice.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import feedparser
import gspread
import numpy as np
import yfinance as yf
from google.oauth2.service_account import Credentials

SHEET_TAB_PREFIX = "Daily Report"
TW_TOP_N = 20
US_TOP_N = 10
HEADERS = [
    "執行日期", "市場", "排名", "代號", "公司", "收盤價", "日變動%",
    "MA20", "MA50", "MACD", "20／50日新高低",
    "技術訊號", "判斷依據", "公開研究／新聞", "來源連結", "50字摘要",
]

# These are a configurable, high-market-cap Taiwan candidate universe, not a claim of an
# official exchange-wide ranking. Set TW_TICKERS to provide your own wider universe.
DEFAULT_TW_TICKERS = "2330.TW,2317.TW,2454.TW,2308.TW,2382.TW,2881.TW,2882.TW,2891.TW,2886.TW,2884.TW,2303.TW,2412.TW,3711.TW,2301.TW,6505.TW,1301.TW,1303.TW,2002.TW,3008.TW,2357.TW,2327.TW,2880.TW,2885.TW,5880.TW,3034.TW,3045.TW,3231.TW,2379.TW,4904.TW,6669.TW"
DEFAULT_US_TICKERS = "NVDA,MSFT,AAPL,AMZN,GOOGL,GOOG,META,BRK-B,AVGO,TSLA,LLY,JPM,WMT,V,MA,XOM,ORCL,COST,NFLX,PLTR,JNJ,HD,PG,ABBV,BAC,KO,CRM,UNH,CSCO"
def num(value: Any) -> float | None:
    """Convert a Yahoo field to float without treating missing data as zero."""
    try:
        result = float(value)
        return result if np.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def fmt(value: float | None, digits: int = 2) -> str:
    return "" if value is None else f"{value:.{digits}f}"


def ticker_list(env_name: str, fallback: str) -> list[str]:
    # GitHub expands an unset Secret to an empty string. Treat that exactly like
    # an unset variable so the built-in candidate list is still used.
    raw = os.getenv(env_name) or fallback
    return list(dict.fromkeys(x.strip().upper() for x in raw.split(",") if x.strip()))


def fetch_top_by_market_cap(tickers: list[str], top_n: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in tickers:
        try:
            info = yf.Ticker(symbol).get_fast_info()
            # Yahoo sometimes omits this field on GitHub-hosted runners. Keep a
            # candidate with a zero sort value rather than dropping every stock.
            market_cap = num(info.get("market_cap") or info.get("marketCap"))
            rows.append({"symbol": symbol, "market_cap": market_cap or 0})
        except Exception as exc:  # one unavailable ticker should not fail daily update
            logging.warning("Market-cap lookup failed for %s: %s", symbol, exc)
            rows.append({"symbol": symbol, "market_cap": 0})
    ranked = sorted(rows, key=lambda r: r["market_cap"], reverse=True)[:top_n]
    if ranked and not any(r["market_cap"] for r in ranked):
        logging.warning("Yahoo returned no market caps; using the configured candidate order for this run")
    logging.info("Selected %d of %d candidates", len(ranked), len(tickers))
    return ranked


def indicators(symbol: str) -> dict[str, Any]:
    history = yf.Ticker(symbol).history(period="6mo", auto_adjust=True)
    if history.empty or len(history) < 55:
        raise ValueError("not enough price history")
    close = history["Close"].dropna()
    delta = close.diff()
    gain, loss = delta.clip(lower=0), -delta.clip(upper=0)
    rs = gain.rolling(14).mean() / loss.rolling(14).mean().replace(0, np.nan)
    rsi = num((100 - 100 / (1 + rs)).iloc[-1])
    ma20, ma50 = num(close.rolling(20).mean().iloc[-1]), num(close.rolling(50).mean().iloc[-1])
    macd_series = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    macd = num(macd_series.iloc[-1])
    last, prev = num(close.iloc[-1]), num(close.iloc[-2])
    change = ((last / prev) - 1) * 100 if last and prev else None
    # Compare today's close with the preceding trading days only. A tied high or
    # low is not labelled as a new breakout.
    prior_close = close.shift(1)
    high20, high50 = num(prior_close.rolling(20).max().iloc[-1]), num(prior_close.rolling(50).max().iloc[-1])
    low20, low50 = num(prior_close.rolling(20).min().iloc[-1]), num(prior_close.rolling(50).min().iloc[-1])
    return {
        "close": last, "change": change, "rsi": rsi, "ma20": ma20, "ma50": ma50, "macd": macd,
        "new_high_20": bool(last is not None and high20 is not None and last > high20),
        "new_high_50": bool(last is not None and high50 is not None and last > high50),
        "new_low_20": bool(last is not None and low20 is not None and last < low20),
        "new_low_50": bool(last is not None and low50 is not None and last < low50),
    }


def signal(d: dict[str, Any]) -> tuple[str, str]:
    bullish = bool(d["close"] and d["ma20"] and d["ma50"] and d["close"] > d["ma20"] > d["ma50"] and d["macd"] and d["macd"] > 0)
    bearish = bool(d["close"] and d["ma20"] and d["ma50"] and d["close"] < d["ma20"] < d["ma50"] and d["macd"] and d["macd"] < 0)
    if bullish and d["rsi"] is not None and d["rsi"] < 70:
        return "偏多", "收盤價＞MA20＞MA50、MACD＞0、RSI＜70"
    if bearish or (d["rsi"] is not None and d["rsi"] > 75):
        basis = "收盤價＜MA20＜MA50、MACD＜0" if bearish else "RSI＞75（可能過熱）"
        return "偏空／過熱", basis
    return "盤整", "未同時符合偏多或偏空／過熱條件"


def high_low_status(d: dict[str, Any]) -> str:
    labels = []
    if d["new_high_20"]:
        labels.append("創20日新高")
    if d["new_high_50"]:
        labels.append("創50日新高")
    if d["new_low_20"]:
        labels.append("創20日新低")
    if d["new_low_50"]:
        labels.append("創50日新低")
    return "；".join(labels) or "—"


def research_news(company: str, symbol: str) -> tuple[str, str]:
    query = f'"{company}" {symbol} (analyst OR research OR earnings)'
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    feed = feedparser.parse(url)
    entries = feed.entries[:2]
    if not entries:
        return "未找到近期公開研究／新聞", ""
    titles = "；".join(re.sub(r"\s+", " ", e.get("title", "")) for e in entries)
    return titles[:180], entries[0].get("link", "")


def fallback_summary(company: str, d: dict[str, Any], technical: str, news: str) -> str:
    trend = "均線偏多" if technical == "偏多" else "走勢偏弱" if technical == "偏空／過熱" else "訊號分歧"
    text = f"{trend}，RSI {fmt(d['rsi'], 0)}。" + ("近期有公開資訊可覆核。" if news else "公開研究資訊有限。")
    return text[:50]


def ai_summary(company: str, d: dict[str, Any], technical: str, news: str) -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return fallback_summary(company, d, technical, news)
    try:
        from openai import OpenAI
        prompt = (f"以繁體中文寫不超過50個字的中性投資訊報摘要，不得下交易指令，且不得提及公司名稱或股票代號。"
                  f"公司:{company}; 技術訊號:{technical}; RSI:{fmt(d['rsi'], 0)}; "
                  f"MA20:{fmt(d['ma20'])}; MA50:{fmt(d['ma50'])}; 公開資訊:{news[:180]}")
        response = OpenAI(api_key=key).responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), input=prompt, max_output_tokens=100
        )
        return re.sub(r"\s+", " ", response.output_text).strip()[:50] or fallback_summary(company, d, technical, news)
    except Exception as exc:
        logging.warning("AI summary failed for %s: %s", company, exc)
        return fallback_summary(company, d, technical, news)


def make_rows(market: str, top: list[dict[str, Any]]) -> list[list[str]]:
    report_date = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d")
    rows: list[list[str]] = []
    for rank, item in enumerate(top, start=1):
        symbol = item["symbol"]
        company = symbol
        try:
            ticker = yf.Ticker(symbol)
            # QuoteSummary (get_info) is occasionally rate-limited by Yahoo.
            # A missing company name must not discard an otherwise valid report.
            try:
                metadata = ticker.get_info()
                company = metadata.get("shortName") or symbol
            except Exception as exc:
                logging.warning("Name lookup failed for %s: %s", symbol, exc)
            d = indicators(symbol)
            technical, basis = signal(d)
            news, link = research_news(company, symbol)
            summary = ai_summary(company, d, technical, news)
            rows.append([report_date, market, rank, symbol, company, fmt(d["close"]), fmt(d["change"]), fmt(d["ma20"]), fmt(d["ma50"]), fmt(d["macd"]), high_low_status(d), technical, basis, news, link, summary])
        except Exception as exc:
            # Write a visible row instead of silently producing an empty report.
            # This makes Yahoo outages debuggable from the sheet and keeps the
            # scheduled job alive for subsequent days.
            logging.exception("Unable to build %s", symbol)
            rows.append([report_date, market, rank, symbol, company, "", "", "", "", "", "", "資料取得失敗", "市場資料暫時無法取得", "", "", "市場資料暫時無法取得。"])
    return rows


def write_sheet(rows: list[list[str]]) -> None:
    raw_credentials, sheet_id = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"), os.getenv("GOOGLE_SHEET_ID")
    if not raw_credentials or not sheet_id:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEET_ID are required")
    credentials = Credentials.from_service_account_info(json.loads(raw_credentials), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    spreadsheet = gspread.authorize(credentials).open_by_key(sheet_id)
    # A monthly sheet keeps each tab small (about 400 rows for 20 stocks on 20
    # trading days) while retaining a complete, easy-to-browse history.
    report_month = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m")
    sheet_tab = f"{SHEET_TAB_PREFIX} {report_month}"
    try:
        ws = spreadsheet.worksheet(sheet_tab)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=sheet_tab, rows=1000, cols=len(HEADERS))
    # Remove old columns when the report layout changes.
    if ws.col_count != len(HEADERS):
        ws.resize(cols=len(HEADERS))
    existing = ws.get_all_values()
    if not existing:
        ws.append_row(HEADERS)
        existing = [HEADERS]
    elif existing[0] != HEADERS:
        ws.update("A1", [HEADERS])
    # One row is uniquely identified by date, market, and ticker. Re-running a
    # workflow updates that exact row instead of appending a duplicate.
    keys = {(row[0], row[1], row[3]): i + 1 for i, row in enumerate(existing[1:]) if len(row) >= 4}
    for row in rows:
        key = (str(row[0]), str(row[1]), str(row[3]))
        if key in keys:
            ws.update(f"A{keys[key]}", [row])
        else:
            ws.append_row(row)
    ws.freeze(rows=1)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    tw = fetch_top_by_market_cap(ticker_list("TW_TICKERS", DEFAULT_TW_TICKERS), TW_TOP_N)
    us = fetch_top_by_market_cap(ticker_list("US_TICKERS", DEFAULT_US_TICKERS), US_TOP_N)
    rows = make_rows("台股", tw) + make_rows("美股", us)
    if not rows:
        raise RuntimeError("No report rows produced; check market-data connectivity")
    write_sheet(rows)
    logging.info("Updated %s rows", len(rows))


if __name__ == "__main__":
    main()
