# System Architecture

## Overview

Market Intelligence Terminal follows a layered architecture where each layer has a single responsibility and communicates through well-defined interfaces.

## Data Flow

```
User Question
     │
     ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Next.js    │────▶│  FastAPI     │────▶│  Query Router   │
│  Frontend   │     │  REST API    │     │  (Mistral)      │
└─────────────┘     └──────┬───────┘     └────────┬────────┘
                           │                      │
                           │               ┌──────▼────────┐
                           │               │  Evidence     │
                           │               │  Builder      │
                           │               └──────┬────────┘
                           │                      │
                    ┌──────▼───────┐       ┌──────▼────────┐
                    │  PostgreSQL  │◀──────│  Market       │
                    │  TimescaleDB │       │  Analyst      │
                    └──────────────┘       │  (Llama3)     │
                           ▲               └───────────────┘
                           │
                    ┌──────┴───────┐
                    │  Data        │
                    │  Pipeline    │
                    └──────┬───────┘
                           ▲
                    ┌──────┴───────┐
                    │  yfinance    │
                    │  FRED API    │
                    └──────────────┘
```

## Layer Responsibilities

### Data Pipeline Layer
- Downloads raw market data from yfinance and FRED
- Cleans, validates, and computes derived fields (pct_change)
- Detects market events (crashes, spikes, sector moves)
- Precomputes aggregation tables (sector_performance)
- Runs daily via APScheduler after market close

### Database Layer
- PostgreSQL 16 with TimescaleDB extension
- Hypertables for time-series data (365-day chunk intervals)
- 9 tables with foreign keys, indexes, and constraints
- Precomputed sector_performance for fast heatmap queries

### API Layer
- FastAPI with Pydantic request/response validation
- 18+ REST endpoints with date range filtering
- Dependency injection for database sessions
- CORS enabled for frontend communication
- OpenAPI documentation auto-generated at /docs

### AI Layer
- Two-model architecture: Router (Mistral) + Analyst (Llama3)
- Evidence Builder bridges database and LLM
- Structured evidence prevents hallucination
- Confidence scores based on available data quality

### Frontend Layer
- Next.js 14 with App Router
- Three-panel trading terminal layout
- Lightweight Charts for candlestick rendering
- Tailwind CSS with custom dark theme (Black Gold)
- Real-time AI chat with source attribution

## Database Schema

```
sectors (11 rows)
  │
  ├──< companies (503 rows)
  │       │
  │       ├──< stocks (3.7M rows) [HYPERTABLE]
  │       │
  │       └──< market_events (70K rows)
  │
  └──< sector_performance (100K rows) [PRECOMPUTED]

crypto_assets (3 rows)
  │
  ├──< crypto_prices (9.4K rows) [HYPERTABLE]
  │
  └──< market_events

macro_events (32K rows) [standalone]
market_regimes [extensible]
```

## Design Decisions

1. **Local LLMs over cloud APIs**: Privacy, no API costs, no rate limits.
   Tradeoff: slower inference (30-60s vs 1-2s), requires GPU for best performance.

2. **Evidence Builder pattern**: The LLM never sees raw database rows.
   Instead, it receives pre-structured financial signals with context.
   This eliminates hallucination for data-grounded questions.

3. **Precomputed aggregation**: The sector_performance table trades
   storage (100K rows) for query speed (200ms → 5ms). Worth it for
   a heatmap that's requested on every page load.

4. **TimescaleDB over plain PostgreSQL**: Hypertable chunking makes
   range queries across 36 years of data nearly instant. Without it,
   scanning 3.7M rows for a date range would be noticeably slow.

5. **Two-model AI**: Mistral is fast and cheap for classification.
   Llama3 is powerful but slow. Using both means the router
   classifies in <1s and only the complex path hits the heavy model.

6. **Idempotent pipelines**: Every INSERT uses ON CONFLICT DO NOTHING.
   Re-running the pipeline never creates duplicates. This makes
   daily automation safe and debugging easy.
