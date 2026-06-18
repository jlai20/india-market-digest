#!/usr/bin/env python3
"""Fetch Indian market news from RSS feeds and generate HTML dashboard."""

import feedparser
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime

# ── Timezones ─────────────────────────────────────────────────────────────────
IST    = timezone(timedelta(hours=5, minutes=30))
SYDNEY = timezone(timedelta(hours=10))  # AEST

# ── Stock universe (F&O eligible) ─────────────────────────────────────────────
# Maps display label → list of name/ticker strings to match in article text.
# Ordered by rough market cap within each sector for display priority.
STOCKS = {
    # ── Banking & Financial Services ──────────────────────────────────────────
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
    # ── IT & Technology ───────────────────────────────────────────────────────
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
    # ── Telecoms ──────────────────────────────────────────────────────────────
    "Telecoms": {
        "Bharti Airtel":    ["Bharti Airtel", "Airtel", "BHARTIARTL"],
        "Reliance Jio":     ["Reliance Jio", "Jio"],
        "Vodafone Idea":    ["Vodafone Idea", "Vi ", "IDEA"],
        "Indus Towers":     ["Indus Towers", "INDUSTOWER"],
        "Tata Comms":       ["Tata Communications", "TATACOMM"],
        "BSNL":             ["BSNL"],
        "MTNL":             ["MTNL"],
    },
    # ── Automobiles ───────────────────────────────────────────────────────────
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
        "Samvardhana":      ["Samvardhana Motherson"],
    },
    # ── E-Commerce & Consumer Tech ────────────────────────────────────────────
    "E-Commerce": {
        "Zomato":           ["Zomato", "ZOMATO"],
        "Swiggy":           ["Swiggy", "SWIGGY"],
        "Nykaa":            ["Nykaa", "FSN"],
        "PolicyBazaar":     ["PolicyBazaar", "PB Fintech", "PBFINTECH"],
        "Paytm":            ["Paytm", "One97", "PAYTM"],
        "Delhivery":        ["Delhivery", "DELHIVERY"],
        "Honasa":           ["Honasa", "Mamaearth", "HONASA"],
        "Ola Electric":     ["Ola Electric", "OLAELEC"],
        "Firstcry":         ["Firstcry", "Brainbees", "BRAINBEES"],
        "Indiamart":        ["Indiamart", "INDIAMART"],
        "Info Edge":        ["Naukri", "Info Edge", "NAUKRI"],
        "D-Mart":           ["D-Mart", "DMart", "Avenue Supermarts", "DMART"],
        "Trent":            ["Trent", "Westside", "TRENT"],
        "Reliance Retail":  ["Reliance Retail"],
    },
    # ── Materials (Metals, Chemicals, Cement) ─────────────────────────────────
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
        "Berger Paints":    ["Berger Paint", "BERGEPAINT"],
        "SRF":              ["SRF", "SRFLTD"],
        "PI Industries":    ["PI Industries", "PIIND"],
        "Coromandel":       ["Coromandel", "COROMANDEL"],
        "UPL":              ["UPL", "UPLLIMITED"],
    },
    # ── Industrials & Infra ───────────────────────────────────────────────────
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
        "Reliance Infra":   ["Reliance Infra", "RELINFRA"],
        "IRB Infra":        ["IRB Infra", "IRB"],
    },
}

# Flat map: search_term → (sector, display_label)
_TERM_MAP: dict[str, tuple[str, str]] = {}
for _sector, _stocks in STOCKS.items():
    for _label, _terms in _stocks.items():
        for _t in _terms:
            _TERM_MAP[_t.lower()] = (_sector, _label)

# ── Macro keywords ────────────────────────────────────────────────────────────
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
    "war", "ceasefire", "peace deal", "export ban", "import duty",
]

# Sector-level keywords (fallback when no stock name matched)
SECTOR_KEYWORDS = {
    "Banking":      ["bank", "banking", "NBFC", "insurance", "credit", "loan", "NPA",
                     "fintech", "mutual fund", "AMC", "Nifty Bank", "repo rate",
                     "interest rate", "financial services", "microfinance", "MFI"],
    "IT":           ["IT sector", "software", "technology", "digital", "AI", "cloud",
                     "outsourcing", "NASSCOM", "SaaS", "Nifty IT", "data center",
                     "cybersecurity", "artificial intelligence"],
    "Telecoms":     ["telecom", "5G", "spectrum", "ARPU", "subscriber",
                     "broadband", "Nifty Telecom", "AGR", "TRAI"],
    "Autos":        ["automobile", "EV", "electric vehicle", "vehicle sales",
                     "auto sector", "passenger vehicle", "two-wheeler",
                     "commercial vehicle", "Nifty Auto", "car sales"],
    "E-Commerce":   ["e-commerce", "ecommerce", "online retail", "food delivery",
                     "quick commerce", "q-commerce", "OTT", "streaming",
                     "digital payments", "UPI", "fintech platform"],
    "Materials":    ["steel", "aluminum", "aluminium", "copper", "zinc", "iron ore",
                     "coal", "metal", "mining", "commodity", "Nifty Metal",
                     "cement", "paints", "chemicals", "agrochemicals"],
    "Industrials":  ["infrastructure", "capital goods", "defence", "defense",
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


def tag_item(title: str, summary: str) -> tuple[set[str], set[str]]:
    """Return (matched_sectors, matched_stock_labels)."""
    combined = f"{title} {summary}".lower()
    matched_sectors: set[str] = set()
    matched_stocks: set[str] = set()

    # Stock-level matching (most precise)
    for term, (sector, label) in _TERM_MAP.items():
        if term in combined:
            matched_sectors.add(sector)
            matched_stocks.add(label)

    # Sector keyword fallback
    for sector, kws in SECTOR_KEYWORDS.items():
        if any(kw.lower() in combined for kw in kws):
            matched_sectors.add(sector)

    return matched_sectors, matched_stocks


def is_macro(title: str, summary: str) -> bool:
    combined = f"{title} {summary}".lower()
    return any(kw.lower() in combined for kw in MACRO_KEYWORDS)


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_all_news(hours_back: int = 24) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    seen: set[str] = set()

    macro_items: list[dict] = []
    sector_items: dict[str, list[dict]] = {s: [] for s in STOCKS}

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"Warning: failed {url}: {e}", file=sys.stderr)
            continue

        for entry in feed.entries:
            title = strip_html(entry.get("title", "")).strip()
            if not title or title in seen:
                continue
            pub = parse_date(entry)
            if pub and pub < cutoff:
                continue
            seen.add(title)

            link    = entry.get("link", "#")
            summary = strip_html(entry.get("summary", ""))[:300]
            pub_str = pub.astimezone(IST).strftime("%d %b %H:%M IST") if pub else ""

            sectors, stocks = tag_item(title, summary)
            macro           = is_macro(title, summary)

            item = {
                "title":   title,
                "link":    link,
                "summary": summary,
                "pub":     pub_str,
                "pub_dt":  pub,
                "stocks":  sorted(stocks),   # stock tags
                "sectors": sorted(sectors),  # sector tags
            }

            if macro:
                macro_items.append(item)
            for sec in sectors:
                if sec in sector_items:
                    sector_items[sec].append(item)

    def sort_key(i):
        return i["pub_dt"] or datetime.min.replace(tzinfo=timezone.utc)

    macro_items.sort(key=sort_key, reverse=True)
    for k in sector_items:
        sector_items[k].sort(key=sort_key, reverse=True)

    return {"macro": macro_items, "sectors": sector_items}


# ── HTML ──────────────────────────────────────────────────────────────────────

def item_html(item: dict) -> str:
    title   = item["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    summary = item["summary"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    link    = item["link"].replace('"', "%22")
    pub     = item["pub"]

    # Stock tags
    stock_tags = ""
    if item["stocks"]:
        tags = "".join(
            f'<span class="tag tag-stock">{s.replace("&","&amp;")}</span>'
            for s in item["stocks"]
        )
        stock_tags = f'<div class="tags">{tags}</div>'

    # Sector tags (only shown in macro section where sector context is useful)
    sector_tags = ""
    if item.get("_show_sector_tags") and item["sectors"]:
        tags = "".join(
            f'<span class="tag tag-sector" style="border-color:{SECTOR_COLORS.get(s,"#888")}">{s}</span>'
            for s in item["sectors"]
        )
        sector_tags = f'<div class="tags">{tags}</div>'

    return f"""
    <article class="news-item">
      <a href="{link}" target="_blank" rel="noopener noreferrer" class="news-title">{title}</a>
      {f'<p class="news-summary">{summary}</p>' if summary else ''}
      <div class="news-footer">
        {f'<span class="news-time">{pub}</span>' if pub else ''}
        {stock_tags}{sector_tags}
      </div>
    </article>"""


def generate_html(data: dict, generated_at: datetime) -> str:
    now_ist = generated_at.astimezone(IST).strftime("%d %b %Y, %H:%M IST")
    now_syd = generated_at.astimezone(SYDNEY).strftime("%d %b %Y, %H:%M AEST")

    # Macro section — show sector tags so reader sees which sectors are in play
    for item in data["macro"]:
        item["_show_sector_tags"] = True
    macro_html = (
        "".join(item_html(i) for i in data["macro"][:25])
        or "<p class='empty'>No macro news in last 24h.</p>"
    )

    # Sector sections
    sector_blocks = ""
    for sec_name, color in SECTOR_COLORS.items():
        items = data["sectors"].get(sec_name, [])
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
        if data["sectors"].get(s)
    )

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
    .updated{{color:var(--muted);font-size:12px;}}
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
                border:1px solid var(--border);transition:border-color .15s;}}
    .news-item:hover{{border-color:#3a4060;}}
    .news-title{{color:var(--link);text-decoration:none;font-weight:500;
                 font-size:13.5px;display:block;margin-bottom:4px;line-height:1.4;}}
    .news-title:hover{{color:var(--link-hover);text-decoration:underline;}}
    .news-summary{{color:var(--muted);font-size:12px;margin-bottom:6px;}}
    .news-footer{{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-top:6px;}}
    .news-time{{font-size:11px;color:#5a6480;margin-right:4px;}}

    .tags{{display:flex;flex-wrap:wrap;gap:4px;}}
    .tag{{font-size:11px;padding:2px 7px;border-radius:10px;font-weight:500;white-space:nowrap;}}
    .tag-stock{{background:#1e2a3a;color:#90caf9;border:1px solid #2a4060;}}
    .tag-sector{{background:transparent;color:var(--muted);border:1px solid;}}

    .empty{{color:var(--muted);font-style:italic;font-size:13px;}}
    footer{{text-align:center;color:var(--muted);font-size:11px;
            padding:32px 16px;border-top:1px solid var(--border);margin-top:40px;}}
  </style>
</head>
<body>
  <header>
    <div class="logo">India <span>Market Digest</span></div>
    <div class="updated">Updated {now_syd} &nbsp;·&nbsp; {now_ist}</div>
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
    India Market Digest · F&amp;O stocks · News since last NSE close · Auto-updated 10am AEST daily<br/>
    Sources: Economic Times · Business Standard · Moneycontrol · LiveMint
  </footer>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Fetching news…", file=sys.stderr)
    data = fetch_all_news(hours_back=24)
    print(f"  Macro: {len(data['macro'])} items", file=sys.stderr)
    for sec in STOCKS:
        n = len(data["sectors"].get(sec, []))
        if n:
            print(f"  {sec}: {n} items", file=sys.stderr)

    html = generate_html(data, datetime.now(timezone.utc))
    out  = Path("docs/index.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Written → {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
