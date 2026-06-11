# Twin-2K-500 Replication

Replicates the 16 heuristics-and-biases experiments from Table 3 of:

> Toubia et al. (2025). *Twin-2K-500: A dataset for building digital twins of over 2,000 people based on their answers to over 500 questions.* arXiv:2505.17479

The paper found ~7/15 effects replicated by AI digital twins (built from real respondents' prior answers). This project asks: **how many effects do Doppelganger's synthetic personas replicate?**

---

## Files

| File | Purpose |
|---|---|
| `config.yaml` | Model, temperature, N personas, seed, between/within mode |
| `experiments.json` | All 16 experiment definitions — question text, conditions, expected effects |
| `llm_client.py` | LLM abstraction (Gemini / OpenAI / Anthropic) |
| `runner.py` | Prompts the LLM and collects responses |
| `analysis.py` | Statistical tests and comparison table |
| `run.py` | CLI entry point |
| `results/` | Timestamped output directories |

---

## Quick start

```bash
# From the repo root
eval "$(pyenv init -)" && eval "$(pyenv virtualenv-init -)" && pyenv activate env_3.11.8

# Install extra dependencies if needed
pip install scipy pyyaml

# Run all 16 experiments
python experiments/twin2k_replication/run.py

# Run one experiment
python experiments/twin2k_replication/run.py --experiment framing

# List all experiment IDs
python experiments/twin2k_replication/run.py --list

# Re-analyze an existing results directory (no LLM calls)
python experiments/twin2k_replication/run.py --analyze experiments/twin2k_replication/results/20250607_123456/
```

---

## Changing the model

Edit `config.yaml`:

```yaml
llm:
  provider: gemini         # gemini | openai | anthropic
  model: gemini-2.0-flash-exp
  temperature: 0.7
```

The API key is read from the parent `.env` file (`GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`).

---

## The 16 experiments

### Between-subject (11)

| ID | Name | Paper result |
|---|---|---|
| `framing` | Framing Problem (Asian Disease) | ✓ replicated |
| `linda` | Conjunction Problem (Linda) | ✓ replicated |
| `anchoring_redwood` | Anchoring — Redwood Tree | ✓ replicated |
| `anchoring_mississippi` | Anchoring — Mississippi River | ✗ not replicated |
| `savings` | Absolute vs. Relative Savings | ✓ replicated |
| `myside` | Myside Bias (foreign car) | ✓ replicated |
| `less_is_more` | Less is More (ice cream cups) | ✓ replicated |
| `wta_wtp` | WTA/WTP Endowment Effect | ✓ replicated |
| `sunk_cost` | Sunk Cost Fallacy | ✗ reversed |
| `outcome_bias` | Outcome Bias (doctor decision) | ✗ not replicated |
| `allais` | Allais Problem | ✗ not replicated |
| `base_rate` | Base Rate Problem | ✗ not replicated |

### Within-subject (5)

| ID | Name | Paper result |
|---|---|---|
| `false_consensus` | False Consensus Effect | ✓ replicated |
| `risk_benefit` | Risk-Benefit Nonseparability | ~ partial (1/4 items) |
| `omission_bias` | Omission Bias (vaccine) | ✗ not replicated |
| `probability_matching` | Probability Matching vs. Maximizing | ✗ not replicated |
| `dominator_neglect` | Dominator Neglect | ✓ replicated |

---

## Output

Each run creates `results/YYYYMMDD_HHMMSS/` containing:
- `{experiment_id}.json` — raw responses per persona per condition
- `config.yaml` — exact config used (for reproducibility)
- `report.md` — detailed statistics for each experiment

The comparison table is also printed to stdout.

---

## Reproducibility

All randomness is seeded via `config.yaml → experiment.seed`. Re-running with the same config + same model produces the same persona assignments. Note that LLM temperature > 0 means individual responses may vary; aggregate statistics should be stable across runs.
