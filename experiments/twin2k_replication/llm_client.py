"""LLM client abstraction. Swap providers via config.yaml without changing runner code.

All clients expose two methods:
  complete(prompt, schema)           — single synchronous call (fallback / testing)
  complete_batch(requests)           — batch call; Gemini uses the 50%-cost Batch API,
                                       other providers fall back to sequential sync calls.

`requests` is a list of {"key": str, "prompt": str, "schema": dict}.
`complete_batch` returns {key: answer_dict_or_None}.
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any

_BATCH_CHUNK = 50  # Gemini drops responses silently above this per job


class LLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Single synchronous call. Returns parsed JSON dict."""

    def complete_batch(
        self,
        requests: list[dict[str, Any]],
        *,
        checkpoint_path: str | None = None,
    ) -> dict[str, dict[str, Any] | None]:
        """Batch call. Default: sequential sync (override in subclasses for true batch).

        `requests` items: {"key": str, "prompt": str, "schema": dict}
        Returns: {key: answer_dict or None on error}

        If checkpoint_path is given, results are written after each request so a
        crashed run can be resumed without re-doing completed work.
        """
        from pathlib import Path

        results: dict[str, dict[str, Any] | None] = {}

        if checkpoint_path:
            cp = Path(checkpoint_path)
            if cp.exists():
                results = json.loads(cp.read_text())
                done = sum(1 for v in results.values() if v is not None)
                if done:
                    print(f"  Resuming from checkpoint: {done}/{len(requests)} already done", flush=True)

        for req in requests:
            if req["key"] in results:
                continue
            try:
                results[req["key"]] = self.complete(req["prompt"], req["schema"])
            except Exception as e:
                print(f"  [sync] {req['key']} failed: {e}", flush=True)
                results[req["key"]] = None
            if checkpoint_path:
                Path(checkpoint_path).write_text(json.dumps(results))

        return results


class GeminiClient(LLMClient):
    def __init__(self, model: str, temperature: float, api_key: str):
        from google import genai
        from google.genai import types as gtypes

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._types = gtypes

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=self._types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=self._temperature,
            ),
        )
        return json.loads(resp.text)

    def complete_batch(
        self, requests: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any] | None]:
        """Submit all requests via Gemini Batch API (50% cost vs. sync).

        Splits into chunks of _BATCH_CHUNK to avoid silent truncation.
        Each request dict: {"key": str, "prompt": str, "schema": dict}
        """
        results: dict[str, dict[str, Any] | None] = {}
        chunks = [
            requests[i: i + _BATCH_CHUNK]
            for i in range(0, len(requests), _BATCH_CHUNK)
        ]
        for idx, chunk in enumerate(chunks):
            label = f"chunk {idx + 1}/{len(chunks)} " if len(chunks) > 1 else ""
            print(f"  Submitting {label}({len(chunk)} requests)...", flush=True)
            results.update(self._submit_chunk(chunk))
        return results

    def _submit_chunk(
        self,
        requests: list[dict[str, Any]],
        poll_interval: int = 30,
        max_wait: int = 2 * 3600,
        max_pending: int = 30 * 60,
    ) -> dict[str, dict[str, Any] | None]:
        inline = [
            self._types.InlinedRequest(
                contents=r["prompt"],
                config=self._types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=r["schema"],
                    temperature=self._temperature,
                ),
            )
            for r in requests
        ]

        last_exc: Exception | None = None
        job = None
        for attempt in range(4):
            if attempt:
                wait = min(60, 10 * 2 ** (attempt - 1))
                print(f"  503 on batch create, retrying in {wait}s "
                      f"(attempt {attempt + 1}/4)...", flush=True)
                time.sleep(wait)
            try:
                job = self._client.batches.create(
                    model=self._model,
                    src=inline,
                    config={"display_name": f"twin2k-batch-{int(time.time())}"},
                )
                break
            except Exception as exc:
                msg = str(exc)
                if "503" in msg or "UNAVAILABLE" in msg:
                    last_exc = exc
                    continue
                raise
        if job is None:
            raise last_exc  # type: ignore[misc]

        print(f"  Batch job {job.name} submitted — polling...", flush=True)

        terminal = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED",
                    "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
        start = time.time()
        pending_since: float | None = None
        while True:
            job = self._client.batches.get(name=job.name)
            state = job.state.name
            if state in terminal:
                break
            if time.time() - start > max_wait:
                raise RuntimeError(f"Batch job exceeded max_wait={max_wait}s")
            if state == "JOB_STATE_PENDING":
                if pending_since is None:
                    pending_since = time.time()
                elif time.time() - pending_since > max_pending:
                    raise RuntimeError(
                        f"Batch job stuck in PENDING for >{max_pending // 60} min"
                    )
            else:
                pending_since = None
            print(f"  state={state}, elapsed={int(time.time() - start)}s...", flush=True)
            time.sleep(poll_interval)

        if job.state.name != "JOB_STATE_SUCCEEDED":
            raise RuntimeError(
                f"Batch job ended in {job.state.name}: {getattr(job, 'error', '?')}"
            )

        inline_responses = job.dest.inlined_responses or []
        if len(inline_responses) != len(requests):
            raise RuntimeError(
                f"Batch returned {len(inline_responses)} responses "
                f"for {len(requests)} requests"
            )

        results: dict[str, dict[str, Any] | None] = {}
        for req, resp in zip(requests, inline_responses):
            if resp.response is None:
                results[req["key"]] = None
                continue
            try:
                results[req["key"]] = json.loads(resp.response.text)
            except Exception:
                results[req["key"]] = None
        return results


class OpenAIClient(LLMClient):
    def __init__(self, model: str, temperature: float, api_key: str):
        import openai
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)


class AnthropicClient(LLMClient):
    def __init__(self, model: str, temperature: float, api_key: str):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        schema_hint = json.dumps(schema, indent=2)
        full_prompt = (
            f"{prompt}\n\nReturn ONLY valid JSON matching this schema:\n{schema_hint}"
        )
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            temperature=self._temperature,
            messages=[{"role": "user", "content": full_prompt}],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())


class OpenRouterClient(LLMClient):
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, model: str, temperature: float, api_key: str, disable_reasoning: bool = False):
        import ssl
        import httpx
        import openai
        import truststore
        ssl_ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        http_client = httpx.Client(verify=ssl_ctx)
        self._client = openai.OpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
            http_client=http_client,
        )
        self._model = model
        self._temperature = temperature
        self._disable_reasoning = disable_reasoning
        self._usage_log: list[dict] = []

    def complete(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        schema_hint = json.dumps(schema, indent=2)
        # /no_think disables Qwen3's chain-of-thought reasoning tokens (cuts cost ~10x)
        full_prompt = (
            f"/no_think\n\n{prompt}\n\nReturn ONLY valid JSON matching this schema:\n{schema_hint}"
        )
        for attempt in range(5):
            kwargs = {}
            if self._disable_reasoning:
                kwargs["extra_body"] = {"reasoning": {"effort": "none"}}
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": full_prompt}],
                    temperature=self._temperature,
                    **kwargs,
                )
            except Exception as exc:
                wait = self._retry_wait(exc, attempt)
                if wait is None:
                    raise
                print(f"  429 rate limit, retrying in {wait}s (attempt {attempt + 1}/5)...", flush=True)
                time.sleep(wait)
                continue
            if resp.usage:
                usage_entry = {
                    "input": resp.usage.prompt_tokens,
                    "output": resp.usage.completion_tokens,
                }
                details = getattr(resp.usage, "completion_tokens_details", None)
                if details:
                    usage_entry["reasoning"] = getattr(details, "reasoning_tokens", 0) or 0
                self._usage_log.append(usage_entry)
            text = resp.choices[0].message.content
            if text is None:
                raise ValueError("OpenRouter returned empty content")
            text = text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        raise RuntimeError("OpenRouter: exceeded max retries on rate limit")

    def print_usage_summary(self, n_total_calls: int, input_price: float = 1.25, output_price: float = 3.75) -> None:
        """Print token usage stats and projected cost for a full run."""
        if not self._usage_log:
            print("  No usage data recorded.")
            return
        n = len(self._usage_log)
        avg_in = sum(u["input"] for u in self._usage_log) / n
        avg_out = sum(u["output"] for u in self._usage_log) / n
        avg_reasoning = sum(u.get("reasoning", 0) for u in self._usage_log) / n
        proj_in = avg_in * n_total_calls / 1_000_000
        proj_out = avg_out * n_total_calls / 1_000_000
        cost = proj_in * input_price + proj_out * output_price
        print(f"\n{'─'*50}")
        print(f"  DRY-RUN TOKEN USAGE ({n} sampled calls)")
        print(f"{'─'*50}")
        print(f"  Avg input tokens/call:     {avg_in:.0f}")
        print(f"  Avg output tokens/call:    {avg_out:.0f}")
        if avg_reasoning > 0:
            print(f"  Avg reasoning tokens/call: {avg_reasoning:.0f}  ← thinking is ON")
        else:
            print(f"  Reasoning tokens/call:     0  ← /no_think working")
        print(f"")
        print(f"  Projected full run ({n_total_calls} calls):")
        print(f"    Input:  {proj_in:.2f}M tokens  →  ${proj_in * input_price:.2f}")
        print(f"    Output: {proj_out:.2f}M tokens  →  ${proj_out * output_price:.2f}")
        print(f"    TOTAL ESTIMATED COST:      ${cost:.2f}")
        print(f"{'─'*50}\n")

    @staticmethod
    def _retry_wait(exc: Exception, attempt: int) -> int | None:
        msg = str(exc)
        if "429" not in msg and "rate" not in msg.lower():
            return None
        # Honour Retry-After if present, otherwise exponential backoff
        import re
        m = re.search(r"retry_after_seconds['\"]:\s*([\d.]+)", msg)
        if m:
            return int(float(m.group(1))) + 2
        return min(120, 30 * 2 ** attempt)


def build_client(provider: str, model: str, temperature: float, api_key: str, disable_reasoning: bool = False) -> LLMClient:
    if provider == "gemini":
        return GeminiClient(model, temperature, api_key)
    if provider == "openai":
        return OpenAIClient(model, temperature, api_key)
    if provider == "anthropic":
        return AnthropicClient(model, temperature, api_key)
    if provider == "openrouter":
        return OpenRouterClient(model, temperature, api_key, disable_reasoning=disable_reasoning)
    raise ValueError(f"Unknown LLM provider: {provider!r}. Use gemini, openai, anthropic, or openrouter.")
