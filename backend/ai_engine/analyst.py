"""
Market Analyst — LLM-Powered Financial Analysis

Uses the Llama3 model (deep reasoning) to generate explanations
grounded in structured evidence from the database.

Flow:
    1. Router classifies the question
    2. Evidence Builder gathers database context
    3. Analyst generates the final response using evidence

Usage:
    from backend.ai_engine.analyst import analyze_question
    result = analyze_question("Why did NVIDIA rise in 2023?")
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import ollama
from loguru import logger
from config import settings
from backend.ai_engine.router import classify_query, extract_tickers, extract_date_hints
from backend.ai_engine.prompts import (
    ANALYST_SYSTEM_PROMPT,
    ANALYST_USER_TEMPLATE,
    KNOWLEDGE_SYSTEM_PROMPT,
    KNOWLEDGE_USER_TEMPLATE,
    OFF_TOPIC_RESPONSE,
)
from backend.analysis.evidence_builder import build_evidence, format_evidence_for_llm


def analyze_question(question: str) -> dict:
    """
    Full AI pipeline: route → build evidence → generate answer.

    Args:
        question: The user's financial question

    Returns:
        Dict with: question, category, answer, evidence_summary, confidence
    """
    start_time = time.time()

    # Step 1: Classify the question
    category = classify_query(question)
    logger.info(f"Analyst: category={category}")

    # Step 2: Handle off-topic
    if category == "off_topic":
        return {
            "question": question,
            "category": category,
            "answer": OFF_TOPIC_RESPONSE,
            "evidence_summary": {},
            "sources_used": [],
            "confidence": 0.0,
            "processing_time": round(time.time() - start_time, 2),
        }

    # Step 3: Handle finance knowledge (no evidence needed)
    if category == "finance_knowledge":
        answer = _generate_knowledge_response(question)
        return {
            "question": question,
            "category": category,
            "answer": answer,
            "evidence_summary": {},
            "sources_used": ["llm_knowledge"],
            "confidence": 0.7,
            "processing_time": round(time.time() - start_time, 2),
        }

    # Step 4: Build evidence for market_data and historical_analysis
    tickers = extract_tickers(question)
    date_hints = extract_date_hints(question)

    logger.info(f"Analyst: tickers={tickers}, dates={date_hints}")

    evidence = build_evidence(
        tickers=tickers,
        date_hints=date_hints,
        category=category,
    )

    # Step 5: Generate analyst response
    evidence_text = format_evidence_for_llm(evidence)
    answer = _generate_analyst_response(question, category, evidence_text)

    # Determine which sources were used
    sources = []
    if evidence["company_data"]:
        sources.append("stock_prices")
    if evidence["sector_performance"]:
        sources.append("sector_data")
    if evidence["market_events"]:
        sources.append("market_events")
    if evidence["macro_events"]:
        sources.append("macro_indicators")
    if evidence["top_movers"]:
        sources.append("top_movers")

    return {
        "question": question,
        "category": category,
        "answer": answer,
        "evidence_summary": {
            "tickers_analyzed": list(evidence["company_data"].keys()),
            "events_found": len(evidence["market_events"]),
            "macro_points": len(evidence["macro_events"]),
            "signals_used": evidence["signals_used"],
            "data_points": evidence["data_points"],
        },
        "sources_used": sources,
        "confidence": evidence["confidence_score"],
        "processing_time": round(time.time() - start_time, 2),
    }


def _generate_analyst_response(question: str, category: str, evidence_text: str) -> str:
    """Generate the analyst response using Llama3."""
    try:
        response = ollama.chat(
            model=settings.llm_analyst_model,
            messages=[
                {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                {"role": "user", "content": ANALYST_USER_TEMPLATE.format(
                    question=question,
                    category=category,
                    evidence=evidence_text,
                )},
            ],
            options={
                "temperature": 0.3,
                "num_predict": 1000,
            },
        )

        return response["message"]["content"].strip()

    except Exception as e:
        logger.error(f"Analyst LLM failed: {e}")
        return (
            f"I encountered an error generating the analysis. "
            f"Error: {str(e)}. "
            f"Please ensure Ollama is running with the {settings.llm_analyst_model} model."
        )


def _generate_knowledge_response(question: str) -> str:
    """Generate a knowledge response using Llama3 (no evidence needed)."""
    try:
        response = ollama.chat(
            model=settings.llm_analyst_model,
            messages=[
                {"role": "system", "content": KNOWLEDGE_SYSTEM_PROMPT},
                {"role": "user", "content": KNOWLEDGE_USER_TEMPLATE.format(question=question)},
            ],
            options={
                "temperature": 0.4,
                "num_predict": 500,
            },
        )

        return response["message"]["content"].strip()

    except Exception as e:
        logger.error(f"Knowledge LLM failed: {e}")
        return f"I couldn't generate a response. Please ensure Ollama is running. Error: {str(e)}"


if __name__ == "__main__":
    # Quick test
    test_questions = [
        "Why did NVIDIA rise in 2023?",
        "What is inflation?",
        "What caused the biggest market crashes?",
    ]

    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print("="*60)
        result = analyze_question(q)
        print(f"Category: {result['category']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Sources: {result['sources_used']}")
        print(f"Time: {result['processing_time']}s")
        print(f"\nAnswer:\n{result['answer'][:500]}...")
