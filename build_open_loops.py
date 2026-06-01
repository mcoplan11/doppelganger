"""Build the 'Open Loops vs Goal Initiation - Study 1' survey in Qualtrics.

Design (v2, 2026-05-25):

Tests whether being in a felt-waiting state reduces motivation to initiate
goals one is actively pursuing.

  Step 1 — Goal identification (TE/ML, common):
      participant names a personal goal they want to start.
  Step 2 — Recall manipulation (between-subjects, 2 cells):
      waiting:  recall something they're currently waiting for
      resolved: recall something they recently got closure on
  Step 3 — Manipulation check (MC/SAHR, 1-7)
  Step 4 — DV: likelihood + motivation toward their named goal (2 MC/SAHR, 1-7)
  Step 5 — Open-text reasoning (TE/ML)

Recall is autobiographical (NOT a vignette), which is the standard JCR-quality
manipulation for activating a felt state. Goal is idiographic so the DV is about
something the participant actively cares about.

Usage:
    python build_open_loops.py
"""
from __future__ import annotations

import sys

import requests

from config import load_config


SURVEY_NAME = "Open Loops vs Goal Initiation - Study 1"

GOAL_PROMPT = (
    "<p>Think about an important personal goal that you have been wanting to "
    "start working on but haven't started yet. This could be related to health, "
    "learning, career, relationships, finances, or anything else important to "
    "you.</p>"
    "<p>Briefly describe your goal in 1–2 sentences.</p>"
)

RECALL_WAITING = (
    "<p>Now, take a moment to think about something important in your life that "
    "you are <strong>currently waiting for</strong> — a result you don't yet "
    "have, a decision you haven't received, an outcome that's still pending.</p>"
    "<p>In 2–3 sentences, briefly describe what you're waiting for and how it "
    "feels to be in this waiting period.</p>"
)
RECALL_RESOLVED = (
    "<p>Now, take a moment to think about something important in your life that "
    "you <strong>recently finished or got closure on</strong> — a decision that "
    "was made, a result you received, a project you wrapped up.</p>"
    "<p>In 2–3 sentences, briefly describe what you recently finished and how it "
    "feels to have closure on it.</p>"
)

MCHECK_TEXT = (
    "<p>Right now, how much do you feel like you have something important left "
    "hanging?</p>"
)
MCHECK_SCALE = {
    "1": {"Display": "1 Not at all"},
    "2": {"Display": "2"},
    "3": {"Display": "3"},
    "4": {"Display": "4"},
    "5": {"Display": "5"},
    "6": {"Display": "6"},
    "7": {"Display": "7 Extremely"},
}

DV_INTRO = (
    "<p>The next two questions are about the personal goal you described at the "
    "start of this study.</p>"
)
DV_LIKELY_TEXT = (
    "<p>How likely are you to take a concrete first step toward your goal "
    "<strong>this week</strong>?</p>"
)
DV_LIKELY_SCALE = {
    "1": {"Display": "1 Not at all likely"},
    "2": {"Display": "2"},
    "3": {"Display": "3"},
    "4": {"Display": "4"},
    "5": {"Display": "5"},
    "6": {"Display": "6"},
    "7": {"Display": "7 Extremely likely"},
}
DV_MOTIV_TEXT = (
    "<p>How motivated do you feel right now to work on your goal?</p>"
)
DV_MOTIV_SCALE = {
    "1": {"Display": "1 Not at all motivated"},
    "2": {"Display": "2"},
    "3": {"Display": "3"},
    "4": {"Display": "4"},
    "5": {"Display": "5"},
    "6": {"Display": "6"},
    "7": {"Display": "7 Extremely motivated"},
}

REASONING_TEXT = (
    "<p>In one or two sentences, briefly explain why you gave the ratings "
    "above.</p>"
)


class Qualtrics:
    def __init__(self, base_url: str, token: str):
        self._base = base_url.rstrip("/")
        self._token = token
        self._s = requests.Session()
        self._s.headers.update({
            "X-API-TOKEN": token,
            "Content-Type": "application/json",
        })

    def _post(self, path: str, body: dict, *, params: dict | None = None) -> dict:
        r = self._s.post(f"{self._base}{path}", json=body, params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"POST {path} → {r.status_code}: {r.text[:300]}")
        return r.json()["result"]

    def _put(self, path: str, body: dict) -> dict:
        r = self._s.put(f"{self._base}{path}", json=body, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"PUT {path} → {r.status_code}: {r.text[:300]}")
        return r.json().get("result", {})

    def _delete(self, path: str) -> None:
        self._s.delete(f"{self._base}{path}", timeout=30)

    def create_survey(self, name: str) -> tuple[str, str]:
        r = self._post("/survey-definitions",
                       {"SurveyName": name, "Language": "EN", "ProjectCategory": "CORE"})
        return r["SurveyID"], r["DefaultBlockID"]

    def create_block(self, sid: str, description: str) -> str:
        r = self._post(f"/survey-definitions/{sid}/blocks",
                       {"Type": "Standard", "Description": description, "BlockElements": []})
        return r["BlockID"]

    def add_question(self, sid: str, block_id: str, body: dict) -> str:
        r = self._post(f"/survey-definitions/{sid}/questions",
                       body, params={"blockId": block_id})
        return r["QuestionID"]

    def set_flow(self, sid: str, flow: dict) -> None:
        self._put(f"/survey-definitions/{sid}/flow", flow)

    def activate(self, sid: str) -> None:
        self._put(f"/surveys/{sid}", {"isActive": True})

    def delete_survey(self, sid: str) -> None:
        self._delete(f"/surveys/{sid}")


def te_ml_question(text: str, tag: str, *, force: bool = True) -> dict:
    q = {
        "QuestionText": text,
        "QuestionType": "TE",
        "Selector": "ML",
        "DataExportTag": tag,
    }
    if force:
        q["Validation"] = {
            "Settings": {"ForceResponse": "ON", "ForceResponseType": "ON", "Type": "None"}
        }
    return q


def mc_likert_question(text: str, tag: str, scale: dict) -> dict:
    return {
        "QuestionText": text,
        "QuestionType": "MC",
        "Selector": "SAHR",
        "SubSelector": "TX",
        "Choices": scale,
        "ChoiceOrder": list(scale.keys()),
        "DataExportTag": tag,
        "Validation": {
            "Settings": {"ForceResponse": "ON", "ForceResponseType": "ON", "Type": "None"}
        },
    }


def db_question(text: str, tag: str) -> dict:
    return {
        "QuestionText": text,
        "QuestionType": "DB",
        "Selector": "TB",
        "DataExportTag": tag,
    }


def build_flow(block_goal: str, block_waiting: str, block_resolved: str, block_dv: str) -> dict:
    def embedded(field: str, value: str, flow_id: str) -> dict:
        return {
            "Type": "EmbeddedData",
            "FlowID": flow_id,
            "EmbeddedData": [{
                "Description": field, "Type": "Custom", "Field": field,
                "VariableType": "String", "DataVisibility": [],
                "AnalyzeText": False, "Value": value,
            }],
        }
    return {
        "Type": "Root", "FlowID": "FL_1",
        "Properties": {"Count": 20},
        "Flow": [
            {"Type": "Block", "FlowID": "FL_5", "ID": block_goal},
            {
                "Type": "BlockRandomizer", "FlowID": "FL_10",
                "EvenPresentation": True, "SubSet": 1,
                "Flow": [
                    {"Type": "Group", "FlowID": "FL_11", "Description": "Waiting arm",
                     "Flow": [
                         embedded("Condition", "waiting", "FL_12"),
                         {"Type": "Block", "FlowID": "FL_13", "ID": block_waiting},
                     ]},
                    {"Type": "Group", "FlowID": "FL_14", "Description": "Resolved arm",
                     "Flow": [
                         embedded("Condition", "resolved", "FL_15"),
                         {"Type": "Block", "FlowID": "FL_16", "ID": block_resolved},
                     ]},
                ],
            },
            {"Type": "Block", "FlowID": "FL_20", "ID": block_dv},
        ],
    }


def main() -> int:
    cfg = load_config()
    q = Qualtrics(cfg.qualtrics_base_url, cfg.qualtrics_token)

    print(f"Creating survey '{SURVEY_NAME}'...")
    sid, default_block = q.create_survey(SURVEY_NAME)
    print(f"  → {sid}")

    try:
        # Default block becomes the goal-identification block.
        block_goal = default_block
        print(f"\nGoal-identification block (default): {block_goal}")
        q.add_question(sid, block_goal, te_ml_question(GOAL_PROMPT, "goal"))
        print("  + goal (TE/ML)")

        print("\nCreating Waiting recall block...")
        block_waiting = q.create_block(sid, "Recall - Waiting Arm")
        q.add_question(sid, block_waiting,
                       te_ml_question(RECALL_WAITING, "recall_waiting"))
        print(f"  → {block_waiting}, + recall_waiting (TE/ML)")

        print("\nCreating Resolved recall block...")
        block_resolved = q.create_block(sid, "Recall - Resolved Arm")
        q.add_question(sid, block_resolved,
                       te_ml_question(RECALL_RESOLVED, "recall_resolved"))
        print(f"  → {block_resolved}, + recall_resolved (TE/ML)")

        print("\nCreating shared DV block (manipulation check + DVs + reasoning)...")
        block_dv = q.create_block(sid, "Manipulation Check + DVs + Reasoning")
        q.add_question(sid, block_dv,
                       mc_likert_question(MCHECK_TEXT, "mcheck_hanging", MCHECK_SCALE))
        print(f"  → {block_dv}")
        print("  + mcheck_hanging (MC/SAHR)")
        q.add_question(sid, block_dv, db_question(DV_INTRO, "dv_intro"))
        print("  + dv_intro (DB)")
        q.add_question(sid, block_dv,
                       mc_likert_question(DV_LIKELY_TEXT, "dv_likely_this_week", DV_LIKELY_SCALE))
        print("  + dv_likely_this_week (MC/SAHR)")
        q.add_question(sid, block_dv,
                       mc_likert_question(DV_MOTIV_TEXT, "dv_motivation", DV_MOTIV_SCALE))
        print("  + dv_motivation (MC/SAHR)")
        q.add_question(sid, block_dv, te_ml_question(REASONING_TEXT, "reasoning"))
        print("  + reasoning (TE/ML)")

        print("\nUpdating survey flow...")
        q.set_flow(sid, build_flow(block_goal, block_waiting, block_resolved, block_dv))
        print("  flow set")

        print("\nActivating survey...")
        q.activate(sid)
        print("  activated")

        print("\n" + "=" * 64)
        print(f"DONE. Survey ID: {sid}")
        print(f"  Edit:    https://mccombs.yul1.qualtrics.com/survey-builder/{sid}/edit")
        print(f"  Preview: https://mccombs.qualtrics.com/jfe/form/{sid}")
        print(f"  Run:     python main.py run --survey-id {sid}")
        print("=" * 64)
        return 0
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        print(f"Deleting partial survey {sid}...", file=sys.stderr)
        q.delete_survey(sid)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
