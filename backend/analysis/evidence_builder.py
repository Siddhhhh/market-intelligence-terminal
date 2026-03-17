"""
Evidence Builder — Structured Financial Context

Queries the database for relevant financial signals before the LLM
generates a response. This grounds the AI's answers in real data
and reduces hallucination.

The evidence object contains:
    - company_data: price history, basic info
    - sector_performance: sector averages
    - market_events: relevant detected events
    - macro_events: economic indicators
    - top_movers: biggest movers around the time period
    - confidence_score: how much evidence was found (0-1)

Usage:
    from backend.analysis.evidence_builder import build_evidence
    evidence = build_evidence(
        tickers=["NVDA"],
        date_hints={"year": 2023},
        category="market_data",
    )
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from loguru import logger
from database.session import engine


def build_evidence(
    tickers: list[str] = None,
    date_hints: dict = None,
    category: str = "market_data",
) -> dict:
    """
    Build a structured evidence object by querying the database.

    Args:
        tickers: Stock/crypto tickers mentioned in the question
        date_hints: Year or date range extracted from the question
        category: Query category from the router

    Returns:
        Evidence dict with all gathered financial signals
    """
    tickers = tickers or []
    date_hints = date_hints or {}

    evidence = {
        "company_data": {},
        "sector_performance": {},
        "market_events": [],
        "macro_events": [],
        "top_movers": [],
        "confidence_score": 0.0,
        "signals_used": 0,
        "data_points": 0,
    }

    # Build date range
    year = date_hints.get("year")
    start_year = date_hints.get("start_year", year)
    end_year = date_hints.get("end_year", year)

    if start_year:
        start_date = f"{start_year}-01-01"
        end_date = f"{end_year or start_year}-12-31"
    else:
        # Default: last 2 years
        now = datetime.now()
        start_date = f"{now.year - 2}-01-01"
        end_date = f"{now.year}-12-31"

    with engine.connect() as conn:

        # ── Company data for mentioned tickers ──────────────
        for ticker in tickers[:5]:  # Limit to 5 tickers
            company_info = _get_company_data(conn, ticker, start_date, end_date)
            if company_info:
                evidence["company_data"][ticker] = company_info
                evidence["signals_used"] += 1
                evidence["data_points"] += company_info.get("price_records", 0)

        # ── Sector performance ──────────────────────────────
        if tickers:
            sector_data = _get_sector_performance(conn, tickers, start_date, end_date)
            if sector_data:
                evidence["sector_performance"] = sector_data
                evidence["signals_used"] += 1

        # ── Market events ───────────────────────────────────
        events = _get_market_events(conn, tickers, start_date, end_date)
        if events:
            evidence["market_events"] = events
            evidence["signals_used"] += 1
            evidence["data_points"] += len(events)

        # ── Macro events ────────────────────────────────────
        macro = _get_macro_context(conn, start_date, end_date)
        if macro:
            evidence["macro_events"] = macro
            evidence["signals_used"] += 1
            evidence["data_points"] += len(macro)

        # ── Top movers (for historical_analysis) ────────────
        if category == "historical_analysis":
            movers = _get_notable_movers(conn, start_date, end_date)
            if movers:
                evidence["top_movers"] = movers
                evidence["signals_used"] += 1

    # Calculate confidence score
    max_signals = 5
    evidence["confidence_score"] = round(
        min(evidence["signals_used"] / max_signals, 1.0), 2
    )

    logger.info(
        f"Evidence built: {evidence['signals_used']} signals, "
        f"{evidence['data_points']} data points, "
        f"confidence={evidence['confidence_score']}"
    )

    return evidence


def _get_company_data(conn, ticker: str, start_date: str, end_date: str) -> dict:
    """Get company info and price summary for a ticker."""
    try:
        # Company info
        company = conn.execute(text("""
            SELECT c.ticker, c.name, s.display_name as sector, c.industry
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.id
            WHERE c.ticker = :ticker
        """), {"ticker": ticker}).fetchone()

        if not company:
            # Try crypto
            crypto = conn.execute(text("""
                SELECT symbol, name FROM crypto_assets WHERE symbol = :symbol
            """), {"symbol": ticker}).fetchone()
            if crypto:
                return _get_crypto_data(conn, ticker, start_date, end_date)
            return None

        # Price summary
        price_summary = conn.execute(text("""
            SELECT
                COUNT(*) as records,
                MIN(close) as min_price,
                MAX(close) as max_price,
                ROUND(AVG(close)::numeric, 2) as avg_price,
                MIN(date)::date as first_date,
                MAX(date)::date as last_date
            FROM stocks s
            JOIN companies c ON s.company_id = c.id
            WHERE c.ticker = :ticker
            AND s.date >= :start_date AND s.date <= :end_date
        """), {"ticker": ticker, "start_date": start_date, "end_date": end_date}).fetchone()

        # Period return
        period_return = conn.execute(text("""
            WITH first_last AS (
                SELECT
                    FIRST_VALUE(close) OVER (ORDER BY date ASC) as first_close,
                    FIRST_VALUE(close) OVER (ORDER BY date DESC) as last_close
                FROM stocks s
                JOIN companies c ON s.company_id = c.id
                WHERE c.ticker = :ticker
                AND s.date >= :start_date AND s.date <= :end_date
            )
            SELECT ROUND(((last_close - first_close) / first_close * 100)::numeric, 2)
            FROM first_last LIMIT 1
        """), {"ticker": ticker, "start_date": start_date, "end_date": end_date}).fetchone()

        # Biggest single-day moves
        big_moves = conn.execute(text("""
            SELECT s.date::date, s.pct_change, s.close
            FROM stocks s
            JOIN companies c ON s.company_id = c.id
            WHERE c.ticker = :ticker
            AND s.date >= :start_date AND s.date <= :end_date
            AND s.pct_change IS NOT NULL
            ORDER BY ABS(s.pct_change) DESC
            LIMIT 5
        """), {"ticker": ticker, "start_date": start_date, "end_date": end_date}).fetchall()

        return {
            "ticker": company[0],
            "name": company[1],
            "sector": company[2],
            "industry": company[3],
            "price_records": price_summary[0] if price_summary else 0,
            "min_price": float(price_summary[1]) if price_summary and price_summary[1] else None,
            "max_price": float(price_summary[2]) if price_summary and price_summary[2] else None,
            "avg_price": float(price_summary[3]) if price_summary and price_summary[3] else None,
            "date_range": f"{price_summary[4]} to {price_summary[5]}" if price_summary and price_summary[4] else None,
            "period_return_pct": float(period_return[0]) if period_return and period_return[0] else None,
            "biggest_moves": [
                {"date": str(m[0]), "pct_change": float(m[1]), "close": float(m[2])}
                for m in big_moves
            ],
        }

    except Exception as e:
        logger.warning(f"Failed to get company data for {ticker}: {e}")
        return None


def _get_crypto_data(conn, symbol: str, start_date: str, end_date: str) -> dict:
    """Get crypto asset price summary."""
    try:
        summary = conn.execute(text("""
            SELECT
                ca.symbol, ca.name,
                COUNT(*) as records,
                MIN(cp.close) as min_price,
                MAX(cp.close) as max_price,
                ROUND(AVG(cp.close)::numeric, 2) as avg_price
            FROM crypto_prices cp
            JOIN crypto_assets ca ON cp.crypto_id = ca.id
            WHERE ca.symbol = :symbol
            AND cp.date >= :start_date AND cp.date <= :end_date
            GROUP BY ca.symbol, ca.name
        """), {"symbol": symbol, "start_date": start_date, "end_date": end_date}).fetchone()

        if not summary:
            return None

        return {
            "ticker": summary[0],
            "name": summary[1],
            "sector": "Cryptocurrency",
            "price_records": summary[2],
            "min_price": float(summary[3]) if summary[3] else None,
            "max_price": float(summary[4]) if summary[4] else None,
            "avg_price": float(summary[5]) if summary[5] else None,
        }

    except Exception as e:
        logger.warning(f"Failed to get crypto data for {symbol}: {e}")
        return None


def _get_sector_performance(conn, tickers: list, start_date: str, end_date: str) -> dict:
    """Get sector performance for the sectors of mentioned tickers."""
    try:
        rows = conn.execute(text("""
            SELECT
                sec.display_name,
                ROUND(AVG(s.pct_change)::numeric, 4) as avg_daily_change,
                COUNT(DISTINCT c.id) as companies
            FROM stocks s
            JOIN companies c ON s.company_id = c.id
            JOIN sectors sec ON c.sector_id = sec.id
            WHERE c.ticker = ANY(:tickers)
            AND s.date >= :start_date AND s.date <= :end_date
            GROUP BY sec.display_name
        """), {"tickers": tickers, "start_date": start_date, "end_date": end_date}).fetchall()

        return {
            r[0]: {"avg_daily_change": float(r[1]) if r[1] else 0, "companies": r[2]}
            for r in rows
        }

    except Exception as e:
        logger.warning(f"Failed to get sector performance: {e}")
        return {}


def _get_market_events(conn, tickers: list, start_date: str, end_date: str) -> list:
    """Get relevant market events for the time period and tickers."""
    try:
        query = """
            SELECT date::date, event_type, severity, ticker, magnitude, description
            FROM market_events
            WHERE date >= :start_date AND date <= :end_date
        """
        params: dict = {"start_date": start_date, "end_date": end_date}

        if tickers:
            query += " AND (ticker = ANY(:tickers) OR event_type IN ('market_crash', 'sector_move'))"
            params["tickers"] = tickers
        else:
            query += " AND severity IN ('high', 'critical')"

        query += " ORDER BY date DESC LIMIT 20"

        rows = conn.execute(text(query), params).fetchall()

        return [
            {
                "date": str(r[0]), "type": r[1], "severity": r[2],
                "ticker": r[3], "magnitude": float(r[4]) if r[4] else None,
                "description": r[5],
            }
            for r in rows
        ]

    except Exception as e:
        logger.warning(f"Failed to get market events: {e}")
        return []


def _get_macro_context(conn, start_date: str, end_date: str) -> list:
    """Get macro economic context for the time period."""
    try:
        rows = conn.execute(text("""
            SELECT indicator, date::date, value, change_pct
            FROM macro_events
            WHERE date >= :start_date AND date <= :end_date
            AND indicator IN ('fed_funds_rate', 'vix', 'unemployment_rate', 'cpi')
            ORDER BY date DESC
            LIMIT 20
        """), {"start_date": start_date, "end_date": end_date}).fetchall()

        return [
            {
                "indicator": r[0], "date": str(r[1]),
                "value": float(r[2]), "change_pct": float(r[3]) if r[3] else None,
            }
            for r in rows
        ]

    except Exception as e:
        logger.warning(f"Failed to get macro context: {e}")
        return []


def _get_notable_movers(conn, start_date: str, end_date: str) -> list:
    """Get the most notable stock moves in the period (for historical analysis)."""
    try:
        rows = conn.execute(text("""
            SELECT c.ticker, c.name, s.date::date, s.pct_change
            FROM stocks s
            JOIN companies c ON s.company_id = c.id
            WHERE s.date >= :start_date AND s.date <= :end_date
            AND ABS(s.pct_change) > 15
            ORDER BY ABS(s.pct_change) DESC
            LIMIT 10
        """), {"start_date": start_date, "end_date": end_date}).fetchall()

        return [
            {"ticker": r[0], "name": r[1], "date": str(r[2]), "pct_change": float(r[3])}
            for r in rows
        ]

    except Exception as e:
        logger.warning(f"Failed to get notable movers: {e}")
        return []


def format_evidence_for_llm(evidence: dict) -> str:
    """
    Convert the evidence dict into a readable string for the LLM prompt.
    """
    parts = []

    # Company data
    if evidence["company_data"]:
        parts.append("=== COMPANY DATA ===")
        for ticker, data in evidence["company_data"].items():
            parts.append(f"\n{ticker} ({data.get('name', 'Unknown')}):")
            parts.append(f"  Sector: {data.get('sector', 'N/A')}")
            if data.get("date_range"):
                parts.append(f"  Date range: {data['date_range']}")
            if data.get("period_return_pct") is not None:
                parts.append(f"  Period return: {data['period_return_pct']:+.2f}%")
            if data.get("min_price") and data.get("max_price"):
                parts.append(f"  Price range: ${data['min_price']:.2f} - ${data['max_price']:.2f}")
            if data.get("biggest_moves"):
                parts.append("  Biggest single-day moves:")
                for m in data["biggest_moves"][:3]:
                    parts.append(f"    {m['date']}: {m['pct_change']:+.2f}% (close: ${m['close']:.2f})")

    # Sector performance
    if evidence["sector_performance"]:
        parts.append("\n=== SECTOR PERFORMANCE ===")
        for sector, perf in evidence["sector_performance"].items():
            parts.append(f"  {sector}: avg daily change {perf['avg_daily_change']:+.4f}%")

    # Market events
    if evidence["market_events"]:
        parts.append("\n=== MARKET EVENTS ===")
        for event in evidence["market_events"][:10]:
            desc = event.get("description", "No description")
            parts.append(f"  [{event['date']}] {event['type']} ({event['severity']}): {desc[:100]}")

    # Macro events
    if evidence["macro_events"]:
        parts.append("\n=== MACROECONOMIC CONTEXT ===")
        seen = set()
        for m in evidence["macro_events"]:
            key = m["indicator"]
            if key not in seen:
                seen.add(key)
                change = f" (change: {m['change_pct']:+.2f}%)" if m.get("change_pct") else ""
                parts.append(f"  {m['indicator']}: {m['value']} as of {m['date']}{change}")

    # Top movers
    if evidence["top_movers"]:
        parts.append("\n=== NOTABLE MOVERS ===")
        for m in evidence["top_movers"][:5]:
            parts.append(f"  {m['ticker']} ({m['name']}): {m['pct_change']:+.2f}% on {m['date']}")

    # Metadata
    parts.append(f"\n=== EVIDENCE QUALITY ===")
    parts.append(f"  Signals used: {evidence['signals_used']}")
    parts.append(f"  Data points: {evidence['data_points']}")
    parts.append(f"  Confidence: {evidence['confidence_score']}")

    return "\n".join(parts)
