"""Built-in tier constructors for common providers. Each returns a Tier whose
`call(system, user, max_tokens)` returns `(text, cost_usd)`. Writing your own
is about 5 lines — see README for the pattern.
"""
from __future__ import annotations

from .breaker import Tier
from .pricing import estimate_cost


def anthropic_tier(api_key: str, model: str = "claude-sonnet-4-5", name: str = None) -> Tier:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    def _call(system: str, user: str, max_tokens: int):
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text
        cost = estimate_cost(model, resp.usage.input_tokens, resp.usage.output_tokens)
        return text, cost

    return Tier(name=name or f"anthropic:{model}", call=_call)


def openai_tier(
    api_key: str,
    model: str = "gpt-4o-mini",
    name: str = None,
    base_url: str = "https://api.openai.com/v1/chat/completions",
) -> Tier:
    import requests

    def _call(system: str, user: str, max_tokens: int):
        r = requests.post(
            base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=60,
        )
        r.raise_for_status()
        body = r.json()
        text = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        cost = estimate_cost(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        return text, cost

    return Tier(name=name or f"openai:{model}", call=_call)


def openrouter_tier(api_key: str, model: str = "google/gemini-2.5-flash", name: str = None) -> Tier:
    import requests

    def _call(system: str, user: str, max_tokens: int):
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=60,
        )
        r.raise_for_status()
        body = r.json()
        if "error" in body:
            raise RuntimeError(body["error"].get("message", "OpenRouter error"))
        text = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        cost = estimate_cost(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        return text, cost

    return Tier(name=name or f"openrouter:{model}", call=_call)


def gemini_tier(api_key: str, model: str = "gemini-2.5-flash", name: str = None) -> Tier:
    import requests

    def _call(system: str, user: str, max_tokens: int):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        r = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": user}]}],
                "systemInstruction": {"parts": [{"text": system}]},
                "generationConfig": {"maxOutputTokens": max_tokens},
            },
            timeout=60,
        )
        r.raise_for_status()
        body = r.json()
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        usage = body.get("usageMetadata", {})
        cost = estimate_cost(model, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0))
        return text, cost

    return Tier(name=name or f"gemini:{model}", call=_call)


def ollama_tier(model: str = "gemma:2b", base_url: str = "http://localhost:11434", name: str = None) -> Tier:
    """Local, free, always-on fallback via https://ollama.com — the tier a
    circuit breaker should route to once the budget runs out."""
    import requests

    def _call(system: str, user: str, max_tokens: int):
        r = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model, "stream": False,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "options": {"num_predict": max_tokens},
            },
            timeout=180,
        )
        r.raise_for_status()
        text = (r.json().get("message") or {}).get("content", "").strip()
        if not text:
            raise RuntimeError("Empty response from Ollama")
        return text, 0.0

    return Tier(name=name or f"ollama:{model}", call=_call, is_local=True)
