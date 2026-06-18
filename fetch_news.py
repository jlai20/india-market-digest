#!/usr/bin/env python3
"""Fetch Indian market news from RSS feeds and generate HTML dashboard."""

import feedparser
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from email.utils import parsedate_to_datetime

# ── Timezone ──────────────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))
SYDNEY = timezone(timedelta(hours=10))  # AEST; script runs ~10am Sydney

# ── NSE Sectors (Nifty 50 weight order) ──────────────────────────────────────
SECTORS = [
    {
        "name": "Financials & Banking",
        "weight": "~33%",
        "color": "#1a73e8",
        "stocks": [
            "HDFC Bank", "HDFCBANK", "ICICI Bank", "ICICIBANK", "SBI", "SBIN",
            "Kotak Mahindra", "KOTAKBANK", "Axis Bank", "AXISBANK",
            "Bajaj Finance", "BAJFINANCE", "HDFC Life", "HDFCLIFE",
            "SBI Life", "SBILIFE", "Bajaj Finserv", "BAJAJFINSV",
            "IndusInd Bank", "INDUSINDBK", "Federal Bank", "FEDERALBNK",
            "Bandhan Bank", "BANDHANBNK", "ICICI Prudential", "ICICIPRULIFE",
            "AU Small Finance", "AUBANK", "CSB Bank", "CSBBANK",
            "RBL Bank", "RBLBANK", "Karnataka Bank", "KTKBANK",
        ],
        "keywords": [
            "bank", "banking", "NBFC", "insurance", "credit", "loan", "NPA",
            "fintech", "mutual fund", "AMC", "Nifty Bank", "repo rate",
            "interest rate", "financial services", "microfinance", "MFI",
        ],
    },
    {
        "name": "IT & Technology",
        "weight": "~13%",
        "color": "#0f9d58",
        "stocks": [
            "TCS", "Infosys", "INFY", "Wipro", "HCL Tech", "HCLTECH",
            "Tech Mahindra", "TECHM", "Persistent Systems", "PERSISTENT",
            "Coforge", "COFORGE", "Mphasis", "MPHASIS", "LTIMindtree", "LTIM",
            "Hexaware", "Oracle Financial", "OFSS", "Mastek", "MASTECH",
            "Cyient", "CYIENT", "Birlasoft", "BSOFT", "KPIT Technologies", "KPITTECH",
        ],
        "keywords": [
            "IT sector", "software", "technology", "digital transformation",
            "AI", "artificial intelligence", "cloud", "outsourcing", "NASSCOM",
            "tech company", "SaaS", "Nifty IT", "data center", "cybersecurity",
        ],
    },
    {
        "name": "Oil, Gas & Energy",
        "weight": "~12%",
        "color": "#f57c00",
        "stocks": [
            "Reliance Industries", "RELIANCE", "ONGC", "BPCL", "IOC", "Indian Oil",
            "Petronet LNG", "PETRONET", "Oil India", "GAIL", "HINDPETRO",
            "MRPL", "Gujarat Gas", "GUJGAS", "IGL", "Indraprastha Gas",
            "MGL", "Adani Total Gas", "ATGL", "Adani Green", "ADANIGREEN",
            "Tata Power", "TATAPOWER", "NHPC", "SJVN", "Torrent Power", "TORNTPOWER",
        ],
        "keywords": [
            "crude oil", "petroleum", "refinery", "natural gas", "LNG",
            "OPEC", "petrol", "diesel", "fuel price", "oil price",
            "Nifty Energy", "renewable energy", "solar", "wind energy", "power sector",
        ],
    },
    {
        "name": "Automobiles",
        "weight": "~7%",
        "color": "#7b1fa2",
        "stocks": [
            "Maruti Suzuki", "MARUTI", "Tata Motors", "TATAMOTORS",
            "Mahindra", "M&M", "MAHINDRA", "Bajaj Auto", "BAJAJAUTO",
            "Hero MotoCorp", "HEROMOTOCO", "Eicher Motors", "EICHERMOT",
            "TVS Motor", "TVSMOTOR", "Ashok Leyland", "ASHOKLEY",
            "Apollo Tyres", "APOLLOTYRE", "MRF", "MRFLTD", "Bosch", "BOSCHLTD",
            "Bharat Forge", "BHARATFORG", "Motherson", "MOTHERSON", "Samvardhana",
        ],
        "keywords": [
            "automobile", "EV", "electric vehicle", "vehicle sales",
            "auto sector", "passenger vehicle", "two-wheeler", "commercial vehicle",
            "Nifty Auto", "car sales", "SUV", "auto OEM", "PLI auto",
        ],
    },
    {
        "name": "FMCG & Consumer",
        "weight": "~8%",
        "color": "#e91e63",
        "stocks": [
            "HUL", "Hindustan Unilever", "ITC", "Nestle", "NESTLEIND",
            "Britannia", "BRITANNIA", "Dabur", "DABUR", "Marico", "MARICO",
            "Godrej Consumer", "GODREJCP", "Emami", "EMAMILTD", "Colgate", "COLPAL",
            "United Spirits", "Tata Consumer", "TATACONSUM",
            "Avenue Supermarts", "DMART", "Varun Beverages", "VBL",
            "Patanjali Foods", "PATANJALI", "Zomato", "ZOMATO", "Swiggy", "SWIGGY",
        ],
        "keywords": [
            "FMCG", "consumer goods", "retail", "rural demand", "urban consumption",
            "food inflation", "packaged food", "Nifty FMCG", "QSR",
            "quick service restaurant", "food delivery", "e-commerce",
        ],
    },
    {
        "name": "Healthcare & Pharma",
        "weight": "~5%",
        "color": "#00838f",
        "stocks": [
            "Sun Pharma", "SUNPHARMA", "Dr Reddy", "DRREDDY", "Cipla", "CIPLA",
            "Divi's Laboratories", "DIVISLAB", "Aurobindo", "AUROPHARMA",
            "Lupin", "LUPIN", "Torrent Pharma", "TORNTPHARM",
            "Apollo Hospitals", "APOLLOHOSP", "Fortis Healthcare", "FORTIS",
            "Max Healthcare", "MAXHEALTH", "Alkem", "ALKEM",
            "Mankind Pharma", "MANKIND", "Gland Pharma", "GLAND",
            "Biocon", "BIOCON", "Natco Pharma", "NATCOPHARM",
        ],
        "keywords": [
            "pharma", "healthcare", "drug", "USFDA", "FDA", "ANDA",
            "clinical trial", "biosimilar", "generic drug", "hospital",
            "medical", "Nifty Pharma", "health ministry", "API",
        ],
    },
    {
        "name": "Metals & Mining",
        "weight": "~6%",
        "color": "#5d4037",
        "stocks": [
            "Tata Steel", "TATASTEEL", "JSW Steel", "JSWSTEEL",
            "Hindalco", "HINDALCO", "Vedanta", "VEDL", "SAIL",
            "NMDC", "Coal India", "COALINDIA", "JSPL", "Jindal Steel",
            "National Aluminium", "NATIONALUM", "Hindustan Zinc", "HINDZINC",
            "APL Apollo Tubes", "APLAPOLLO", "Welspun Corp", "WELCORP",
        ],
        "keywords": [
            "steel", "aluminum", "aluminium", "copper", "zinc", "iron ore",
            "coal", "metal", "mining", "commodity", "Nifty Metal",
            "LME", "scrap", "coking coal",
        ],
    },
    {
        "name": "Capital Goods & Defence",
        "weight": "~5%",
        "color": "#37474f",
        "stocks": [
            "L&T", "Larsen & Toubro", "LT", "Siemens", "SIEMENS",
            "ABB India", "ABB", "Bharat Electronics", "BEL",
            "BHEL", "HAL", "Hindustan Aeronautics", "Cochin Shipyard", "COCHINSHIP",
            "Power Grid", "POWERGRID", "NTPC", "Adani Ports", "ADANIPORTS",
            "Container Corp", "CONCOR", "IRB Infra", "IRB",
            "KEC International", "KECL", "Cummins", "CUMMINSIND",
            "Thermax", "THERMAX", "Data Patterns", "DATAPATTNS",
        ],
        "keywords": [
            "infrastructure", "capital goods", "defence", "defense", "power",
            "electricity grid", "PLI scheme", "manufacturing", "Make in India",
            "order book", "Nifty Infra", "capex", "EPC", "shipbuilding",
        ],
    },
    {
        "name": "Telecom & Media",
        "weight": "~3%",
        "color": "#283593",
        "stocks": [
            "Bharti Airtel", "BHARTIARTL", "Reliance Jio", "BSNL",
            "Vodafone Idea", "IDEA", "Indus Towers", "INDUSTOWER",
            "Tata Communications", "TATACOMM", "Zee Entertainment", "ZEEL",
            "Sun TV Network", "SUNTV", "PVR INOX", "PVRINOX",
        ],
        "keywords": [
            "telecom", "5G", "spectrum auction", "ARPU", "subscriber",
            "broadband", "OTT", "streaming", "media", "Nifty Telecom",
            "AGR", "TRAI",
        ],
    },
    {
        "name": "Real Estate & REITs",
        "weight": "~2%",
        "color": "#c62828",
        "stocks": [
            "DLF", "Godrej Properties", "GODREJPROP", "Prestige Estates", "PRESTIGE",
            "Oberoi Realty", "OBEROIRLTY", "Phoenix Mills", "PHOENIXLTD",
            "Brigade Enterprises", "BRIGADE", "Sobha", "SOBHA",
            "Embassy REIT", "Mindspace REIT", "Nexus Select", "NEXUS",
            "Macrotech", "LODHA", "Signature Global", "SIGNATURE",
        ],
        "keywords": [
            "real estate", "realty", "housing", "property market", "REIT",
            "residential project", "commercial property", "Nifty Realty",
            "home loan", "affordable housing", "RERA", "stamp duty",
        ],
    },
]

MACRO_KEYWORDS = [
    "RBI", "Reserve Bank of India", "rupee", "INR", "USD/INR", "forex reserve",
    "GDP", "inflation", "CPI", "WPI", "IIP", "PMI", "trade deficit",
    "current account deficit", "fiscal deficit", "Union Budget", "GST collection",
    "trade deal", "FTA", "free trade agreement", "tariff", "WTO", "IMF", "World Bank",
    "geopolitics", "sanctions", "war", "ceasefire", "conflict",
    "US-India", "China-India", "Pakistan", "border tension", "LAC",
    "Nifty 50", "Sensex", "NSE", "BSE", "FII", "FPI", "DII", "FDI",
    "repo rate", "MPC", "monetary policy", "rate cut", "rate hike",
    "OPEC", "US Fed", "Federal Reserve", "dollar index", "DXY",
]

RSS_FEEDS = [
    # Economic Times
    "https://economictimes.indiatimes.com/markets/stocks/news/rssfeeds/2146842.cms",
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://economictimes.indiatimes.com/economy/rssfeeds/1373380680.cms",
    "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
    # Business Standard
    "https://www.business-standard.com/rss/markets-106.rss",
    "https://www.business-standard.com/rss/economy-policy-102.rss",
    "https://www.business-standard.com/rss/finance-113.rss",
    # Moneycontrol
    "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "https://www.moneycontrol.com/rss/marketreports.xml",
    # LiveMint
    "https://www.livemint.com/rss/markets",
    "https://www.livemint.com/rss/economy",
    "https://www.livemint.com/rss/companies",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def text_matches(text: str, terms: list[str]) -> bool:
    text_lower = text.lower()
    return any(t.lower() in text_lower for t in terms)


def classify_item(title: str, summary: str) -> list[str]:
    """Return list of sector names this item belongs to (may be multiple)."""
    combined = f"{title} {summary}"
    matched = []
    for sector in SECTORS:
        if text_matches(combined, sector["stocks"]) or text_matches(combined, sector["keywords"]):
            matched.append(sector["name"])
    return matched


def is_macro(title: str, summary: str) -> bool:
    return text_matches(f"{title} {summary}", MACRO_KEYWORDS)


def parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            import time
            return datetime(*val[:6], tzinfo=timezone.utc)
    # try string parse
    for attr in ("published", "updated"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return parsedate_to_datetime(val).astimezone(timezone.utc)
            except Exception:
                pass
    return None


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def fetch_all_news(hours_back: int = 24) -> dict:
    """Fetch RSS feeds and return categorised news dict."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    seen_titles: set[str] = set()

    macro_items: list[dict] = []
    sector_items: dict[str, list[dict]] = {s["name"]: [] for s in SECTORS}
    uncategorised: list[dict] = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"Warning: failed to fetch {url}: {e}", file=sys.stderr)
            continue

        for entry in feed.entries:
            title = strip_html(entry.get("title", "")).strip()
            if not title or title in seen_titles:
                continue

            pub = parse_date(entry)
            if pub and pub < cutoff:
                continue

            seen_titles.add(title)
            link = entry.get("link", "#")
            summary = strip_html(entry.get("summary", ""))[:300]
            pub_str = pub.astimezone(IST).strftime("%d %b %H:%M IST") if pub else ""

            item = {"title": title, "link": link, "summary": summary, "pub": pub_str, "pub_dt": pub}

            sectors_matched = classify_item(title, summary)
            macro = is_macro(title, summary)

            if macro:
                macro_items.append(item)
            for sec in sectors_matched:
                sector_items[sec].append(item)
            if not macro and not sectors_matched:
                uncategorised.append(item)

    # sort each bucket newest-first
    def sort_key(i):
        return i["pub_dt"] or datetime.min.replace(tzinfo=timezone.utc)

    macro_items.sort(key=sort_key, reverse=True)
    for k in sector_items:
        sector_items[k].sort(key=sort_key, reverse=True)

    return {"macro": macro_items, "sectors": sector_items, "uncategorised": uncategorised}


# ── HTML generation ───────────────────────────────────────────────────────────

def item_html(item: dict) -> str:
    title = item["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    summary = item["summary"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    pub = item["pub"]
    link = item["link"].replace('"', "%22")
    return f"""
    <article class="news-item">
      <a href="{link}" target="_blank" rel="noopener noreferrer" class="news-title">{title}</a>
      {f'<p class="news-summary">{summary}</p>' if summary else ''}
      {f'<span class="news-time">{pub}</span>' if pub else ''}
    </article>"""


def generate_html(data: dict, generated_at: datetime) -> str:
    now_ist = generated_at.astimezone(IST).strftime("%d %b %Y, %H:%M IST")
    now_syd = generated_at.astimezone(SYDNEY).strftime("%d %b %Y, %H:%M AEST")

    macro_html = "".join(item_html(i) for i in data["macro"][:20]) or "<p class='empty'>No macro news in last 24h.</p>"

    sector_blocks = ""
    for sector in SECTORS:
        items = data["sectors"].get(sector["name"], [])
        if not items:
            continue
        items_html = "".join(item_html(i) for i in items[:12])
        sector_blocks += f"""
    <section class="sector-card" id="{sector['name'].replace(' ', '-').lower()}">
      <div class="sector-header" style="border-left: 4px solid {sector['color']}">
        <span class="sector-name">{sector['name']}</span>
        <span class="sector-badge">{sector['weight']} of Nifty&nbsp;50</span>
        <span class="sector-count">{len(items)} stories</span>
      </div>
      <div class="news-list">{items_html}</div>
    </section>"""

    nav_items = "".join(
        f'<a href="#{s["name"].replace(" ", "-").lower()}" style="border-color:{s["color"]}">{s["name"]}</a>'
        for s in SECTORS if data["sectors"].get(s["name"])
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>India Market Digest</title>
  <style>
    :root {{
      --bg: #0f1117;
      --surface: #1a1d27;
      --surface2: #22263a;
      --text: #e8eaf0;
      --muted: #8892a4;
      --accent: #ff6b35;
      --macro-color: #ffd700;
      --border: #2a2f42;
      --link: #64b5f6;
      --link-hover: #90caf9;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      font-size: 14px;
      line-height: 1.6;
    }}
    header {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 16px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    .logo {{
      font-size: 20px;
      font-weight: 700;
      color: var(--accent);
      letter-spacing: -0.5px;
    }}
    .logo span {{ color: var(--text); }}
    .updated {{
      color: var(--muted);
      font-size: 12px;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 20px 16px; }}

    /* Nav */
    .sector-nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 24px;
      padding: 16px;
      background: var(--surface);
      border-radius: 8px;
      border: 1px solid var(--border);
    }}
    .sector-nav a {{
      color: var(--text);
      text-decoration: none;
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 4px;
      border: 1px solid;
      opacity: 0.8;
      transition: opacity 0.15s;
    }}
    .sector-nav a:hover {{ opacity: 1; background: var(--surface2); }}

    /* Macro section */
    .macro-section {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-top: 3px solid var(--macro-color);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    .macro-title {{
      font-size: 16px;
      font-weight: 700;
      color: var(--macro-color);
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .macro-title::before {{ content: "◆"; font-size: 10px; }}

    /* Sector cards */
    .sector-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 20px;
    }}
    .sector-header {{
      display: flex;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 16px;
      padding-left: 12px;
      flex-wrap: wrap;
    }}
    .sector-name {{
      font-size: 16px;
      font-weight: 700;
    }}
    .sector-badge {{
      font-size: 11px;
      color: var(--muted);
      background: var(--surface2);
      padding: 2px 8px;
      border-radius: 10px;
    }}
    .sector-count {{
      font-size: 11px;
      color: var(--muted);
      margin-left: auto;
    }}

    /* News items */
    .news-list {{ display: flex; flex-direction: column; gap: 12px; }}
    .news-item {{
      padding: 12px;
      background: var(--surface2);
      border-radius: 6px;
      border: 1px solid var(--border);
      transition: border-color 0.15s;
    }}
    .news-item:hover {{ border-color: #3a4060; }}
    .news-title {{
      color: var(--link);
      text-decoration: none;
      font-weight: 500;
      font-size: 13.5px;
      display: block;
      margin-bottom: 4px;
      line-height: 1.4;
    }}
    .news-title:hover {{ color: var(--link-hover); text-decoration: underline; }}
    .news-summary {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .news-time {{
      font-size: 11px;
      color: #5a6480;
    }}
    .empty {{ color: var(--muted); font-style: italic; font-size: 13px; }}

    footer {{
      text-align: center;
      color: var(--muted);
      font-size: 11px;
      padding: 32px 16px;
      border-top: 1px solid var(--border);
      margin-top: 40px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="logo">India <span>Market Digest</span></div>
    <div class="updated">Updated {now_syd} &nbsp;·&nbsp; {now_ist}</div>
  </header>
  <div class="container">
    <nav class="sector-nav" aria-label="Jump to sector">
      <a href="#macro" style="border-color:#ffd700">Macro</a>
      {nav_items}
    </nav>

    <section class="macro-section" id="macro">
      <div class="macro-title">Indian Macro &amp; Geopolitics</div>
      <div class="news-list">{macro_html}</div>
    </section>

    {sector_blocks}
  </div>
  <footer>
    India Market Digest · F&amp;O stocks only · News since last NSE close · Auto-updated 10am AEST daily<br/>
    Sources: Economic Times · Business Standard · Moneycontrol · LiveMint
  </footer>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("Fetching news feeds...", file=sys.stderr)
    data = fetch_all_news(hours_back=24)
    print(f"  Macro: {len(data['macro'])} items", file=sys.stderr)
    for s in SECTORS:
        n = len(data["sectors"].get(s["name"], []))
        if n:
            print(f"  {s['name']}: {n} items", file=sys.stderr)

    html = generate_html(data, datetime.now(timezone.utc))
    out = Path("docs/index.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Written to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
