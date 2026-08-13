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


# Ordered roster. Labels/slugs are the public identity; `model` is a secret.
ROSTER: list[ModelSpec] = [
    ModelSpec("Model A", "model_a", "gemini", "gemini-3.5-flash"),
    ModelSpec("Model B", "model_b", "openrouter", "z-ai/glm-5.2"),
    ModelSpec("Model C", "model_c", "openrouter", "qwen/qwen3-235b-a22b-2507"),
]

# Trial ("smoke") runs use a single cheap model — quality doesn't matter, we're
# only verifying the survey converts and submits. Kept anonymous for symmetry.
SMOKE_SPEC = ModelSpec("Trial", "trial", "gemini", "gemini-2.5-flash-lite")


def roster_for(is_smoke: bool) -> list[ModelSpec]:
    return [SMOKE_SPEC] if is_smoke else list(ROSTER)


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
        )
    raise ValueError(f"Unknown provider {spec.provider!r} for model {spec.label!r}")


def use_batch_for(spec: ModelSpec, is_smoke: bool) -> bool | None:
    """Batch-API eligibility. Only Gemini has a batch API; OpenRouter is sync.

    Returns the ``use_batch`` value to pass to ``simulator.run_many``:
      - False for OpenRouter (no batch API) and for smoke runs (fast feedback).
      - None (auto-detect by size) for full Gemini runs.
    """
    if spec.provider != "gemini" or is_smoke:
        return False
    return None
