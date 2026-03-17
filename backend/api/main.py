"""
Market Intelligence Terminal — FastAPI Application

The main API server. Mounts all route modules and provides
OpenAPI documentation at /docs.

Run:
    uvicorn backend.api.main:app --reload --port 8000

Swagger UI:
    http://localhost:8000/docs
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import stocks, crypto, events, sectors, movers, heatmap, chat, market, compare, company, investments, compare

app = FastAPI(
    title="Market Intelligence Terminal",
    description=(
        "Bloomberg-style financial intelligence API. "
        "Provides access to 35+ years of stock data, crypto markets, "
        "macroeconomic indicators, detected market events, and AI analysis."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow frontend (Next.js) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all route modules
app.include_router(stocks.router)
app.include_router(crypto.router)
app.include_router(events.router)
app.include_router(sectors.router)
app.include_router(movers.router)
app.include_router(heatmap.router)
app.include_router(chat.router)
app.include_router(market.router)
app.include_router(compare.router)
app.include_router(company.router)
app.include_router(investments.router)


@app.get("/", tags=["Health"])
def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "Market Intelligence Terminal API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/stats", tags=["Health"])
def api_stats():
    """Database statistics overview."""
    from sqlalchemy import text
    from database.session import engine

    with engine.connect() as conn:
        stats = {}
        for table in ["companies", "stocks", "crypto_prices", "market_events", "macro_events"]:
            stats[table] = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()

    return {
        "status": "online",
        "database": stats,
    }
