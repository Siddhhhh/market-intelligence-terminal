"""
Query Router — Intent Classification

Uses the Mistral model (fast, lightweight) to classify user questions
into one of four categories:
    - finance_knowledge
    - market_data
    - historical_analysis
    - off_topic

Usage:
    from backend.ai_engine.router import classify_query
    category = classify_query("Why did NVIDIA rise in 2023?")
    # Returns: "market_data"
"""

import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ollama
from loguru import logger
from config import settings
from backend.ai_engine.prompts import ROUTER_SYSTEM_PROMPT, ROUTER_USER_TEMPLATE


VALID_CATEGORIES = ["finance_knowledge", "market_data", "historical_analysis", "off_topic"]


def classify_query(question: str) -> str:
    """
    Classify a user question into a category using Mistral.

    Args:
        question: The user's question string

    Returns:
        One of: finance_knowledge, market_data, historical_analysis, off_topic
    """
    logger.info(f"Router: classifying '{question[:60]}...'")

    try:
        response = ollama.chat(
            model=settings.llm_router_model,
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": ROUTER_USER_TEMPLATE.format(question=question)},
            ],
            options={
                "temperature": 0.1,
                "num_predict": 20,
            },
        )

        raw = response["message"]["content"].strip().lower()

        # Extract the category from the response
        # The model should return just the category name, but sometimes adds extra text
        for category in VALID_CATEGORIES:
            if category in raw:
                logger.info(f"Router: classified as '{category}'")
                return category

        # Fallback: try to match partial keywords
        if any(w in raw for w in ["knowledge", "concept", "definition", "explain"]):
            return "finance_knowledge"
        if any(w in raw for w in ["data", "stock", "price", "company", "ticker"]):
            return "market_data"
        if any(w in raw for w in ["history", "historical", "crash", "trend", "past"]):
            return "historical_analysis"

        logger.warning(f"Router: unrecognized response '{raw}', defaulting to market_data")
        return "market_data"

    except Exception as e:
        logger.error(f"Router failed: {e}")
        # Fallback classification based on keywords
        q = question.lower()
        if any(w in q for w in ["what is", "define", "explain", "how does", "how do"]):
            return "finance_knowledge"
        if any(w in q for w in ["crash", "history", "since", "biggest", "worst", "best"]):
            return "historical_analysis"
        if any(w in q for w in ["weather", "joke", "recipe", "movie"]):
            return "off_topic"
        return "market_data"


def extract_tickers(question: str) -> list[str]:
    """
    Extract stock ticker symbols from a question.

    Looks for:
        - All-caps words 2-5 chars (AAPL, NVDA, TSLA)
        - Company names mapped to tickers
    """
    # Find uppercase words that look like tickers
    potential = re.findall(r'\b[A-Z]{2,5}\b', question)

    # Filter out common words that aren't tickers
    stop_words = {
        "THE", "AND", "FOR", "BUT", "NOT", "ARE", "WAS", "HAS",
        "HAD", "HOW", "WHY", "WHO", "DID", "CAN", "GDP", "CPI",
        "USD", "ETF", "IPO", "CEO", "CFO", "SEC", "FED", "VIX",
    }
    tickers = [t for t in potential if t not in stop_words]

    # Also check for well-known company names
    name_to_ticker = {
        "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL",
        "alphabet": "GOOGL", "amazon": "AMZN", "nvidia": "NVDA",
        "tesla": "TSLA", "meta": "META", "facebook": "META",
        "netflix": "NFLX", "intel": "INTC", "amd": "AMD",
        "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL",
        "jpmorgan": "JPM", "walmart": "WMT", "disney": "DIS",
        "coca-cola": "KO", "pepsi": "PEP", "boeing": "BA",
    }

    q_lower = question.lower()
    for name, ticker in name_to_ticker.items():
        if name in q_lower and ticker not in tickers:
            tickers.append(ticker)

    return tickers


def extract_date_hints(question: str) -> dict:
    """
    Extract date-related hints from a question.

    Returns dict with optional keys: year, start_year, end_year
    """
    hints = {}
    q = question.lower()

    # Single year: "in 2023", "during 2020"
    year_match = re.findall(r'\b(19\d{2}|20\d{2})\b', question)
    if year_match:
        years = [int(y) for y in year_match]
        if len(years) == 1:
            hints["year"] = years[0]
        elif len(years) >= 2:
            hints["start_year"] = min(years)
            hints["end_year"] = max(years)

    # Relative: "last year", "this year"
    if "last year" in q:
        from datetime import datetime
        hints["year"] = datetime.now().year - 1
    if "this year" in q:
        from datetime import datetime
        hints["year"] = datetime.now().year

    return hints


if __name__ == "__main__":
    # Quick test
    test_questions = [
        "What is inflation?",
        "Why did NVIDIA rise in 2023?",
        "Show biggest market crashes since 1990",
        "What's the weather today?",
    ]

    for q in test_questions:
        category = classify_query(q)
        tickers = extract_tickers(q)
        dates = extract_date_hints(q)
        print(f"Q: {q}")
        print(f"  Category: {category}")
        print(f"  Tickers:  {tickers}")
        print(f"  Dates:    {dates}")
        print()
