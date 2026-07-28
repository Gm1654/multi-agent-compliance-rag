"""Shared Gemini LLM helpers for agents."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.1-flash-lite")
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "5"))


def _get_genai():
    import google.generativeai as genai

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("Set GOOGLE_API_KEY or GEMINI_API_KEY for LLM calls.")
    genai.configure(api_key=api_key)
    return genai


def _retry_delay(attempt: int) -> float:
    return min(60.0, 2 ** attempt)


def generate_text(
    prompt: str,
    *,
    thinking_level: str = "low",
    temperature: float = 0.2,
) -> str:
    from google.api_core import exceptions as google_exceptions

    genai = _get_genai()
    model = genai.GenerativeModel(LLM_MODEL)

    generation_config: dict[str, Any] = {"temperature": temperature}
    if thinking_level:
        generation_config["thinking_config"] = {"thinking_level": thinking_level}

    last_error: Exception | None = None
    for attempt in range(LLM_MAX_RETRIES):
        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                request_options={"timeout": 120},
            )
            return (response.text or "").strip()
        except (google_exceptions.DeadlineExceeded, google_exceptions.ResourceExhausted) as exc:
            last_error = exc
            if attempt == LLM_MAX_RETRIES - 1:
                raise
            time.sleep(_retry_delay(attempt))
        except Exception as exc:
            last_error = exc
            try:
                response = model.generate_content(
                    prompt,
                    request_options={"timeout": 120},
                )
                return (response.text or "").strip()
            except (google_exceptions.DeadlineExceeded, google_exceptions.ResourceExhausted) as retry_exc:
                last_error = retry_exc
                if attempt == LLM_MAX_RETRIES - 1:
                    raise
                time.sleep(_retry_delay(attempt))

    if last_error:
        raise last_error
    raise RuntimeError("LLM call failed without a response.")


def generate_json(
    prompt: str,
    *,
    thinking_level: str = "low",
    temperature: float = 0.1,
) -> Any:
    text = generate_text(
        prompt,
        thinking_level=thinking_level,
        temperature=temperature,
    )
    return _parse_json(text)


def _parse_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise
