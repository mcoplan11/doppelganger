"""The production model ensemble — single source of truth.

Each run is administered independently through every model in ROSTER (same
persona panel, one Qualtrics copy per model). Results are surfaced *per model*
so a real effect shows up as a signal in at least one model.

ANONYMITY CONTRACT
------------------
The real provider/model identifiers below are INTERNAL ONLY. They may appear in
server logs and the admin-only run-notification email, but must NEVER reach a
user. Every user-facing surface — Qualtrics copy names, the results API, the CSV
export, the frontend — refers to a model exclusively by its public ``label``
("Model A", "Model B", …) and/or ``slug`` ("model_a", …). To rename or reorder
models, edit ROSTER here; nothing else encodes the mapping.

The ensemble members were selected on the Twin-2K-500 replication benchmark for
complementary coverage of classic decision biases (see
experiments/twin2k_replication/results_summary.md).
"""
from __future__ import annotations

from dataclasses import dataclass

from app_config import settings


@dataclass(frozen=True)
class ModelSpec:
    label: str          # public, user-facing (e.g. "Model A")
    slug: str           # public, filesystem/key-safe (e.g. "model_a")
    provider: str       # internal: "gemini" | "openrouter"
    model: str          # internal: real model id — never expose to users
    disable_reasoning: bool = False


# Model A's Gemini model. Hardcoded on purpose — changing it requires a deploy.
# To switch cost/quality, edit this one line and redeploy:
#   "gemini-2.5-flash"       — cheaper (current)
#   "gemini-3.5-flash"       — higher quality, ~2x cost
#   "gemini-2.5-flash-lite"  — cheapest (same as the free/smoke test)
MODEL_A_GEMINI = "gemini-2.5-flash"

# Ordered roster. Labels/slugs are the public identity; `model` is a secret.
ROSTER: list[ModelSpec] = [
    ModelSpec("Model A", "model_a", "gemini", MODEL_A_GEMINI),
    ModelSpec("Model B", "model_b", "openrouter", "z-ai/glm-5.2"),
    ModelSpec("Model C", "model_c", "openrouter", "qwen/qwen3-235b-a22b-2507"),
]

# Vision roster, used only when the survey contains image stimuli (<img> tags
# in question/descriptive text). Text-only surveys keep the Twin-2K-validated
# ROSTER above; glm-5.2 and qwen3-235b are text-only models, so image surveys
# swap Model B/C to vision-capable siblings from the SAME families, priced in
# the same band (glm-4.6v $0.30/$0.90 per M in/out; qwen3-vl-235b $0.21/$1.90
# vs qwen3-235b $0.09/$0.55 — checked 2026-10-29). Model A (Gemini Flash) is
# natively multimodal and stays. Labels are identical on purpose: the public
# identity is "Model A/B/C", whichever variant served the run.
VISION_ROSTER: list[ModelSpec] = [
    ModelSpec("Model A", "model_a", "gemini", MODEL_A_GEMINI),
    ModelSpec("Model B", "model_b", "openrouter", "z-ai/glm-4.6v"),
    ModelSpec("Model C", "model_c", "openrouter", "qwen/qwen3-vl-235b-a22b-instruct"),
]

# Trial ("smoke") runs use a single cheap model — quality doesn't matter, we're
# only verifying the survey converts and submits. Kept anonymous for symmetry.
# gemini-2.5-flash-lite is multimodal, so the same spec covers image surveys.
SMOKE_SPEC = ModelSpec("Trial", "trial", "gemini", "gemini-2.5-flash-lite")


def roster_for(is_smoke: bool, has_images: bool = False) -> list[ModelSpec]:
    if is_smoke:
        return [SMOKE_SPEC]
    return list(VISION_ROSTER if has_images else ROSTER)


def build_client(spec: ModelSpec, temperature: float = 0.5):
    """Construct the answer client for a model.

    Both clients expose the same ``answer_block`` / ``answer_blocks_batch``
    interface the simulator calls, so the runner treats them uniformly.
    """
    if spec.provider == "gemini":
        from gemini_client import GeminiClient
        if settings.gemini_use_vertex:
            return GeminiClient(
                None,
                spec.model,
                temperature=temperature,
                use_vertex=True,
                project=settings.gemini_project,
                location=settings.gemini_location,
            )
        return GeminiClient(settings.gemini_api_key, spec.model, temperature=temperature)
    if spec.provider == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set — required for ensemble model "
                f"{spec.label!r}. Set it in the backend environment."
            )
        from openrouter_client import OpenRouterAnswerClient
        return OpenRouterAnswerClient(
            settings.openrouter_api_key,
            spec.model,
            temperature=temperature,
            disable_reasoning=spec.disable_reasoning,
            # Reasoning models (glm-5.2, qwen3-235b) are latency-bound, so the
            # in-round thread pool is the throughput lever. 12 is a safe bump
            # over the default 8 given the client's built-in 429 backoff.
            max_workers=12,
        )
    raise ValueError(f"Unknown provider {spec.provider!r} for model {spec.label!r}")


def use_batch_for(spec: ModelSpec, is_smoke: bool) -> bool | None:
    """Batch-runner eligibility (the ``use_batch`` arg to ``simulator.run_many``).

    Both providers benefit from the batched runner — it fans the per-round LLM
    calls out concurrently while keeping all Qualtrics session mutation on the
    serial main loop:
      - Gemini: real Batch API off-Vertex; a concurrent sync fallback on Vertex.
      - OpenRouter: no batch API, but ``answer_blocks_batch`` runs a thread pool.
    Returning None lets ``run_many`` auto-enable it by panel size.

    Smoke runs stay on the serial path for fast, simple single-session feedback.
    """
    if is_smoke:
        return False
    return None
