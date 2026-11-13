"""One wrapper for every LLM call: Gemini primary, Groq failover, JSON only.
complete_json() strips <think>...</think> blocks (Qwen3-family) before parsing, validates the JSON,
retries once on the same provider, then fails over. It records which provider answered."""
from __future__ import annotations
import json
import logging
import re
import time

from .config import settings

log = logging.getLogger("pathfinder.llm")
THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


class LLMError(RuntimeError):
    pass


def available() -> bool:
    return bool(settings.gemini_api_key or settings.groq_api_key)


def _parse(text: str) -> dict:
    """Take the FIRST JSON value in the text. Gemini sometimes appends a second object or trailing text
    ("Extra data" errors), and Qwen may wrap it in <think> or ``` fences."""
    t = THINK.sub("", text or "").strip()
    t = FENCE.sub("", t).strip()
    starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if not starts:
        raise ValueError("no JSON in response")
    out, _ = json.JSONDecoder().raw_decode(t[min(starts):])
    if isinstance(out, list):                        # a bare list of rows -> {"rows": [...]}
        out = {"rows": out}
    if not isinstance(out, dict):
        raise ValueError("JSON is not an object")
    return out


GROQ_MAX_PROMPT_CHARS = 9000   # Groq on-demand tier rejects big requests (429 "Request too large"); keep prompt + output small


_gemini = None
_groq = None


def _call_gemini(prompt: str, system: str) -> str:
    global _gemini
    from google import genai
    from google.genai import types
    _gemini = _gemini or genai.Client(api_key=settings.gemini_api_key)
    r = _gemini.models.generate_content(
        model=settings.gemini_model, contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json", temperature=0.2,
                                           max_output_tokens=4096),
    )
    return r.text or ""


def _call_groq(prompt: str, system: str) -> str:
    global _groq
    from groq import Groq
    _groq = _groq or Groq(api_key=settings.groq_api_key, timeout=30)
    if len(prompt) > GROQ_MAX_PROMPT_CHARS:          # keep the instructions (start) and the JSON shape (end), trim the page text
        prompt = prompt[:GROQ_MAX_PROMPT_CHARS - 1600] + "\n[...page text trimmed...]\n" + prompt[-1500:]
    r = _groq.chat.completions.create(
        model=settings.groq_model, temperature=0.2, response_format={"type": "json_object"}, max_tokens=2048,
        messages=[{"role": "system", "content": system + "\nReply with one JSON object only."}, {"role": "user", "content": prompt}],
    )
    return r.choices[0].message.content or ""


def complete_json(prompt: str, schema_hint: str = "", system: str = "You are a careful assistant for Georgia State University students.") -> tuple[dict, str]:
    """Returns (parsed_json, provider). Raises LLMError if every provider fails."""
    full = f"{prompt}\n\nReturn JSON matching this shape:\n{schema_hint}" if schema_hint else prompt
    providers = []
    if settings.gemini_api_key:
        providers.append(("gemini", _call_gemini))
    if settings.groq_api_key:
        providers.append(("groq", _call_groq))
    errors = []
    for name, fn in providers:
        for attempt in (1, 2):                       # one retry on the same provider, then fail over
            t0 = time.time()
            try:
                out = _parse(fn(full, system))
                log.info("llm ok provider=%s attempt=%s %.0fms", name, attempt, (time.time() - t0) * 1000)
                return out, name
            except Exception as e:                   # network, quota, invalid JSON
                errors.append(f"{name}#{attempt}: {type(e).__name__}: {str(e)[:160]}")
                log.warning("llm fail %s", errors[-1])
    raise LLMError("; ".join(errors) or "no LLM provider configured (set GEMINI_API_KEY or GROQ_API_KEY)")