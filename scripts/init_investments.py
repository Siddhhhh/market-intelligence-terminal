"""
Initialize Investment Intelligence Tables

Creates user_profiles and portfolio_holdings tables.

Run:
    python scripts/init_investments.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from loguru import logger
from database.session import engine


def main():
    logger.info("=" * 60)
    logger.info("  INITIALIZE INVESTMENT SYSTEM")
    logger.info("=" * 60)

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL DEFAULT 'Default User',
                risk_tolerance VARCHAR(20) NOT NULL DEFAULT 'moderate',
                investment_horizon VARCHAR(20) NOT NULL DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS portfolio_holdings (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                asset_type VARCHAR(10) NOT NULL DEFAULT 'stock',
                ticker VARCHAR(20) NOT NULL,
                quantity NUMERIC(12,4) NOT NULL,
                avg_buy_price NUMERIC(12,4) NOT NULL,
                buy_date DATE,
                notes TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_portfolio_user_ticker ON portfolio_holdings(user_id, ticker)"))

        # Create default user profile
        existing = conn.execute(text("SELECT id FROM user_profiles WHERE user_id = 'demo_user_1'")).fetchone()
        if not existing:
            conn.execute(text("""
                INSERT INTO user_profiles (user_id, name, risk_tolerance, investment_horizon)
                VALUES ('demo_user_1', 'Default User', 'moderate', 'medium')
            """))
            logger.info("  Created default user profile (demo_user_1)")

        conn.commit()

    logger.info("  Tables created successfully")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
