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

SHEET_TAB = "Daily Report"
TOP_N = 10
HEADERS = [
    "執行日期", "市場", "排名", "代號", "公司", "市值(USD)", "收盤價", "日變動%",
    "RSI(14)", "MA20", "MA50", "MACD", "技術訊號", "公開研究／新聞", "來源連結",
    "50字摘要", "規則式資訊參考", "免責聲明",
]

# These are a configurable, high-market-cap Taiwan candidate universe, not a claim of an
# official exchange-wide ranking. Set TW_TICKERS to provide your own wider universe.
DEFAULT_TW_TICKERS = "2330.TW,2317.TW,2454.TW,2308.TW,2382.TW,2881.TW,2882.TW,2891.TW,2886.TW,2884.TW,2303.TW,2412.TW,3711.TW,2301.TW,6505.TW,1301.TW,1303.TW,2002.TW,3008.TW,2357.TW,2327.TW,2880.TW,2885.TW,5880.TW,3034.TW,3045.TW,3231.TW,2379.TW,4904.TW,6669.TW"
DEFAULT_US_TICKERS = "NVDA,MSFT,AAPL,AMZN,GOOGL,GOOG,META,BRK-B,AVGO,TSLA,LLY,JPM,WMT,V,MA,XOM,ORCL,COST,NFLX,PLTR,JNJ,HD,PG,ABBV,BAC,KO,CRM,UNH,CSCO"
DISCLAIMER = "僅供資訊研究，非個人化投資建議；投資有風險。"


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
    raw = os.getenv(env_name, fallback)
    return list(dict.fromkeys(x.strip().upper() for x in raw.split(",") if x.strip()))


def fetch_top_by_market_cap(tickers: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in tickers:
        try:
            info = yf.Ticker(symbol).get_fast_info()
            market_cap = num(info.get("market_cap"))
            if not market_cap:
                continue
            rows.append({"symbol": symbol, "market_cap": market_cap})
        except Exception as exc:  # one unavailable ticker should not fail daily update
            logging.warning("Skipping %s: %s", symbol, exc)
    return sorted(rows, key=lambda r: r["market_cap"], reverse=True)[:TOP_N]


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
    return {"close": last, "change": change, "rsi": rsi, "ma20": ma20, "ma50": ma50, "macd": macd}


def signal(d: dict[str, Any]) -> tuple[str, str]:
    bullish = bool(d["close"] and d["ma20"] and d["ma50"] and d["close"] > d["ma20"] > d["ma50"] and d["macd"] and d["macd"] > 0)
    bearish = bool(d["close"] and d["ma20"] and d["ma50"] and d["close"] < d["ma20"] < d["ma50"] and d["macd"] and d["macd"] < 0)
    if bullish and d["rsi"] is not None and d["rsi"] < 70:
        return "偏多", "關注：趨勢偏多且未過熱；仍應設停損並查證基本面。"
    if bearish or (d["rsi"] is not None and d["rsi"] > 75):
        return "偏空／過熱", "保守：趨勢偏弱或可能過熱，宜降低追價並等待確認。"
    return "盤整", "觀望：訊號未一致，待趨勢與基本面資訊更明朗。"


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
    text = f"{company}：{trend}，RSI {fmt(d['rsi'], 0)}。" + ("近期有公開資訊可覆核。" if news else "公開研究資訊有限。")
    return text[:50]


def ai_summary(company: str, d: dict[str, Any], technical: str, news: str) -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return fallback_summary(company, d, technical, news)
    try:
        from openai import OpenAI
        prompt = (f"以繁體中文寫不超過50個字的中性投資訊報摘要，不得下交易指令。"
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
        try:
            ticker = yf.Ticker(symbol)
            metadata = ticker.get_info()
            company = metadata.get("shortName") or symbol
            d = indicators(symbol)
            technical, guidance = signal(d)
            news, link = research_news(company, symbol)
            summary = ai_summary(company, d, technical, news)
            rows.append([report_date, market, rank, symbol, company, round(item["market_cap"], 0), fmt(d["close"]), fmt(d["change"]), fmt(d["rsi"]), fmt(d["ma20"]), fmt(d["ma50"]), fmt(d["macd"]), technical, news, link, summary, guidance, DISCLAIMER])
        except Exception as exc:
            logging.warning("Unable to build %s: %s", symbol, exc)
    return rows


def write_sheet(rows: list[list[str]]) -> None:
    raw_credentials, sheet_id = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"), os.getenv("GOOGLE_SHEET_ID")
    if not raw_credentials or not sheet_id:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEET_ID are required")
    credentials = Credentials.from_service_account_info(json.loads(raw_credentials), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    spreadsheet = gspread.authorize(credentials).open_by_key(sheet_id)
    try:
        ws = spreadsheet.worksheet(SHEET_TAB)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=SHEET_TAB, rows=200, cols=len(HEADERS))
    existing = ws.get_all_values()
    if not existing:
        ws.append_row(HEADERS)
        existing = [HEADERS]
    elif existing[0] != HEADERS:
        ws.update("A1", [HEADERS])
    keys = {(row[0], row[1]): i + 1 for i, row in enumerate(existing[1:]) if len(row) >= 2}
    for row in rows:
        key = (str(row[0]), str(row[1]))
        if key in keys:
            ws.update(f"A{keys[key]}", [row])
        else:
            ws.append_row(row)
    ws.freeze(rows=1)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    tw = fetch_top_by_market_cap(ticker_list("TW_TICKERS", DEFAULT_TW_TICKERS))
    us = fetch_top_by_market_cap(ticker_list("US_TICKERS", DEFAULT_US_TICKERS))
    rows = make_rows("台股", tw) + make_rows("美股", us)
    if not rows:
        raise RuntimeError("No report rows produced; check market-data connectivity")
    write_sheet(rows)
    logging.info("Updated %s rows", len(rows))


if __name__ == "__main__":
    main()
