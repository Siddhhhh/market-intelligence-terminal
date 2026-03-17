"""
Market Intelligence Terminal — Database Models

All SQLAlchemy table definitions for the system.

Tables:
    - sectors           GICS sectors (Technology, Energy, etc.)
    - companies         S&P 500 + global companies
    - stocks            Daily OHLCV price data (TimescaleDB hypertable)
    - crypto_assets     Cryptocurrency definitions (BTC, ETH, SOL)
    - crypto_prices     Daily crypto OHLCV data (TimescaleDB hypertable)
    - market_events     Detected anomalies (crashes, spikes, volume)
    - macro_events      Macroeconomic indicators (rates, GDP, CPI)
    - market_regimes    Detected market environments (bull, bear, etc.)

TimescaleDB hypertables:
    stocks and crypto_prices are converted to hypertables after creation.
    This partitions them by date for fast time-range queries across 35+ years.
"""

from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Numeric,
    Text,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    UniqueConstraint,
    Index,
    JSON,
    text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


# ── Base ────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# ── Sectors ─────────────────────────────────────────────────

class Sector(Base):
    """
    GICS sectors: Technology, Energy, Financials, Healthcare, etc.
    Each company belongs to exactly one sector.
    """
    __tablename__ = "sectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, comment="Sector key: technology, energy, etc.")
    display_name = Column(String(100), nullable=False, comment="Human-readable: Technology, Energy, etc.")
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    # Relationships
    companies = relationship("Company", back_populates="sector", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Sector(id={self.id}, name='{self.name}')>"


# ── Companies ───────────────────────────────────────────────

class Company(Base):
    """
    Individual companies. Covers S&P 500 + additional global companies.

    Fields:
        ticker      Unique stock symbol (AAPL, NVDA, TSLA)
        name        Full company name
        sector_id   FK to sectors table
        industry    Sub-industry classification
        country     Country of headquarters
        market_cap  Latest market capitalization in USD
        is_sp500    Whether the company is in the S&P 500 index
        is_active   Whether we actively track this company
    """
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=True)
    industry = Column(String(255), nullable=True)
    country = Column(String(100), server_default=text("'US'"), nullable=False)
    market_cap = Column(BigInteger, nullable=True, comment="Market cap in USD")
    is_sp500 = Column(Boolean, server_default=text("FALSE"), nullable=False)
    is_active = Column(Boolean, server_default=text("TRUE"), nullable=False)
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    # Relationships
    sector = relationship("Sector", back_populates="companies", lazy="selectin")
    stock_prices = relationship("Stock", back_populates="company", lazy="noload")

    def __repr__(self) -> str:
        return f"<Company(ticker='{self.ticker}', name='{self.name}')>"


# ── Stocks (TimescaleDB Hypertable) ────────────────────────

class Stock(Base):
    """
    Daily stock price data. OHLCV + percent change.

    This table is converted to a TimescaleDB hypertable partitioned
    by the `date` column. This makes range queries extremely fast
    even across 35+ years x 500 companies (~4.5 million rows).

    Composite primary key: (date, company_id)
    """
    __tablename__ = "stocks"

    date = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    open = Column(Numeric(12, 4), nullable=True)
    high = Column(Numeric(12, 4), nullable=True)
    low = Column(Numeric(12, 4), nullable=True)
    close = Column(Numeric(12, 4), nullable=False)
    volume = Column(BigInteger, nullable=True)
    pct_change = Column(Numeric(8, 4), nullable=True, comment="Daily percent change")

    # Relationships
    company = relationship("Company", back_populates="stock_prices", lazy="selectin")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_stocks_company_date", "company_id", "date"),
        Index("idx_stocks_date", "date"),
        Index("idx_stocks_pct_change", "pct_change"),
    )

    def __repr__(self) -> str:
        return f"<Stock(company_id={self.company_id}, date='{self.date}', close={self.close})>"


# ── Crypto Assets ───────────────────────────────────────────

class CryptoAsset(Base):
    """
    Cryptocurrency definitions. Currently: BTC, ETH, SOL.

    Fields:
        symbol          Trading symbol (BTC, ETH, SOL)
        name            Full name (Bitcoin, Ethereum, Solana)
        coingecko_id    CoinGecko API identifier for data fetching
    """
    __tablename__ = "crypto_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    coingecko_id = Column(String(100), unique=True, nullable=False, comment="CoinGecko API ID")
    is_active = Column(Boolean, server_default=text("TRUE"), nullable=False)
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    # Relationships
    prices = relationship("CryptoPrice", back_populates="crypto_asset", lazy="noload")

    def __repr__(self) -> str:
        return f"<CryptoAsset(symbol='{self.symbol}', name='{self.name}')>"


# ── Crypto Prices (TimescaleDB Hypertable) ──────────────────

class CryptoPrice(Base):
    """
    Daily cryptocurrency price data. OHLCV + market cap + percent change.

    Converted to TimescaleDB hypertable like stocks.
    Composite primary key: (date, crypto_id)
    """
    __tablename__ = "crypto_prices"

    date = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    crypto_id = Column(
        Integer,
        ForeignKey("crypto_assets.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    open = Column(Numeric(16, 4), nullable=True)
    high = Column(Numeric(16, 4), nullable=True)
    low = Column(Numeric(16, 4), nullable=True)
    close = Column(Numeric(16, 4), nullable=False)
    volume_usd = Column(Numeric(20, 2), nullable=True, comment="24h trading volume in USD")
    market_cap_usd = Column(Numeric(20, 2), nullable=True, comment="Market cap in USD")
    pct_change = Column(Numeric(8, 4), nullable=True, comment="Daily percent change")

    # Relationships
    crypto_asset = relationship("CryptoAsset", back_populates="prices", lazy="selectin")

    # Indexes
    __table_args__ = (
        Index("idx_crypto_prices_asset_date", "crypto_id", "date"),
        Index("idx_crypto_prices_date", "date"),
        Index("idx_crypto_prices_pct_change", "pct_change"),
    )

    def __repr__(self) -> str:
        return f"<CryptoPrice(crypto_id={self.crypto_id}, date='{self.date}', close={self.close})>"


# ── Market Events ───────────────────────────────────────────

class MarketEvent(Base):
    """
    Detected market anomalies and significant events.

    Event types:
        price_spike     Single stock rose > 8% in one day
        price_crash     Single stock fell > 8% in one day
        volume_anomaly  Volume > 3x the 20-day average
        sector_move     5+ companies in same sector moving > 3% same direction
        market_crash    20+ companies dropping > 5% on the same day

    Severity levels: low, medium, high, critical

    entity_type: 'stock' or 'crypto'
    entity_id:   FK to companies.id or crypto_assets.id
    """
    __tablename__ = "market_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    event_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="price_spike, price_crash, volume_anomaly, sector_move, market_crash",
    )
    severity = Column(
        String(20),
        nullable=False,
        server_default=text("'medium'"),
        comment="low, medium, high, critical",
    )
    entity_type = Column(
        String(20),
        nullable=True,
        comment="stock or crypto",
    )
    entity_id = Column(Integer, nullable=True, comment="FK to companies.id or crypto_assets.id")
    ticker = Column(String(20), nullable=True, index=True, comment="Denormalized for fast lookups")
    magnitude = Column(Numeric(10, 4), nullable=True, comment="Size of the move (percent)")
    description = Column(Text, nullable=True)
    extra_data = Column("metadata", JSON, nullable=True, comment="Extra context as JSON")
    detected_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_market_events_date_type", "date", "event_type"),
        Index("idx_market_events_entity", "entity_type", "entity_id"),
    )

    def __repr__(self) -> str:
        return f"<MarketEvent(date='{self.date}', type='{self.event_type}', ticker='{self.ticker}')>"


# ── Macro Events ────────────────────────────────────────────

class MacroEvent(Base):
    """
    Macroeconomic data points from FRED and other sources.

    Indicators:
        fed_funds_rate      Federal funds interest rate
        cpi                 Consumer Price Index (inflation)
        gdp_growth          GDP growth rate
        unemployment_rate   Unemployment rate
        treasury_10y        10-year Treasury yield
        vix                 CBOE Volatility Index

    Each row is one data point for one indicator on one date.
    """
    __tablename__ = "macro_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    indicator = Column(
        String(50),
        nullable=False,
        index=True,
        comment="fed_funds_rate, cpi, gdp_growth, unemployment_rate, etc.",
    )
    value = Column(Numeric(12, 4), nullable=False)
    previous_value = Column(Numeric(12, 4), nullable=True)
    change_pct = Column(Numeric(8, 4), nullable=True, comment="Change from previous value")
    source = Column(String(50), server_default=text("'FRED'"), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_macro_events_indicator_date", "indicator", "date"),
        UniqueConstraint("date", "indicator", name="uq_macro_date_indicator"),
    )

    def __repr__(self) -> str:
        return f"<MacroEvent(date='{self.date}', indicator='{self.indicator}', value={self.value})>"


# ── Market Regimes ──────────────────────────────────────────

class MarketRegime(Base):
    """
    Detected market environments / regimes.

    Regime types:
        bull_market         Sustained uptrend (index above 200-day MA, rising)
        bear_market         Sustained downtrend (index below 200-day MA, falling)
        high_volatility     VIX or rolling vol > 25
        low_volatility      VIX or rolling vol < 15
        sector_rotation     High dispersion between sector returns
        macro_shock         Sudden macro event (rate hike, crisis)

    Each regime has a start_date and end_date (NULL if still active).
    supporting_indicators stores the data that triggered detection.
    """
    __tablename__ = "market_regimes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    regime_type = Column(
        String(50),
        nullable=False,
        index=True,
        comment="bull_market, bear_market, high_volatility, etc.",
    )
    confidence = Column(Numeric(5, 4), nullable=False, comment="0.0 to 1.0")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True, comment="NULL if regime is still active")
    supporting_indicators = Column(JSON, nullable=True, comment="Data that triggered this detection")
    detected_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_regimes_type_dates", "regime_type", "start_date", "end_date"),
    )

    def __repr__(self) -> str:
        return f"<MarketRegime(type='{self.regime_type}', start='{self.start_date}')>"


# ── Sector Performance (Precomputed) ───────────────────────

class SectorPerformance(Base):
    """
    Precomputed daily sector performance.

    Populated by the sector performance engine during ingestion or daily updates.
    Eliminates expensive runtime aggregation across millions of stock rows.

    Composite primary key: (date, sector_id)
    """
    __tablename__ = "sector_performance"

    date = Column(Date, primary_key=True, nullable=False)
    sector_id = Column(
        Integer,
        ForeignKey("sectors.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    avg_pct_change = Column(Numeric(8, 4), nullable=False, comment="Average pct change of sector companies")
    company_count = Column(Integer, nullable=False, comment="Number of companies with data that day")
    total_volume = Column(BigInteger, nullable=True, comment="Total sector volume")
    top_gainer_ticker = Column(String(20), nullable=True)
    top_gainer_pct = Column(Numeric(8, 4), nullable=True)
    top_loser_ticker = Column(String(20), nullable=True)
    top_loser_pct = Column(Numeric(8, 4), nullable=True)
    computed_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_sector_perf_date", "date"),
        Index("idx_sector_perf_sector_date", "sector_id", "date"),
    )

    def __repr__(self) -> str:
        return f"<SectorPerformance(date='{self.date}', sector_id={self.sector_id}, avg={self.avg_pct_change})>"


# ── Daily Indicators (Precomputed) ─────────────────────────

class DailyIndicator(Base):
    """
    Precomputed technical indicators for each company per trading day.

    Computed offline by the indicator pipeline — NEVER at request time.
    Used by the Movement Attribution Engine for signal extraction.
    """
    __tablename__ = "daily_indicators"

    date = Column(Date, primary_key=True, nullable=False)
    company_id = Column(
        Integer,
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    ma20 = Column(Numeric(12, 4), nullable=True, comment="20-day simple moving average")
    ma50 = Column(Numeric(12, 4), nullable=True, comment="50-day simple moving average")
    ma200 = Column(Numeric(12, 4), nullable=True, comment="200-day simple moving average")
    rsi = Column(Numeric(8, 4), nullable=True, comment="14-day RSI (0-100)")
    macd = Column(Numeric(10, 4), nullable=True, comment="MACD line (12,26)")
    macd_signal = Column(Numeric(10, 4), nullable=True, comment="MACD signal line (9)")
    macd_histogram = Column(Numeric(10, 4), nullable=True, comment="MACD histogram")
    volatility_20d = Column(Numeric(8, 4), nullable=True, comment="20-day rolling stddev of returns")
    volume_ratio = Column(Numeric(8, 4), nullable=True, comment="Today volume / 20-day avg volume")
    trend_direction = Column(String(20), nullable=True, comment="bullish / bearish / neutral")
    computed_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    __table_args__ = (
        Index("idx_daily_ind_company_date", "company_id", "date"),
    )

    def __repr__(self) -> str:
        return f"<DailyIndicator(company_id={self.company_id}, date='{self.date}', rsi={self.rsi})>"


# ── Company Cache (Provider-backed) ────────────────────────

class CompanyCache(Base):
    """
    Cached company fundamentals from yfinance.

    Refreshed daily by the company data provider.
    Wraps yfinance so core logic never calls it directly.
    """
    __tablename__ = "company_cache"

    ticker = Column(String(20), primary_key=True, nullable=False)
    market_cap = Column(BigInteger, nullable=True)
    pe_ratio = Column(Numeric(10, 4), nullable=True)
    forward_pe = Column(Numeric(10, 4), nullable=True)
    revenue = Column(BigInteger, nullable=True)
    net_income = Column(BigInteger, nullable=True)
    profit_margin = Column(Numeric(8, 4), nullable=True)
    eps = Column(Numeric(10, 4), nullable=True)
    revenue_growth = Column(Numeric(8, 4), nullable=True)
    fifty_two_week_high = Column(Numeric(12, 4), nullable=True)
    fifty_two_week_low = Column(Numeric(12, 4), nullable=True)
    avg_volume = Column(BigInteger, nullable=True)
    top_holders = Column(JSON, nullable=True, comment="Array of {name, shares, pct}")
    updated_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    def __repr__(self) -> str:
        return f"<CompanyCache(ticker='{self.ticker}', pe={self.pe_ratio})>"


# ── Company Relationships (Graph Model) ────────────────────

class CompanyRelationship(Base):
    """
    Curated relationships between companies.
    Supplier, partner, competitor links.

    Labeled as estimated where data is approximated.
    """
    __tablename__ = "company_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    related_company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    relationship_type = Column(String(30), nullable=False, comment="supplier, partner, competitor")
    confidence_score = Column(Numeric(5, 4), nullable=False, comment="0.0 to 1.0")
    description = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_company_rel_company", "company_id"),
        Index("idx_company_rel_related", "related_company_id"),
    )

    def __repr__(self) -> str:
        return f"<CompanyRelationship(company={self.company_id}, related={self.related_company_id}, type='{self.relationship_type}')>"


# ── Movement Cache ─────────────────────────────────────────

class MovementCache(Base):
    """
    Cached movement explanation results.

    TTL: 6-12 hours. Avoids re-running the attribution engine
    for the same ticker+range within the cache window.
    """
    __tablename__ = "movement_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, index=True)
    range_period = Column(String(10), nullable=False, comment="1d, 7d, 30d")
    result_json = Column(JSON, nullable=False)
    generated_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    __table_args__ = (
        Index("idx_movement_cache_ticker_range", "ticker", "range_period"),
    )


# ── User Profiles ──────────────────────────────────────────

class UserProfile(Base):
    """
    User financial profile for investment intelligence.

    Temporary: uses demo_user_1 as default before auth integration.
    Stores risk tolerance and investment horizon for personalized scoring.
    """
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), unique=True, nullable=False, index=True, comment="demo_user_1 default")
    name = Column(String(100), nullable=False, default="Default User")
    risk_tolerance = Column(
        String(20), nullable=False, default="moderate",
        comment="conservative, moderate, aggressive",
    )
    investment_horizon = Column(
        String(20), nullable=False, default="medium",
        comment="short (< 1yr), medium (1-5yr), long (5yr+)",
    )
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    def __repr__(self) -> str:
        return f"<UserProfile(user_id='{self.user_id}', risk='{self.risk_tolerance}')>"


# ── Portfolio Holdings ─────────────────────────────────────

class PortfolioHolding(Base):
    """
    Individual portfolio position.

    Tracks buy price for P&L calculation. Current value computed
    at query time from the stocks table.

    Supports both stocks and crypto via asset_type field.
    """
    __tablename__ = "portfolio_holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, index=True, comment="FK to user_profiles.user_id")
    asset_type = Column(String(10), nullable=False, default="stock", comment="stock or crypto")
    ticker = Column(String(20), nullable=False)
    quantity = Column(Numeric(12, 4), nullable=False)
    avg_buy_price = Column(Numeric(12, 4), nullable=False)
    buy_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime, server_default=text("NOW()"), nullable=False)

    __table_args__ = (
        Index("idx_portfolio_user_ticker", "user_id", "ticker"),
    )

    def __repr__(self) -> str:
        return f"<PortfolioHolding(user='{self.user_id}', ticker='{self.ticker}', qty={self.quantity})>"
