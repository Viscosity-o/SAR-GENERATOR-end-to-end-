"""
Unified LLM Client Wrapper for Groq (and Bedrock prod compatibility).
Provides JSON formatting, prompt execution, temperature controls, and retry fallback.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

DEFAULT_API_KEY = os.getenv("GROQ_API_KEY", "")
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = "qwen/qwen3.8-27b"

# Cache client instance
_GROQ_CLIENT: Optional[Groq] = None


def get_groq_client() -> Groq:
    """Returns singleton Groq client with loaded API key."""
    global _GROQ_CLIENT
    if _GROQ_CLIENT is None:
        api_key = os.getenv("GROQ_API_KEY") or DEFAULT_API_KEY
        _GROQ_CLIENT = Groq(api_key=api_key)
    return _GROQ_CLIENT


def clean_json_text(text: str) -> str:
    """Removes markdown code fences and cleans JSON response."""
    text = text.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


def invoke_llm(
    prompt: str,
    system_prompt: str = "You are an expert AML Compliance and Financial Crime Investigator.",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    model: Optional[str] = None,
) -> str:
    """
    Invokes Groq LLM with system message and prompt.
    Temperature: dev=0.7, prod=0.3.
    """
    client = get_groq_client()
    target_model = model or DEFAULT_MODEL

    try:
        response = client.chat.completions.create(
            model=target_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        # Fallback to secondary model if primary encounters an issue
        try:
            response = client.chat.completions.create(
                model=FALLBACK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as fallback_err:
            raise RuntimeError(f"Groq LLM invocation failed: {str(e)} -> fallback: {str(fallback_err)}")


def invoke_llm_json(
    prompt: str,
    system_prompt: str = "You are an expert AML Investigator. Always output valid JSON only.",
    temperature: float = 0.7,
    max_tokens: int = 2048,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Invokes LLM and parses the returned JSON.
    """
    raw_output = invoke_llm(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )
    cleaned = clean_json_text(raw_output)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find first '{' and last '}'
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise ValueError(f"Failed to parse LLM output as JSON:\n{raw_output}")
