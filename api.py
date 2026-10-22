"""Backend: a FastAPI service that analyses one customer review with an LLM.

The model is asked for structured JSON matching a Pydantic schema, so every
response comes back as a validated label, score and theme rather than free text.
Two providers are supported and chosen in .env:

    LLM_PROVIDER=openai   (default, uses OPENAI_API_KEY)
    LLM_PROVIDER=gemini   (uses GOOGLE_API_KEY)

Run it with:
    uv run fastapi dev api.py

Interactive API docs are then available at http://127.0.0.1:8000/docs
"""

import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "openai").strip().lower()
DEFAULT_MODELS = {"openai": "gpt-4.1", "gemini": "gemini-2.5-flash"}
KEY_VARS = {"openai": ["OPENAI_API_KEY"], "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY"]}

if PROVIDER not in DEFAULT_MODELS:
    raise RuntimeError(f"LLM_PROVIDER must be 'openai' or 'gemini', not '{PROVIDER}'.")
if not any(os.getenv(var) for var in KEY_VARS[PROVIDER]):
    raise RuntimeError(
        f"No API key found for {PROVIDER}. Copy .env.example to .env and set {KEY_VARS[PROVIDER][0]}."
    )

MODEL = os.getenv("LLM_MODEL") or DEFAULT_MODELS[PROVIDER]

app = FastAPI(
    title="Customer Feedback Analyzer API",
    description="Classifies a customer review's sentiment, rating and main theme using an LLM.",
    version="1.1.0",
)


class Review(BaseModel):
    """Request body: the review to analyse."""

    text: str = Field(min_length=1, max_length=2000, examples=["The food was great but delivery was slow."])


class LLMAnalysis(BaseModel):
    """Schema sent to the model. Kept to the JSON Schema features every provider supports."""

    label: Literal["positive", "negative", "neutral"]
    score: int
    theme: str


class Analysis(LLMAnalysis):
    """Validated result returned by this API."""

    score: int = Field(ge=1, le=5, description="1 = very bad, 5 = very good")
    theme: str = Field(description="One lowercase word for the main topic, e.g. delivery")


INSTRUCTIONS = (
    "You analyze customer reviews.\n"
    "label must be 'positive', 'negative', or 'neutral'.\n"
    "score must be a whole number from 1 (very bad) to 5 (very good).\n"
    "theme must be ONE lowercase word for the main topic "
    "(for example: delivery, taste, price, service, quality)."
)


def _call_openai(text: str) -> LLMAnalysis | None:
    from openai import OpenAI

    response = OpenAI().responses.parse(
        model=MODEL,
        input=[
            {"role": "system", "content": INSTRUCTIONS},
            {"role": "user", "content": f"Review: {text}"},
        ],
        text_format=LLMAnalysis,
        temperature=0,  # same review -> same answer
    )
    return response.output_parsed  # None if the model refused


def _call_gemini(text: str) -> LLMAnalysis | None:
    from google import genai
    from google.genai import types

    response = genai.Client().models.generate_content(
        model=MODEL,
        contents=f"{INSTRUCTIONS}\nReview: {text}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMAnalysis,
            temperature=0,
        ),
    )
    return response.parsed


def call_llm(text: str) -> LLMAnalysis | None:
    """Send one review to the configured provider and return its structured reply."""
    return _call_openai(text) if PROVIDER == "openai" else _call_gemini(text)


@app.get("/health")
def health():
    """Lets the dashboard check that the backend is running before it sends reviews."""
    return {"status": "ok", "provider": PROVIDER, "model": MODEL}


@app.post("/analyze", response_model=Analysis)
def analyze(review: Review) -> Analysis:
    try:
        result = call_llm(review.text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{PROVIDER} request failed: {exc}") from exc

    if result is None:
        raise HTTPException(status_code=502, detail=f"{PROVIDER} returned a response that did not match the schema.")

    try:
        analysis = Analysis.model_validate(result.model_dump())
    except ValidationError as exc:
        raise HTTPException(status_code=502, detail=f"{PROVIDER} returned invalid values: {exc.errors()[0]['msg']}") from exc

    analysis.theme = analysis.theme.strip().lower()
    return analysis
