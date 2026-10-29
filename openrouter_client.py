"""OpenRouter-backed answer client for the production simulator.

Mirrors the surface of ``gemini_client.GeminiClient`` (``answer_block`` and
``answer_blocks_batch``) so ``simulator.run_many`` can drive it interchangeably.
It reuses the provider-agnostic prompt/schema builders from ``gemini_client`` —
only the API call differs.

OpenRouter has no batch API, so ``answer_blocks_batch`` runs sync calls
concurrently across a small thread pool. Pass ``use_batch=False`` in
``run_many`` for these models (see ensemble.use_batch_for).
"""
from __future__ import annotations

import json
import re
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from gemini_client import (
    BatchInput,
    _build_prompt,
    _build_response_schema,
    collect_image_urls,
    image_labels_for,
)
from personas import Persona
from qualtrics_client import Question
from stimuli import image_data_url

_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterAnswerClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.5,
        disable_reasoning: bool = False,
        max_workers: int = 8,
    ):
        import httpx
        import openai
        import truststore

        ssl_ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._client = openai.OpenAI(
            api_key=api_key,
            base_url=_BASE_URL,
            http_client=httpx.Client(verify=ssl_ctx, timeout=120.0),
        )
        self._model = model
        self._temperature = temperature
        self._disable_reasoning = disable_reasoning
        self._max_workers = max_workers

    # ── single block ─────────────────────────────────────────────────────────
    def answer_block(
        self,
        persona: Persona,
        questions: list[Question],
        prior_answers: list[tuple[Question, Any]],
        read_context: list[Question] | None = None,
        survey_name: str = "",
    ) -> dict[str, Any]:
        answerable = [q for q in questions if _answerable(q)]
        if not answerable:
            return {}
        schema = _build_response_schema(answerable)
        image_urls = collect_image_urls(answerable, read_context or [])
        labels = image_labels_for(image_urls)
        prompt = _build_prompt(
            persona, answerable, prior_answers, read_context or [], survey_name,
            image_labels=labels,
        )
        return self._complete(prompt, schema, image_urls, labels)

    # ── batch (sequential/threaded sync — no OpenRouter batch API) ─────────────
    def answer_blocks_batch(
        self,
        inputs: list[BatchInput],
        *,
        on_progress=None,
        # Accepted for interface parity with GeminiClient; unused here.
        poll_interval_seconds: int = 30,
        max_wait_seconds: int = 2 * 3600,
        max_pending_seconds: int = 30 * 60,
    ) -> dict[str, dict[str, Any] | None]:
        results: dict[str, dict[str, Any] | None] = {}

        to_send: list[BatchInput] = []
        for inp in inputs:
            if not inp.answerable:
                results[inp.key] = {}
            else:
                to_send.append(inp)
        if not to_send:
            return results

        def _one(inp: BatchInput) -> tuple[str, dict[str, Any] | None]:
            schema = _build_response_schema(inp.answerable)
            image_urls = collect_image_urls(inp.answerable, inp.read_context)
            labels = image_labels_for(image_urls)
            prompt = _build_prompt(
                inp.persona, inp.answerable, inp.prior_answers,
                inp.read_context, inp.survey_name, image_labels=labels,
            )
            try:
                return inp.key, self._complete(prompt, schema, image_urls, labels)
            except Exception as exc:
                print(f"  [openrouter] {inp.key} failed: {exc}", flush=True)
                return inp.key, None

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            for key, answer in pool.map(_one, to_send):
                results[key] = answer
                if on_progress:
                    on_progress(f"openrouter answered {key}")
        return results

    # ── low-level call with retry + JSON extraction ────────────────────────────
    def _complete(
        self,
        prompt: str,
        schema: dict[str, Any],
        image_urls: list[str] | None = None,
        image_labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        schema_hint = json.dumps(schema, indent=2)
        full_prompt = (
            f"/no_think\n\n{prompt}\n\n"
            f"Return ONLY valid JSON matching this schema:\n{schema_hint}"
        )
        content = _build_message_content(full_prompt, image_urls or [], image_labels or {})
        for attempt in range(5):
            kwargs: dict[str, Any] = {}
            if self._disable_reasoning:
                kwargs["extra_body"] = {"reasoning": {"effort": "none"}}
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": content}],
                    temperature=self._temperature,
                    **kwargs,
                )
            except Exception as exc:
                wait = self._retry_wait(exc, attempt)
                if wait is None:
                    raise
                print(f"  [openrouter] rate/limit, retry in {wait}s "
                      f"(attempt {attempt + 1}/5)...", flush=True)
                time.sleep(wait)
                continue
            text = resp.choices[0].message.content
            if not text or not text.strip():
                # Some models (esp. reasoning ones) occasionally return empty
                # content. Retry within budget rather than failing the session.
                print(f"  [openrouter] empty content, retrying "
                      f"(attempt {attempt + 1}/5)...", flush=True)
                time.sleep(min(20, 3 * 2 ** attempt))
                continue
            return json.loads(_strip_fences(text.strip()))
        raise RuntimeError("OpenRouter: no valid response after retries (rate limit or empty content)")

    @staticmethod
    def _retry_wait(exc: Exception, attempt: int) -> int | None:
        msg = str(exc)
        if not any(s in msg for s in ("429", "rate", "503", "UNAVAILABLE", "overloaded")):
            return None
        m = re.search(r"retry_after_seconds['\"]:\s*([\d.]+)", msg)
        if m:
            return int(float(m.group(1))) + 2
        return min(120, 30 * 2 ** attempt)


def _build_message_content(
    prompt: str, image_urls: list[str], image_labels: dict[str, str]
) -> "str | list[dict[str, Any]]":
    """Plain string for text-only blocks (unchanged behavior); OpenAI-style
    content parts when the block has image stimuli. Images go in as base64
    data URLs (fetched once, cached in stimuli.fetch_image) so providers never
    have to reach Qualtrics-hosted URLs themselves. A failed download degrades
    to a text note so the session still completes."""
    if not image_urls:
        return prompt
    parts: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for url in image_urls:
        label = image_labels.get(url, url)
        try:
            data_url = image_data_url(url)
        except Exception as exc:
            print(f"  [stimuli] failed to fetch {label} ({url}): {exc}", flush=True)
            parts.append({
                "type": "text",
                "text": f"\n{label}: (image failed to load — answer from the text alone)",
            })
            continue
        parts.append({"type": "text", "text": f"\n{label}:"})
        parts.append({"type": "image_url", "image_url": {"url": data_url}})
    return parts


def _strip_fences(text: str) -> str:
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


def _answerable(q: Question) -> bool:
    from gemini_client import is_answerable
    return is_answerable(q)
