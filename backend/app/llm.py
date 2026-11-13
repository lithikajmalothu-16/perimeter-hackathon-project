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

def search_gsu(question: str, campus_hint: str = "") -> tuple[list[dict], str]:
    """Discovery: Gemini + Google Search grounding. Returns ([{url, title}], summary_text).
    Only the URLs matter: they are filtered to gsu.edu in code and then go through the normal ingestion pipeline
    (fetch -> extract -> evidence check), so nothing from search is shown to a student unverified."""
    q = (f"Find official Georgia State University web pages (gsu.edu or its subdomains) that help a student with: {question}. "
         f"{campus_hint} Prefer pages about GSU programs, offices, student organizations, advising and events. "
         "List each page's title and URL.")
    last = None
    models = list(dict.fromkeys([*settings.gemini_search_models, settings.gemini_model, "gemini-2.5-flash"])) if settings.gemini_api_key else []
    if models:
        global _gemini
        from google import genai
        from google.genai import types
        _gemini = _gemini or genai.Client(api_key=settings.gemini_api_key)
    for model in models:                             # quota is per model: on 429 move to the next model
        try:
            r = _gemini.models.generate_content(model=model, contents=q,
                                                config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.2))
            found = []
            for cand in r.candidates or []:
                gm = getattr(cand, "grounding_metadata", None)
                for ch in (getattr(gm, "grounding_chunks", None) or []):
                    w = getattr(ch, "web", None)
                    if w and w.uri:
                        found.append({"url": w.uri, "title": w.title or w.domain or ""})
            for u in re.findall(r"https?://[\w.-]*gsu\.edu[^\s)\]\"'>]*", r.text or ""):
                found.append({"url": u.rstrip(".,"), "title": ""})
            log.info("search_gsu ok model=%s results=%s", model, len(found))
            return found, (r.text or "")[:1500]
        except Exception as e:
            last = e
            log.warning("search_gsu model=%s failed: %s", model, str(e)[:200])
    # Groq failover: Compound models have built-in web search, restricted here to gsu.edu
    if settings.groq_api_key:
        for model in ("groq/compound-mini", "groq/compound"):
            try:
                found = _groq_search(q, model)
                log.info("search_gsu ok model=%s results=%s", model, len(found))
                if found:
                    return found, ""
            except Exception as e:
                last = e
                log.warning("search_gsu model=%s failed: %s", model, str(e)[:200])
    raise LLMError(f"search failed on Gemini and Groq: {last}" if last else "search needs GEMINI_API_KEY or GROQ_API_KEY")


def _groq_search(q: str, model: str) -> list[dict]:
    global _groq
    from groq import Groq
    _groq = _groq or Groq(api_key=settings.groq_api_key, timeout=30)
    r = _groq.chat.completions.create(model=model, messages=[{"role": "user", "content": q}],
                                      extra_body={"search_settings": {"include_domains": ["gsu.edu", "*.gsu.edu"]}})
    msg = r.choices[0].message
    found = []
    get = lambda o, k: (o.get(k) if isinstance(o, dict) else getattr(o, k, None))
    for t in (getattr(msg, "executed_tools", None) or []):
        sr = get(t, "search_results")
        results = (get(sr, "results") if sr is not None else None) or (sr if isinstance(sr, list) else [])
        for res in results or []:
            u = get(res, "url")
            if u:
                found.append({"url": u, "title": get(res, "title") or ""})
    for u in re.findall(r"https?://[\w.-]*gsu\.edu[^\s)\]\"'>]*", msg.content or ""):
        found.append({"url": u.rstrip(".,"), "title": ""})
    return found
