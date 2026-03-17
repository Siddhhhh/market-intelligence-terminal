"""
Seed Company Relationships + Create New Tables

Creates the new tables (daily_indicators, company_cache, company_relationships,
movement_cache) and seeds curated company relationships.

Run:
    python scripts/init_intelligence.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from loguru import logger
from database.session import engine


RELATIONSHIPS = [
    # Apple supply chain
    ("AAPL", "TSM", "supplier", 0.95, "TSMC manufactures Apple's custom chips"),
    ("AAPL", "QCOM", "supplier", 0.80, "Qualcomm provides modem chips"),
    ("AAPL", "MSFT", "competitor", 0.85, "Competes in devices and services"),
    ("AAPL", "GOOGL", "competitor", 0.80, "Competes in mobile OS (iOS vs Android)"),

    # NVIDIA ecosystem
    ("NVDA", "TSM", "supplier", 0.95, "TSMC fabricates NVIDIA GPUs"),
    ("NVDA", "AMD", "competitor", 0.90, "Direct GPU and datacenter competitor"),
    ("NVDA", "MSFT", "partner", 0.85, "Microsoft Azure major customer for AI chips"),
    ("NVDA", "META", "partner", 0.80, "Meta major customer for AI training GPUs"),
    ("NVDA", "AMZN", "partner", 0.80, "AWS uses NVIDIA GPUs for cloud AI"),
    ("NVDA", "GOOGL", "partner", 0.75, "Google Cloud uses NVIDIA GPUs"),

    # Microsoft ecosystem
    ("MSFT", "GOOGL", "competitor", 0.90, "Cloud (Azure vs GCP), AI, productivity"),
    ("MSFT", "AMZN", "competitor", 0.85, "Cloud (Azure vs AWS)"),
    ("MSFT", "CRM", "competitor", 0.70, "Enterprise software competition"),

    # Tesla ecosystem
    ("TSLA", "RIVN", "competitor", 0.80, "EV manufacturer competitor"),
    ("TSLA", "F", "competitor", 0.70, "Traditional auto now competing in EV"),
    ("TSLA", "GM", "competitor", 0.70, "Traditional auto now competing in EV"),

    # Amazon ecosystem
    ("AMZN", "GOOGL", "competitor", 0.80, "Cloud and advertising competition"),
    ("AMZN", "WMT", "competitor", 0.85, "Retail competition"),
    ("AMZN", "SHOP", "partner", 0.60, "Many Shopify merchants sell on Amazon"),

    # Meta ecosystem
    ("META", "GOOGL", "competitor", 0.90, "Digital advertising competition"),
    ("META", "SNAP", "competitor", 0.75, "Social media and messaging competition"),

    # Semiconductor chain
    ("AMD", "INTC", "competitor", 0.90, "CPU and datacenter chip competition"),
    ("AMD", "TSM", "supplier", 0.95, "TSMC fabricates AMD chips"),
    ("INTC", "TSM", "competitor", 0.75, "Both are chip fabricators"),

    # Financial sector
    ("JPM", "GS", "competitor", 0.85, "Investment banking competition"),
    ("JPM", "BAC", "competitor", 0.80, "Banking and financial services"),
    ("V", "MA", "competitor", 0.90, "Payment network competition"),

    # Cloud/SaaS
    ("GOOGL", "CRM", "partner", 0.65, "CRM runs on Google Cloud"),
    ("NOW", "CRM", "competitor", 0.70, "Enterprise platform competition"),
]


def main():
    logger.info("=" * 60)
    logger.info("  INITIALIZE INTELLIGENCE SYSTEM")
    logger.info("=" * 60)

    with engine.connect() as conn:
        # Create new tables
        logger.info("Creating new tables...")

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS company_cache (
                ticker VARCHAR(20) PRIMARY KEY,
                market_cap BIGINT,
                pe_ratio NUMERIC(10,4),
                forward_pe NUMERIC(10,4),
                revenue BIGINT,
                net_income BIGINT,
                profit_margin NUMERIC(8,4),
                eps NUMERIC(10,4),
                revenue_growth NUMERIC(8,4),
                fifty_two_week_high NUMERIC(12,4),
                fifty_two_week_low NUMERIC(12,4),
                avg_volume BIGINT,
                top_holders JSON,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS company_relationships (
                id SERIAL PRIMARY KEY,
                company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                related_company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                relationship_type VARCHAR(30) NOT NULL,
                confidence_score NUMERIC(5,4) NOT NULL,
                description TEXT
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_company_rel_company ON company_relationships(company_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_company_rel_related ON company_relationships(related_company_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS movement_cache (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                range_period VARCHAR(10) NOT NULL,
                result_json JSON NOT NULL,
                generated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_movement_cache_ticker_range ON movement_cache(ticker, range_period)"))

        conn.commit()
        logger.info("  Tables created.")

        # Seed relationships
        logger.info("Seeding company relationships...")
        inserted = 0

        for ticker1, ticker2, rel_type, conf, desc in RELATIONSHIPS:
            # Resolve company IDs
            c1 = conn.execute(text("SELECT id FROM companies WHERE ticker = :t"), {"t": ticker1}).fetchone()
            c2 = conn.execute(text("SELECT id FROM companies WHERE ticker = :t"), {"t": ticker2}).fetchone()

            if not c1 or not c2:
                continue

            # Check if relationship already exists
            existing = conn.execute(text("""
                SELECT id FROM company_relationships
                WHERE company_id = :c1 AND related_company_id = :c2 AND relationship_type = :rt
            """), {"c1": c1[0], "c2": c2[0], "rt": rel_type}).fetchone()

            if existing:
                continue

            # Insert both directions
            conn.execute(text("""
                INSERT INTO company_relationships (company_id, related_company_id, relationship_type, confidence_score, description)
                VALUES (:c1, :c2, :rt, :conf, :desc)
            """), {"c1": c1[0], "c2": c2[0], "rt": rel_type, "conf": conf, "desc": desc})

            conn.execute(text("""
                INSERT INTO company_relationships (company_id, related_company_id, relationship_type, confidence_score, description)
                VALUES (:c2, :c1, :rt, :conf, :desc)
            """), {"c2": c2[0], "c1": c1[0], "rt": rel_type, "conf": conf, "desc": f"(reverse) {desc}"})

            inserted += 1

        conn.commit()
        logger.info(f"  {inserted} relationships seeded ({inserted * 2} bidirectional entries)")

    logger.info("=" * 60)
    logger.info("  INTELLIGENCE SYSTEM INITIALIZED")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
