"""Generate additional MTurk/Prolific-style personas using Gemini.

Asks gemini-3.5-flash for N new personas matching the existing v2 roster style:
- Distinctly non-"average American" — these model the *paid online survey worker*
  population (younger, more educated, geographically clustered, satisficing).
- Distinct from the existing roster (existing names passed into the prompt).
- Each persona spans 70–100 words of description covering: age, gender, job,
  region, education, survey-platform habits, and concrete satisficing behavior.

Usage:
    python generate_personas.py --count 100 --out responses/generated_v3.json

The output file is JSON: list of {"name": "...", "description": "..."} objects.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from google import genai
from google.genai import types

from config import load_config
from personas import DEFAULT_PERSONAS


PROMPT_TEMPLATE = """Generate {count} new personas representing the typical population that takes paid online surveys on platforms like Amazon MTurk and Prolific.

CRITICAL: these are NOT a cross-section of average Americans. The MTurk/Prolific population is:
- Skewed younger (heavily 18–40, with some 40+ and a few retirees)
- More educated than the US average (most have at least some college; many have bachelor's)
- More likely to be in lower-paid service jobs, gig economy, stay-home parents, students, or freelancers
- More likely white or Asian, less likely Black or Hispanic than the US average
- Geographically diverse but skewing US (with some non-US English-speakers possible)
- Treats survey-taking as either a side hustle or a fun way to earn coffee money
- Demonstrates SATISFICING behavior: rushing through, skimming vignettes, clicking the middle option, straight-lining matrix questions, picking "neither" when unsure, scanning for keywords

Each persona should have:
- name: snake_case_role_age_sex format (e.g. "biology_student_19f", "freelance_writer_29nb", "stay_home_dad_32m"). Use 'm', 'f', or 'nb' for gender.
- description: 70–100 words covering age, location (US state or region), job, education, family situation if relevant, and CONCRETE survey-taking behavior (what specifically they do on Prolific/MTurk — be vivid and varied).

EXISTING ROSTER (do NOT duplicate these names or descriptions):
{existing_names}

Generate {count} NEW personas distinct from the above. Vary across:
- Ages (mostly 18–45, but include some 45+ and a couple of retirees)
- Job categories (service, retail, freelance, gig, admin, student, stay-home, healthcare-support, tech-adjacent, education, etc.)
- Gender (~50% female, ~45% male, ~5% nb)
- Geography (varied US regions; can include 1–2 non-US English speakers)
- Survey behaviors (some speed-clickers, some careful-readers-for-payment, some attention-check-paranoid, some who write minimum-effort open-text, etc.)

Return as a JSON array of {{"name": "...", "description": "..."}} objects.
"""


def make_prompt(count: int) -> str:
    existing = ", ".join(p.name for p in DEFAULT_PERSONAS)
    return PROMPT_TEMPLATE.format(count=count, existing_names=existing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--count", type=int, default=100, help="Number of personas to generate")
    parser.add_argument("--out", default="responses/generated_v3.json",
                        help="Output JSON path")
    parser.add_argument("--model", default=None,
                        help="Gemini model (default: from GEMINI_MODEL env var)")
    args = parser.parse_args()

    cfg = load_config()
    model = args.model or cfg.gemini_model

    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["name", "description"],
        },
    }

    client = genai.Client(api_key=cfg.gemini_api_key)
    print(f"Calling {model} for {args.count} personas...", flush=True)
    resp = client.models.generate_content(
        model=model,
        contents=make_prompt(args.count),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.95,
        ),
    )

    personas = json.loads(resp.text)
    existing_names = {p.name for p in DEFAULT_PERSONAS}
    deduped = []
    seen = set()
    for p in personas:
        name = p.get("name", "").strip()
        desc = p.get("description", "").strip()
        if not name or not desc:
            continue
        if name in existing_names or name in seen:
            continue
        seen.add(name)
        deduped.append({"name": name, "description": desc})

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(deduped, indent=2))
    print(f"Saved {len(deduped)} new personas to {args.out}", flush=True)
    print(f"(Generated {len(personas)} total, {len(personas)-len(deduped)} duplicates/empties filtered)")
    if deduped:
        print(f"\nSample (first 5):")
        for p in deduped[:5]:
            print(f"  {p['name']}")
            print(f"    {p['description'][:120]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
