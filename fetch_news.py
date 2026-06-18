#!/usr/bin/env python3
"""
India Market Digest
  1. Fetch RSS news
  2. Deduplicate against persistent depository (data/news_store.json)
  3. Analyse new items with Claude — positive / negative / neutral per stock
  4. Commit depository + regenerate docs/index.html
"""

import feedparser
import json
import hashlib
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime

import anthropic

# ── Timezones ─────────────────────────────────────────────────────────────────
IST    = timezone(timedelta(hours=5, minutes=30))
SYDNEY = timezone(timedelta(hours=10))

# ── Stock universe ─────────────────────────────────────────────────────────────
STOCKS = {
    "Banking": {
        "HDFC Bank":        ["HDFC Bank", "HDFCBANK"],
        "ICICI Bank":       ["ICICI Bank", "ICICIBANK"],
        "SBI":              ["State Bank", "SBI", "SBIN"],
        "Kotak Bank":       ["Kotak Mahindra", "Kotak Bank", "KOTAKBANK"],
        "Axis Bank":        ["Axis Bank", "AXISBANK"],
        "Bajaj Finance":    ["Bajaj Finance", "BAJFINANCE"],
        "HDFC Life":        ["HDFC Life", "HDFCLIFE"],
        "SBI Life":         ["SBI Life", "SBILIFE"],
        "Bajaj Finserv":    ["Bajaj Finserv", "BAJAJFINSV"],
        "IndusInd Bank":    ["IndusInd", "INDUSINDBK"],
        "ICICI Pru Life":   ["ICICI Prudential", "ICICIPRULIFE"],
        "Federal Bank":     ["Federal Bank", "FEDERALBNK"],
        "Bandhan Bank":     ["Bandhan Bank", "BANDHANBNK"],
        "AU SFB":           ["AU Small Finance", "AUBANK"],
        "RBL Bank":         ["RBL Bank", "RBLBANK"],
        "PNB":              ["Punjab National", "PNB"],
        "Bank of Baroda":   ["Bank of Baroda", "BANKBARODA"],
        "Canara Bank":      ["Canara Bank", "CANARABANK"],
        "Muthoot Finance":  ["Muthoot Finance", "MUTHOOTFIN"],
        "Shriram Finance":  ["Shriram Finance", "SHRIRAMFIN"],
    },
    "IT": {
        "TCS":              ["TCS", "Tata Consultancy"],
        "Infosys":          ["Infosys", "INFY"],
        "Wipro":            ["Wipro", "WIPRO"],
        "HCL Tech":         ["HCL Tech", "HCLTECH"],
        "Tech Mahindra":    ["Tech Mahindra", "TECHM"],
        "LTIMindtree":      ["LTIMindtree", "LTIM"],
        "Persistent":       ["Persistent Systems", "PERSISTENT"],
        "Coforge":          ["Coforge", "COFORGE"],
        "Mphasis":          ["Mphasis", "MPHASIS"],
        "KPIT Tech":        ["KPIT Tech", "KPITTECH"],
        "Oracle FS":        ["Oracle Financial", "OFSS"],
        "Birlasoft":        ["Birlasoft", "BSOFT"],
        "Cyient":           ["Cyient", "CYIENT"],
    },
    "Telecoms": {
        "Bharti Airtel":    ["Bharti Airtel", "Airtel", "BHARTIARTL"],
        "Reliance Jio":     ["Reliance Jio", "Jio"],
        "Vodafone Idea":    ["Vodafone Idea", "Vi ", "IDEA"],
        "Indus Towers":     ["Indus Towers", "INDUSTOWER"],
        "Tata Comms":       ["Tata Communications", "TATACOMM"],
        "BSNL":             ["BSNL"],
    },
    "Autos": {
        "Maruti Suzuki":    ["Maruti", "MARUTI"],
        "Tata Motors":      ["Tata Motors", "TATAMOTORS"],
        "M&M":              ["Mahindra", "M&M", "MAHINDRA"],
        "Bajaj Auto":       ["Bajaj Auto", "BAJAJAUTO"],
        "Hero MotoCorp":    ["Hero MotoCorp", "HEROMOTOCO"],
        "Eicher Motors":    ["Eicher", "EICHERMOT"],
        "TVS Motor":        ["TVS Motor", "TVSMOTOR"],
        "Ashok Leyland":    ["Ashok Leyland", "ASHOKLEY"],
        "Bosch":            ["Bosch", "BOSCHLTD"],
        "Bharat Forge":     ["Bharat Forge", "BHARATFORG"],
        "Apollo Tyres":     ["Apollo Tyre", "APOLLOTYRE"],
        "MRF":              ["MRF"],
        "Motherson":        ["Motherson", "MOTHERSON"],
    },
    "E-Commerce": {
        "Zomato":           ["Zomato", "ZOMATO"],
        "Swiggy":           ["Swiggy", "SWIGGY"],
        "Nykaa":            ["Nykaa", "FSN"],
        "PolicyBazaar":     ["PolicyBazaar", "PB Fintech", "PBFINTECH"],
        "Paytm":            ["Paytm", "One97", "PAYTM"],
        "Delhivery":        ["Delhivery", "DELHIVERY"],
        "Ola Electric":     ["Ola Electric", "OLAELEC"],
        "Firstcry":         ["Firstcry", "Brainbees", "BRAINBEES"],
        "Indiamart":        ["Indiamart", "INDIAMART"],
        "Info Edge":        ["Naukri", "Info Edge", "NAUKRI"],
        "D-Mart":           ["D-Mart", "DMart", "Avenue Supermarts", "DMART"],
        "Trent":            ["Trent", "Westside", "TRENT"],
        "Honasa":           ["Honasa", "Mamaearth", "HONASA"],
    },
    "Materials": {
        "Tata Steel":       ["Tata Steel", "TATASTEEL"],
        "JSW Steel":        ["JSW Steel", "JSWSTEEL"],
        "Hindalco":         ["Hindalco", "HINDALCO"],
        "Vedanta":          ["Vedanta", "VEDL"],
        "SAIL":             ["SAIL", "Steel Authority"],
        "NMDC":             ["NMDC"],
        "Coal India":       ["Coal India", "COALINDIA"],
        "JSPL":             ["JSPL", "Jindal Steel", "Jindal Power"],
        "Hind Zinc":        ["Hindustan Zinc", "HINDZINC"],
        "Natl Aluminium":   ["National Aluminium", "NATIONALUM"],
        "APL Apollo":       ["APL Apollo", "APLAPOLLO"],
        "UltraTech":        ["UltraTech", "ULTRACEMCO"],
        "Shree Cement":     ["Shree Cement", "SHREECEMC"],
        "Ambuja":           ["Ambuja Cement", "AMBUJACEM"],
        "ACC":              ["ACC Cement", "ACC"],
        "Pidilite":         ["Pidilite", "PIDILITIND"],
        "Asian Paints":     ["Asian Paints", "ASIANPAINT"],
        "SRF":              ["SRF", "SRFLTD"],
        "PI Industries":    ["PI Industries", "PIIND"],
        "UPL":              ["UPL", "UPLLIMITED"],
    },
    "Industrials": {
        "L&T":              ["Larsen", "L&T", "LT "],
        "Siemens":          ["Siemens", "SIEMENS"],
        "ABB India":        ["ABB India", "ABB"],
        "BEL":              ["Bharat Electronics", "BEL"],
        "HAL":              ["HAL", "Hindustan Aeronautics"],
        "BHEL":             ["BHEL", "Bharat Heavy"],
        "Cochin Ship":      ["Cochin Shipyard", "COCHINSHIP"],
        "Power Grid":       ["Power Grid", "POWERGRID"],
        "NTPC":             ["NTPC"],
        "Adani Ports":      ["Adani Ports", "ADANIPORTS"],
        "Adani Enterprises":["Adani Enterprises", "ADANIENT"],
        "Adani Green":      ["Adani Green", "ADANIGREEN"],
        "Tata Power":       ["Tata Power", "TATAPOWER"],
        "CONCOR":           ["Container Corp", "CONCOR"],
        "KEC Intl":         ["KEC International", "KECL"],
        "Cummins":          ["Cummins India", "CUMMINSIND"],
        "Thermax":          ["Thermax", "THERMAX"],
        "Data Patterns":    ["Data Patterns", "DATAPATTNS"],
        "RVNL":             ["RVNL", "Rail Vikas"],
        "IRFC":             ["IRFC", "Indian Railway Finance"],
        "GMR Airports":     ["GMR", "GMRAIRPORT"],
        "IRB Infra":        ["IRB Infra", "IRB"],
        "L&T Finance":      ["L&T Finance", "LTFH"],
    },
}

# Flat term → (sector, label)
_TERM_MAP: dict[str, tuple[str, str]] = {}
for _sec, _stks in STOCKS.items():
    for _lbl, _terms in _stks.items():
        for _t in _terms:
            _TERM_MAP[_t.lower()] = (_sec, _lbl)

MACRO_KEYWORDS = [
    "RBI", "Reserve Bank of India", "rupee", "INR", "USD/INR", "forex reserve",
    "GDP", "inflation", "CPI", "WPI", "IIP", "PMI", "trade deficit",
    "current account", "fiscal deficit", "Union Budget", "GST collection",
    "trade deal", "FTA", "free trade agreement", "tariff", "WTO", "IMF", "World Bank",
    "geopolitics", "sanctions", "ceasefire", "conflict",
    "US-India", "China-India", "Pakistan", "border tension", "LAC",
    "Nifty 50", "Sensex", "NSE", "BSE", "FII", "FPI", "DII", "FDI",
    "repo rate", "MPC", "monetary policy", "rate cut", "rate hike",
    "OPEC", "US Fed", "Federal Reserve", "dollar index", "DXY",
    "war", "export ban", "import duty",
]

SECTOR_KEYWORDS = {
    "Banking":    ["bank", "banking", "NBFC", "insurance", "credit", "loan", "NPA",
                   "fintech", "mutual fund", "AMC", "Nifty Bank", "repo rate",
                   "interest rate", "financial services", "microfinance"],
    "IT":         ["IT sector", "software", "technology", "digital", "AI", "cloud",
                   "outsourcing", "NASSCOM", "SaaS", "Nifty IT", "data center",
                   "cybersecurity", "artificial intelligence"],
    "Telecoms":   ["telecom", "5G", "spectrum", "ARPU", "subscriber",
                   "broadband", "Nifty Telecom", "AGR", "TRAI"],
    "Autos":      ["automobile", "EV", "electric vehicle", "vehicle sales",
                   "auto sector", "passenger vehicle", "two-wheeler",
                   "commercial vehicle", "Nifty Auto", "car sales"],
    "E-Commerce": ["e-commerce", "ecommerce", "online retail", "food delivery",
                   "quick commerce", "q-commerce", "OTT", "digital payments", "UPI"],
    "Materials":  ["steel", "aluminum", "aluminium", "copper", "zinc", "iron ore",
                   "coal", "metal", "mining", "commodity", "Nifty Metal",
                   "cement", "paints", "chemicals", "agrochemicals"],
    "Industrials":["infrastructure", "capital goods", "defence", "defense",
                   "power sector", "electricity", "PLI scheme", "Make in India",
                   "order book", "Nifty Infra", "capex", "EPC", "shipbuilding",
                   "railways", "airport", "logistics"],
}

RSS_FEEDS = [
    "https://economictimes.indiatimes.com/markets/stocks/news/rssfeeds/2146842.cms",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://economictimes.indiatimes.com/economy/rssfeeds/1373380680.cms",
    "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
    "https://www.business-standard.com/rss/markets-106.rss",
    "https://www.business-standard.com/rss/economy-policy-102.rss",
    "https://www.business-standard.com/rss/finance-113.rss",
    "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "https://www.moneycontrol.com/rss/marketreports.xml",
    "https://www.livemint.com/rss/markets",
    "https://www.livemint.com/rss/economy",
    "https://www.livemint.com/rss/companies",
]

SECTOR_COLORS = {
    "Banking":     "#1a73e8",
    "IT":          "#0f9d58",
    "Telecoms":    "#283593",
    "Autos":       "#7b1fa2",
    "E-Commerce":  "#e91e63",
    "Materials":   "#5d4037",
    "Industrials": "#37474f",
}

SENTIMENT_STYLE = {
    "positive": {"color": "#1e3a2a", "border": "#2e7d52", "text": "#4caf80", "label": "▲ Positive"},
    "negative": {"color": "#3a1a1a", "border": "#8b2e2e", "text": "#f28b82", "label": "▼ Negative"},
    "neutral":  {"color": "#1e2030", "border": "#3a4060", "text": "#8892a4", "label": "● Neutral"},
    "mixed":    {"color": "#2a2010", "border": "#7a5c1e", "text": "#ffb74d", "label": "◆ Mixed"},
}

STORE_PATH = Path("data/news_store.json")
STORE_DAYS = None  # keep everything — full historical depository
BATCH_SIZE = 8    # items per Claude call


# ── Helpers ───────────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            return datetime(*val[:6], tzinfo=timezone.utc)
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return parsedate_to_datetime(val).astimezone(timezone.utc)
            except Exception:
                pass
    return None


def item_id(title: str, pub_dt: datetime | None) -> str:
    day = pub_dt.strftime("%Y-%m-%d") if pub_dt else "unknown"
    return hashlib.md5(f"{day}::{title}".encode()).hexdigest()[:16]


def tag_item(title: str, summary: str) -> tuple[set[str], set[str]]:
    combined = f"{title} {summary}".lower()
    sectors, stocks = set(), set()
    for term, (sec, lbl) in _TERM_MAP.items():
        if term in combined:
            sectors.add(sec)
            stocks.add(lbl)
    for sec, kws in SECTOR_KEYWORDS.items():
        if any(kw.lower() in combined for kw in kws):
            sectors.add(sec)
    return sectors, stocks


def is_macro(title: str, summary: str) -> bool:
    combined = f"{title} {summary}".lower()
    return any(kw.lower() in combined for kw in MACRO_KEYWORDS)


# ── Depository ────────────────────────────────────────────────────────────────

def load_store() -> dict:
    if STORE_PATH.exists():
        try:
            return json.loads(STORE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"items": {}}


def save_store(store: dict) -> None:
    STORE_PATH.parent.mkdir(exist_ok=True)
    STORE_PATH.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Claude sentiment analysis ─────────────────────────────────────────────────

def build_history_context(store: dict, stocks: set[str], days: int = 14) -> str:
    """Return recent store items that mention the same stocks, as context."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    relevant = []
    for item in store["items"].values():
        if item.get("pub_dt", "") < cutoff:
            continue
        if any(s in item.get("stocks", []) for s in stocks):
            sent = item.get("sentiment", {})
            relevant.append(
                f"- [{item.get('pub','')[:10]}] {item['title']} "
                f"→ {sent.get('overall','?')}: {sent.get('reasoning','')[:100]}"
            )
    return "\n".join(relevant[-20:]) if relevant else "No recent history for these stocks."


def analyse_batch(client: anthropic.Anthropic, batch: list[dict], store: dict) -> list[dict]:
    """Send a batch of new items to Claude for sentiment analysis. Returns enriched items."""

    items_text = ""
    for i, item in enumerate(batch, 1):
        history = build_history_context(store, set(item["stocks"]))
        items_text += f"""
--- Item {i} ---
Headline: {item['title']}
Summary: {item['summary']}
Stocks tagged: {', '.join(item['stocks']) or 'none (sector-level)'}
Sectors: {', '.join(item['sectors'])}
Recent history for these stocks:
{history}
"""

    prompt = f"""You are an Indian equity analyst. Analyse each news item below and output ONLY valid JSON.

For each item, reason about whether the news is positive, negative, neutral, or mixed for the stocks involved.
Consider: direct impact on earnings/margins/growth, regulatory implications, competitive dynamics, macro linkages.
Use the recent history to spot whether this is a continuation of a trend or a reversal.

Return a JSON array with one object per item, in the same order:
[
  {{
    "overall": "positive|negative|neutral|mixed",
    "reasoning": "2-3 sentence explanation of WHY, referencing specific impact on earnings/valuation",
    "stocks": {{"StockName": "positive|negative|neutral"}}
  }},
  ...
]

Only include stocks from the 'Stocks tagged' list in the stocks dict.
If no specific stocks are tagged, leave stocks as {{}}.

News items:
{items_text}

Return ONLY the JSON array, no other text."""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Extract JSON array even if model adds preamble
        match = re.search(r"\[[\s\S]*\]", raw)
        if not match:
            raise ValueError("No JSON array in response")
        results = json.loads(match.group())
        for item, result in zip(batch, results):
            item["sentiment"] = {
                "overall":   result.get("overall", "neutral"),
                "reasoning": result.get("reasoning", ""),
                "stocks":    result.get("stocks", {}),
            }
    except Exception as e:
        print(f"  Warning: Claude analysis failed for batch: {e}", file=sys.stderr)
        for item in batch:
            item["sentiment"] = {"overall": "neutral", "reasoning": "", "stocks": {}}

    return batch


# ── RSS fetch ─────────────────────────────────────────────────────────────────

def fetch_new_items(store: dict, hours_back: int = 26) -> list[dict]:
    """Fetch RSS and return only items not already in the store."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    seen_titles: set[str] = set()
    new_items: list[dict] = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"Warning: failed {url}: {e}", file=sys.stderr)
            continue

        for entry in feed.entries:
            title = strip_html(entry.get("title", "")).strip()
            if not title or title in seen_titles:
                continue
            pub = parse_date(entry)
            if pub and pub < cutoff:
                continue
            seen_titles.add(title)

            summary  = strip_html(entry.get("summary", ""))[:400]
            link     = entry.get("link", "#")
            pub_str  = pub.astimezone(IST).strftime("%d %b %H:%M IST") if pub else ""
            pub_iso  = pub.isoformat() if pub else ""

            sectors, stocks = tag_item(title, summary)
            macro           = is_macro(title, summary)

            iid = item_id(title, pub)
            if iid in store["items"]:
                continue  # already processed

            new_items.append({
                "id":      iid,
                "title":   title,
                "link":    link,
                "summary": summary,
                "pub":     pub_str,
                "pub_dt":  pub_iso,
                "sectors": sorted(sectors),
                "stocks":  sorted(stocks),
                "macro":   macro,
                "sentiment": None,   # filled by Claude
            })

    return new_items


# ── HTML ──────────────────────────────────────────────────────────────────────

def sentiment_badge(sent: dict | None) -> str:
    if not sent or not sent.get("overall"):
        return ""
    s = sent["overall"]
    st = SENTIMENT_STYLE.get(s, SENTIMENT_STYLE["neutral"])
    return (
        f'<span class="sentiment-badge" '
        f'style="background:{st["color"]};border-color:{st["border"]};color:{st["text"]}">'
        f'{st["label"]}</span>'
    )


def stock_sentiment_tags(sent: dict | None, all_stocks: list[str]) -> str:
    if not sent or not sent.get("stocks"):
        return ""
    tags = []
    for stock in all_stocks:
        s = sent["stocks"].get(stock)
        if not s:
            continue
        st = SENTIMENT_STYLE.get(s, SENTIMENT_STYLE["neutral"])
        tags.append(
            f'<span class="tag tag-stock" '
            f'style="border-color:{st["border"]};color:{st["text"]}">'
            f'{stock.replace("&","&amp;")}</span>'
        )
    return "".join(tags)


def reasoning_block(sent: dict | None) -> str:
    if not sent or not sent.get("reasoning"):
        return ""
    text = sent["reasoning"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<p class="reasoning">{text}</p>'


def item_html(item: dict, show_sector_tags: bool = False) -> str:
    title   = item["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    summary = item["summary"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    link    = item["link"].replace('"', "%22")
    pub     = item["pub"]
    sent    = item.get("sentiment")

    overall = sent.get("overall", "neutral") if sent else "neutral"
    st      = SENTIMENT_STYLE.get(overall, SENTIMENT_STYLE["neutral"])

    stock_tags_html = stock_sentiment_tags(sent, item.get("stocks", []))
    if not stock_tags_html:
        # fallback: plain stock tags
        stock_tags_html = "".join(
            f'<span class="tag tag-stock">{s.replace("&","&amp;")}</span>'
            for s in item.get("stocks", [])
        )

    sector_tags_html = ""
    if show_sector_tags and item.get("sectors"):
        sector_tags_html = "".join(
            f'<span class="tag tag-sector" style="border-color:{SECTOR_COLORS.get(s,"#888")}">{s}</span>'
            for s in item["sectors"]
        )

    return f"""
    <article class="news-item" style="border-left:3px solid {st['border']}">
      <div class="news-top">
        <a href="{link}" target="_blank" rel="noopener noreferrer" class="news-title">{title}</a>
        {sentiment_badge(sent)}
      </div>
      {reasoning_block(sent)}
      {f'<p class="news-summary">{summary}</p>' if summary and not sent else ''}
      <div class="news-footer">
        {f'<span class="news-time">{pub}</span>' if pub else ''}
        <div class="tags">{stock_tags_html}{sector_tags_html}</div>
      </div>
    </article>"""


def generate_html(today_items: list[dict], store: dict, generated_at: datetime) -> str:
    now_ist = generated_at.astimezone(IST).strftime("%d %b %Y, %H:%M IST")
    now_syd = generated_at.astimezone(SYDNEY).strftime("%d %b %Y, %H:%M AEST")

    # Split today's items
    macro_items   = [i for i in today_items if i.get("macro")]
    sector_items  = {sec: [] for sec in STOCKS}
    for item in today_items:
        for sec in item.get("sectors", []):
            if sec in sector_items:
                sector_items[sec].append(item)

    macro_html = (
        "".join(item_html(i, show_sector_tags=True) for i in macro_items[:25])
        or "<p class='empty'>No macro news in last 24h.</p>"
    )

    sector_blocks = ""
    for sec_name, color in SECTOR_COLORS.items():
        items = sector_items.get(sec_name, [])
        if not items:
            continue
        items_html = "".join(item_html(i) for i in items[:15])
        count = len(items)
        sector_blocks += f"""
    <section class="sector-card" id="{sec_name.lower()}">
      <div class="sector-header" style="border-left:4px solid {color}">
        <span class="sector-name">{sec_name}</span>
        <span class="sector-count">{count} {"story" if count==1 else "stories"}</span>
      </div>
      <div class="news-list">{items_html}</div>
    </section>"""

    nav_items = "".join(
        f'<a href="#{s.lower()}" style="border-color:{c}">{s}</a>'
        for s, c in SECTOR_COLORS.items()
        if sector_items.get(s)
    )

    # Depository stats
    total_items = len(store["items"])
    oldest = min((v["pub_dt"] for v in store["items"].values() if v.get("pub_dt")), default="")
    oldest_str = oldest[:10] if oldest else "—"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>India Market Digest</title>
  <style>
    :root {{
      --bg:#0f1117; --surface:#1a1d27; --surface2:#22263a;
      --text:#e8eaf0; --muted:#8892a4; --border:#2a2f42;
      --link:#64b5f6; --link-hover:#90caf9;
      --accent:#ff6b35; --macro:#ffd700;
    }}
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
          background:var(--bg);color:var(--text);font-size:14px;line-height:1.6;}}
    header{{background:var(--surface);border-bottom:1px solid var(--border);
            padding:14px 24px;display:flex;align-items:center;
            justify-content:space-between;flex-wrap:wrap;gap:8px;
            position:sticky;top:0;z-index:100;}}
    .logo{{font-size:20px;font-weight:700;color:var(--accent);letter-spacing:-0.5px;}}
    .logo span{{color:var(--text);}}
    .meta{{display:flex;flex-direction:column;align-items:flex-end;gap:2px;}}
    .updated{{color:var(--muted);font-size:12px;}}
    .store-stat{{color:#5a6480;font-size:11px;}}
    .container{{max-width:1200px;margin:0 auto;padding:20px 16px;}}

    .sector-nav{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px;
                 padding:14px;background:var(--surface);border-radius:8px;
                 border:1px solid var(--border);}}
    .sector-nav a{{color:var(--text);text-decoration:none;font-size:12px;
                   padding:4px 10px;border-radius:4px;border:1px solid;
                   opacity:.8;transition:opacity .15s;}}
    .sector-nav a:hover{{opacity:1;background:var(--surface2);}}

    .macro-section{{background:var(--surface);border:1px solid var(--border);
                    border-top:3px solid var(--macro);border-radius:8px;
                    padding:20px;margin-bottom:24px;}}
    .macro-title{{font-size:16px;font-weight:700;color:var(--macro);
                  margin-bottom:16px;display:flex;align-items:center;gap:8px;}}
    .macro-title::before{{content:"◆";font-size:10px;}}

    .sector-card{{background:var(--surface);border:1px solid var(--border);
                  border-radius:8px;padding:20px;margin-bottom:20px;}}
    .sector-header{{display:flex;align-items:baseline;gap:12px;
                    margin-bottom:16px;padding-left:12px;flex-wrap:wrap;}}
    .sector-name{{font-size:16px;font-weight:700;}}
    .sector-count{{font-size:11px;color:var(--muted);margin-left:auto;}}

    .news-list{{display:flex;flex-direction:column;gap:10px;}}
    .news-item{{padding:12px;background:var(--surface2);border-radius:6px;
                border:1px solid var(--border);border-left-width:3px;
                transition:border-color .15s;}}
    .news-top{{display:flex;align-items:flex-start;gap:10px;margin-bottom:4px;flex-wrap:wrap;}}
    .news-title{{color:var(--link);text-decoration:none;font-weight:500;
                 font-size:13.5px;line-height:1.4;flex:1;min-width:200px;}}
    .news-title:hover{{color:var(--link-hover);text-decoration:underline;}}

    .sentiment-badge{{font-size:11px;padding:2px 8px;border-radius:10px;
                      border:1px solid;white-space:nowrap;font-weight:600;
                      flex-shrink:0;margin-top:1px;}}
    .reasoning{{font-size:12px;color:#a0aabe;margin:6px 0;line-height:1.5;
                border-left:2px solid #2a3050;padding-left:8px;font-style:italic;}}
    .news-summary{{color:var(--muted);font-size:12px;margin-bottom:6px;}}
    .news-footer{{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-top:6px;}}
    .news-time{{font-size:11px;color:#5a6480;margin-right:4px;}}

    .tags{{display:flex;flex-wrap:wrap;gap:4px;}}
    .tag{{font-size:11px;padding:2px 7px;border-radius:10px;font-weight:500;white-space:nowrap;}}
    .tag-stock{{background:#1a2030;border:1px solid;}}
    .tag-sector{{background:transparent;color:var(--muted);border:1px solid;}}

    .empty{{color:var(--muted);font-style:italic;font-size:13px;}}
    footer{{text-align:center;color:var(--muted);font-size:11px;
            padding:32px 16px;border-top:1px solid var(--border);margin-top:40px;}}
  </style>
</head>
<body>
  <header>
    <div class="logo">India <span>Market Digest</span></div>
    <div class="meta">
      <span class="updated">Updated {now_syd} · {now_ist}</span>
      <span class="store-stat">Depository: {total_items:,} items since {oldest_str}</span>
    </div>
  </header>
  <div class="container">
    <nav class="sector-nav">
      <a href="#macro" style="border-color:var(--macro)">Macro</a>
      {nav_items}
    </nav>

    <section class="macro-section" id="macro">
      <div class="macro-title">Indian Macro &amp; Geopolitics</div>
      <div class="news-list">{macro_html}</div>
    </section>

    {sector_blocks}
  </div>
  <footer>
    India Market Digest · F&amp;O stocks · Sentiment powered by Claude · Auto-updated 10am AEST daily<br/>
    Sources: Economic Times · Business Standard · Moneycontrol · LiveMint
  </footer>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    client  = anthropic.Anthropic(api_key=api_key) if api_key else None

    print("Loading depository…", file=sys.stderr)
    store = load_store()
    print(f"  {len(store['items'])} existing items", file=sys.stderr)

    print("Fetching RSS…", file=sys.stderr)
    new_items = fetch_new_items(store)
    print(f"  {len(new_items)} new items", file=sys.stderr)

    # Analyse with Claude in batches
    if new_items and client:
        print("Analysing sentiment…", file=sys.stderr)
        for i in range(0, len(new_items), BATCH_SIZE):
            batch = new_items[i:i + BATCH_SIZE]
            print(f"  batch {i//BATCH_SIZE + 1}: {len(batch)} items", file=sys.stderr)
            analyse_batch(client, batch, store)
            if i + BATCH_SIZE < len(new_items):
                time.sleep(1)  # avoid rate limits
    elif new_items and not client:
        print("  No ANTHROPIC_API_KEY — skipping sentiment", file=sys.stderr)
        for item in new_items:
            item["sentiment"] = {"overall": "neutral", "reasoning": "", "stocks": {}}

    # Commit new items to store
    for item in new_items:
        store["items"][item["id"]] = item

    save_store(store)
    print(f"  Store saved ({len(store['items'])} items)", file=sys.stderr)

    # Collect today's items for the HTML (last 26 hours from store)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=26)).isoformat()
    today_items = sorted(
        [v for v in store["items"].values() if v.get("pub_dt", "") >= cutoff],
        key=lambda x: x.get("pub_dt", ""),
        reverse=True,
    )
    print(f"  {len(today_items)} items in today's digest", file=sys.stderr)

    html = generate_html(today_items, store, datetime.now(timezone.utc))
    out  = Path("docs/index.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Written → {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
