"""Central watchlist -- single source of truth for all adapters.

ALL adapters import from here. Never hardcode tickers in adapters.

Signal Tier routing (added May 5 2026):
    HIGH/EXTREME D-value signals on sector ETFs route to 3x leveraged equivalents.
    The LEVERAGED_ETF_MAP in trade_advisor.py handles the routing.
    Bull and bear leveraged ETFs are both tracked here for OHLCV and price context.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Individual equities
# ---------------------------------------------------------------------------
CORE_STOCKS: list[str] = [
    # Mega-cap tech
    "AAPL", "NVDA", "TSLA", "AMD",  "AMZN", "MSFT", "META",
    "GOOG", "GOOGL","ARM",  "AVGO", "NOW",  "QCOM", "NFLX",
    # High-activity retail/meme
    "PLTR", "GME",  "AMC",  "MSTR", "COIN", "HOOD", "RBLX",
    "SNAP", "SHOP", "SQ",   "UBER", "LYFT",
    # Semis
    "INTC", "SMCI", "SNDK", "MU",   "KLAC", "TXN",
    # Finance
    "BAC",  "JPM",  "GS",   "MS",   "V",    "MA",   "SOFI",
    # Healthcare / pharma
    "LLY",  "UNH",  "PFE",  "MRK",  "ABBV", "JNJ",
    # Biotech / PDUFA candidates
    "VRDN", "PTGX", "SNDX", "INCY", "REGN", "ALNY", "KROS", "NTRA",
    # Consumer / retail
    "COST", "WMT",  "TGT",
    # Energy
    "XOM",  "CVX",
    # Defense / gov contract
    "NOC",  "LMT",  "RTX",  "PANW",
    # Enterprise tech
    "ORCL", "IBM",  "ADBE", "CTSH", "IT",
    # Other
    "F",    "BE",   "IONQ", "CVNA", "PYPL",
]

# ---------------------------------------------------------------------------
# ETF universe
# ---------------------------------------------------------------------------
BROAD_ETFS: list[str] = [
    "SPY",  # S&P 500
    "QQQ",  # Nasdaq 100
    "IWM",  # Russell 2000
    "DIA",  # Dow Jones
    "VTI",  # Total market
]

SECTOR_ETFS: list[str] = [
    "XLK",  # Technology
    "XLF",  # Financials
    "XLE",  # Energy
    "XLV",  # Health Care
    "XLI",  # Industrials
    "XLB",  # Materials
    "XLU",  # Utilities
    "XLRE", # Real Estate
    "XLC",  # Communication Services
    "XLY",  # Consumer Discretionary
    "XLP",  # Consumer Staples
]

THEMATIC_ETFS: list[str] = [
    "SMH",  # Semiconductors (VanEck)
    "SOXX", # Semiconductors (iShares)
    "XBI",  # Biotech
    "IBB",  # Biotech (iShares)
    "ARKK", # Innovation (Cathie Wood)
    "KWEB", # China internet
    "FINX", # Fintech
    "GDX",  # Gold miners
    "OIH",  # Oil services
    # -- Leveraged ETFs (bull) ------------------------------------------------
    "TQQQ", # 3x long Nasdaq 100
    "UPRO", # 3x long S&P 500
    "SOXL", # 3x long Semiconductors
    "TNA",  # 3x long Russell 2000
    "LABU", # 3x long Biotech
    "FAS",  # 3x long Financials
    "ERX",  # 3x long Energy
    "NUGT", # 3x long Gold Miners
    # -- Leveraged ETFs (bear) ------------------------------------------------
    "SQQQ", # 3x short Nasdaq 100
    "SPXS", # 3x short S&P 500
    "SOXS", # 3x short Semiconductors
    "TZA",  # 3x short Russell 2000
    "LABD", # 3x short Biotech
    "FAZ",  # 3x short Financials  <-- key for XLF SHORT D=38.9 signal
    "ERY",  # 3x short Energy
    "DUST", # 3x short Gold Miners
]

COMMODITY_ETFS: list[str] = [
    "GLD",  # Gold
    "IAU",  # Gold (iShares)
    "SLV",  # Silver
    "USO",  # Oil (WTI)
    "UNG",  # Natural gas
    "WEAT", # Wheat
    "CORN", # Corn
    "PDBC", # Broad commodities
    "DJP",  # Bloomberg Commodity Index
]

INTERNATIONAL_ETFS: list[str] = [
    "EEM",  # Emerging Markets
    "EWJ",  # Japan
    "FXI",  # China large cap
    "EWZ",  # Brazil
    "EWG",  # Germany
    "EWU",  # UK
    "EWY",  # South Korea
    "INDA", # India
    "MCHI", # MSCI China
]

MACRO_ETFS: list[str] = [
    "TLT",  # 20yr Treasury
    "HYG",  # High yield bonds
    "LQD",  # Investment grade bonds
    "UUP",  # Dollar index (DXY proxy)
    "UVXY", # VIX (short-term volatility)
    "SVXY", # Inverse VIX
]

# ---------------------------------------------------------------------------
# Full universe
# ---------------------------------------------------------------------------
FULL_WATCHLIST: list[str] = list(dict.fromkeys(
    CORE_STOCKS +
    BROAD_ETFS +
    SECTOR_ETFS +
    THEMATIC_ETFS +
    COMMODITY_ETFS +
    INTERNATIONAL_ETFS +
    MACRO_ETFS
))

# ---------------------------------------------------------------------------
# Sector constituent map
# ---------------------------------------------------------------------------
SECTOR_CONSTITUENTS: dict[str, list[str]] = {
    "XLK": ["AAPL", "NVDA", "MSFT", "AVGO", "AMD", "QCOM", "NOW", "INTC"],
    "XLF": ["JPM", "BAC", "V", "MA", "GS", "MS", "SOFI"],
    "XLE": ["XOM", "CVX", "OIH"],
    "XLV": ["LLY", "UNH", "PFE", "MRK", "ABBV", "JNJ"],
    "XLI": ["GE", "HON", "UPS", "BA", "CAT"],
    "XLB": ["LIN", "APD", "NEM", "FCX", "NUE"],
    "XLU": ["NEE", "DUK", "SO", "AEP", "SRE"],
    "XLRE": ["PLD", "AMT", "EQIX", "PSA", "SPG"],
    "XLC": ["META", "GOOG", "GOOGL", "NFLX", "T", "VZ"],
    "XLY": ["AMZN", "TSLA", "HD", "MCD", "NKE", "COST", "TGT"],
    "XLP": ["PG", "KO", "PEP", "COST", "WMT", "PM"],
    # Thematic
    "SMH":  ["NVDA", "AVGO", "AMD", "QCOM", "INTC", "SMCI", "ARM"],
    "SOXX": ["NVDA", "AMD", "AVGO", "QCOM", "INTC", "ARM"],
    "XBI":  ["ABBV", "MRK", "PFE", "LLY", "REGN", "VRTX"],
    "IBB":  ["ABBV", "MRK", "PFE", "LLY", "AMGN", "GILD"],
    "ARKK": ["TSLA", "COIN", "RBLX", "SHOP", "HOOD"],
    "KWEB": ["MCHI", "FXI"],
    "FINX": ["SOFI", "SQ", "V", "MA"],
    "GDX":  ["GLD", "IAU"],
    "OIH":  ["XOM", "CVX"],
    "GLD":  [],
    "SLV":  [],
    "USO":  ["XOM", "CVX"],
    "UNG":  [],
    "EEM":  ["MCHI", "EWJ", "EWZ", "EWY", "INDA", "FXI"],
    "FXI":  ["MCHI"],
    "MCHI": ["KWEB"],
    "HYG":  [],
    "TLT":  [],
    "UUP":  [],
    "UVXY": [],
}

# Tickers that generate high options flow signal
OPTIONS_WATCHLIST: list[str] = list(dict.fromkeys(
    CORE_STOCKS + BROAD_ETFS + SECTOR_ETFS +
    ["SMH", "GDX", "GLD", "SLV", "TLT", "HYG", "XBI",
     "TQQQ", "SQQQ", "SOXL", "SOXS", "UPRO", "SPXS",
     "USO", "EEM", "QQQ",
     "SPX", "SPXW",  # S&P 500 index options — highest volume
    ]
))

# Tickers for news/social sentiment (no pure commodity/macro ETFs)
SENTIMENT_WATCHLIST: list[str] = CORE_STOCKS + BROAD_ETFS + SECTOR_ETFS

# Tickers for congressional trade monitoring
CONGRESS_WATCHLIST: list[str] = CORE_STOCKS + BROAD_ETFS + SECTOR_ETFS

# Cold-start fallback
SEED_WATCHLIST: list[str] = [
    "SPY", "QQQ", "NVDA", "TSLA", "AAPL",
    "MSFT", "AMD", "META", "GOOGL", "AMZN",
    "NFLX", "COIN", "PLTR", "SMCI", "AVGO",
    "IWM", "GLD", "TLT", "UVXY", "XLK",
]


def resolve_watchlist(module_id: str = "stocks", size: int = 20) -> list[str]:
    """Prefer dynamic top-N; fall back to seed if DB is cold."""
    from alphahound.modules.stocks.watchlist._dynamic import top_mentioned
    tickers = top_mentioned(module_id=module_id, size=size)
    if tickers:
        return tickers
    return SEED_WATCHLIST[:size]
