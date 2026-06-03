"""Convert a Qualtrics survey to AI-compatible form.

Workflow:
  1. Copy the source survey into a new survey owned by the API user.
  2. Soft-strip: delete questions whose DataExportTag matches a stop-list
     (demographics, consent, attention checks — useless for AI runs).
  3. Activate the copy.
  4. Hard-strip: probe with start_session. Qualtrics returns the exact QIDs
     it cannot handle in the `incompatibilities` block. Delete them and retry
     until either the survey is runnable or we've looped too many times.

Usage:
    python convert_to_ai.py SV_xxxxxxxxxxxxxxx
    python convert_to_ai.py SV_xxxxxxxxxxxxxxx --name "My Custom Copy Name"
    python convert_to_ai.py SV_xxxxxxxxxxxxxxx --no-soft-strip
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

import requests

from config import load_config

# Tags whose questions are useless for AI runs (demographics, consent, attention checks).
SOFT_STRIP_TAGS = {
    "age", "sex", "gender", "consent",
    "check", "AC", "fail",
    "bot", "Captcha", "delay",
}
# Question (Type, Selector) pairs that are known to be either:
#   - rejected by the Sessions API (Slider, Captcha, Timing, Matrix-Likert), OR
#   - useless to surface to an AI respondent (Meta/Browser, TE/PW).
# IMPORTANT: these must be stripped BEFORE the survey is activated. The Sessions
# API caches the survey state at activation; deletions made afterward don't
# propagate, even if survey-definitions GET shows them removed (Qualtrics bug,
# discovered 2026-05-25 on Hiding Success Full).
INCOMPATIBLE_TYPE_SELECTORS = {
    ("Slider", "STAR"),
    ("Slider", "HSLIDER"),
    ("Slider", "HBAR"),
    ("Slider", "VRTL"),
    ("Timing", "PageTimer"),
    ("Timing", "FirstClick"),
    ("Timing", "LastClick"),
    ("Captcha", "V2"),
    ("Matrix", "Likert"),
    ("Meta", "Browser"),
    ("TE", "PW"),
}
MAX_HARD_STRIP_ROUNDS = 4


class ConverterError(RuntimeError):
    pass


class Qualtrics:
    def __init__(self, base_url: str, token: str):
        self._base = base_url.rstrip("/")
        self._token = token
        self._s = requests.Session()
        self._s.headers["X-API-TOKEN"] = token
        self._s.headers["Content-Type"] = "application/json"

    def whoami(self) -> dict[str, Any]:
        r = self._s.get(f"{self._base}/whoami", timeout=30)
        r.raise_for_status()
        return r.json()["result"]

    def copy_survey(self, source_id: str, new_name: str, owner_id: str) -> str:
        headers = {
            "X-API-TOKEN": self._token,
            "Content-Type": "application/json",
            "X-COPY-SOURCE": source_id,
            "X-COPY-DESTINATION-OWNER": owner_id,
        }
        r = requests.post(
            f"{self._base}/surveys",
            headers=headers,
            json={"projectName": new_name},
            timeout=60,
        )
        if r.status_code != 200:
            raise ConverterError(f"copy failed: {r.status_code} {r.text[:300]}")
        return r.json()["result"]["id"]

    def get_questions(self, survey_id: str) -> dict[str, dict]:
        r = self._s.get(f"{self._base}/survey-definitions/{survey_id}", timeout=30)
        r.raise_for_status()
        return r.json()["result"].get("Questions", {}) or {}

    def get_flow(self, survey_id: str) -> dict:
        r = self._s.get(f"{self._base}/survey-definitions/{survey_id}/flow", timeout=30)
        r.raise_for_status()
        return r.json()["result"]

    def update_flow(self, survey_id: str, flow: dict) -> None:
        r = self._s.put(
            f"{self._base}/survey-definitions/{survey_id}/flow",
            json=flow,
            timeout=30,
        )
        if r.status_code != 200:
            raise ConverterError(f"update flow failed: {r.status_code} {r.text[:200]}")

    def get_survey_name(self, survey_id: str) -> str:
        r = self._s.get(f"{self._base}/survey-definitions/{survey_id}", timeout=30)
        r.raise_for_status()
        return r.json()["result"].get("SurveyName", "")

    def delete_question(self, survey_id: str, qid: str) -> None:
        r = self._s.delete(
            f"{self._base}/survey-definitions/{survey_id}/questions/{qid}",
            timeout=30,
        )
        if r.status_code != 200:
            raise ConverterError(f"delete {qid} failed: {r.status_code} {r.text[:200]}")

    def activate(self, survey_id: str) -> None:
        r = self._s.put(
            f"{self._base}/surveys/{survey_id}",
            json={"isActive": True},
            timeout=30,
        )
        if r.status_code != 200:
            raise ConverterError(f"activate failed: {r.status_code} {r.text[:200]}")

    def delete_survey(self, survey_id: str) -> None:
        r = self._s.delete(f"{self._base}/surveys/{survey_id}", timeout=30)
        if r.status_code != 200:
            raise ConverterError(f"delete survey failed: {r.status_code} {r.text[:200]}")

    def probe_session(self, survey_id: str) -> tuple[bool, dict[str, Any], str | None]:
        """Try POST /sessions. Returns (runnable, incompatibilities, session_id_to_close).

        `incompatibilities` is the FULL block the API returns — it can contain
        a `questions` map ({qid: [reason, ...]}) and/or a `flow` map
        ({flow_id: [reason, ...]}). Empty if runnable.
        Note: QIDs returned by the Sessions API can refer to the ORIGINAL survey,
        not the current copy (Qualtrics bug). The caller should treat the reason
        strings as authoritative and match against the copy's questions by type.
        """
        r = self._s.post(f"{self._base}/surveys/{survey_id}/sessions", json={}, timeout=30)
        if r.status_code in (200, 201):
            session_id = r.json()["result"].get("sessionId")
            return True, {}, session_id
        if r.status_code == 400:
            try:
                body = r.json()
                incompat = body.get("meta", {}).get("error", {}).get("incompatibilities", {}) or {}
                return False, incompat, None
            except ValueError:
                pass
        raise ConverterError(f"probe failed unexpectedly: {r.status_code} {r.text[:300]}")

    def close_session(self, survey_id: str, session_id: str) -> None:
        try:
            self._s.post(
                f"{self._base}/surveys/{survey_id}/sessions/{session_id}",
                json={"close": True},
                timeout=15,
            )
        except Exception:
            pass


def pre_activation_strip(
    client: Qualtrics, survey_id: str, *, do_soft: bool = True
) -> list[tuple[str, str, str]]:
    """Delete known-bad questions BEFORE the survey is activated.

    Two categories:
      - INCOMPATIBLE_TYPE_SELECTORS (always stripped): types the Sessions API
        rejects (sliders, timing, captchas, matrix-likert).
      - SOFT_STRIP_TAGS (stripped if do_soft): demographics, consent,
        attention checks — useless content for an AI respondent.

    Returns list of (qid, tag, reason) removed.
    """
    questions = client.get_questions(survey_id)
    removed = []
    for qid, q in questions.items():
        tag = q.get("DataExportTag", "")
        ts = (q.get("QuestionType", ""), q.get("Selector", ""))
        reason = None
        if ts in INCOMPATIBLE_TYPE_SELECTORS:
            reason = f"incompatible-type {ts[0]}/{ts[1]}"
        elif do_soft and tag in SOFT_STRIP_TAGS:
            reason = f"tag={tag}"
        if reason:
            client.delete_question(survey_id, qid)
            removed.append((qid, tag, reason))
    return removed


def pre_activation_flow_strip(client: Qualtrics, survey_id: str) -> list[str]:
    """Neutralize EndSurvey flow elements the Sessions API rejects.

    Surveys fielded on Prolific/MTurk end with an advanced EndSurvey element that
    redirects the participant to a completion URL (EOSRedirectURL / custom
    SurveyTermination). The Sessions API refuses to start a session on a survey
    with such a redirect. An AI run never needs the participant redirect — it just
    needs to reach the end — so we strip these elements down to a plain default
    end-of-survey. Like question strips, this must happen BEFORE activation
    (Qualtrics caches survey state at activation time).

    Returns the list of FlowIDs that were neutralized.
    """
    flow = client.get_flow(survey_id)
    neutralized: list[str] = []

    def walk(el: dict) -> None:
        if el.get("Type") == "EndSurvey" and (el.get("Options") or el.get("EndingType") == "Advanced"):
            el.pop("Options", None)
            el.pop("EndingType", None)
            neutralized.append(el.get("FlowID", "?"))
        for child in el.get("Flow", []) or []:
            walk(child)

    for el in flow.get("Flow", []) or []:
        walk(el)

    if neutralized:
        client.update_flow(survey_id, flow)
    return neutralized


def _question_type_signature(q: dict) -> str:
    """Build the 'Matrix-Likert-SingleAnswer'-style signature that matches what
    the Sessions API reports in `Unsupported question type ...` messages."""
    parts = [q.get("QuestionType", ""), q.get("Selector", ""), q.get("SubSelector", "")]
    return "-".join(p for p in parts if p)


def _extract_unsupported_type(reasons: list[str]) -> str | None:
    """From a list like ['Unsupported question type Matrix-Likert-SingleAnswer'],
    return the type string. None if we can't parse it."""
    prefix = "Unsupported question type "
    for r in reasons:
        if r.startswith(prefix):
            return r[len(prefix):].strip()
    return None


def hard_strip(client: Qualtrics, survey_id: str) -> list[tuple[str, str]]:
    """Loop: probe session → delete incompatibilities → repeat until runnable.

    Strategy per round:
      1. Probe session. If runnable, done.
      2. For each (api_qid, reasons) in the incompatibility report:
         a. If api_qid exists in the current survey, delete it directly.
         b. Otherwise (Qualtrics bug returns stale QIDs after a copy),
            parse the type signature out of the reason and delete ALL
            questions in the current survey matching that signature.

    Returns list of (qid_deleted, why) for the report.
    """
    removed = []
    all_deleted: set[str] = set()
    for round_idx in range(MAX_HARD_STRIP_ROUNDS):
        runnable, incompat, session_id = client.probe_session(survey_id)
        if runnable:
            if session_id:
                client.close_session(survey_id, session_id)
            return removed

        incompat_map = incompat.get("questions") or {}
        if not incompat_map:
            # Non-question incompatibilities (e.g. flow redirects) can't be fixed
            # by deleting questions. These should have been handled pre-activation;
            # surface exactly what's wrong instead of a useless generic error.
            other = {k: v for k, v in incompat.items() if k != "questions"}
            if other:
                raise ConverterError(
                    f"survey has non-question incompatibilities that must be fixed "
                    f"before activation (e.g. end-of-survey redirects): {other}"
                )
            raise ConverterError("survey marked incompatible but API gave no details")

        # Qualtrics caches the incompatibility list: after deleting the flagged
        # QIDs, the next probe sometimes still reports them. If every flagged
        # QID is one we've already deleted in a prior round, the survey is
        # actually fine — the API just hasn't refreshed.
        flagged = set(incompat_map.keys())
        if flagged <= all_deleted:
            return removed

        qmap = client.get_questions(survey_id)
        deleted_this_round: set[str] = set()

        # Collect all "unsupported type" signatures that the API reported,
        # so we can match against the copy's questions.
        unsupported_types: set[str] = set()
        for api_qid, reasons in incompat_map.items():
            t = _extract_unsupported_type(reasons)
            if t:
                unsupported_types.add(t)
            if api_qid in qmap and api_qid not in deleted_this_round:
                client.delete_question(survey_id, api_qid)
                deleted_this_round.add(api_qid)
                removed.append((api_qid, f"API rejected {t or 'unknown'}"))

        for qid, q in list(qmap.items()):
            if qid in deleted_this_round:
                continue
            sig = _question_type_signature(q)
            if sig in unsupported_types:
                client.delete_question(survey_id, qid)
                deleted_this_round.add(qid)
                removed.append((qid, f"matched type {sig}"))

        if not deleted_this_round:
            raise ConverterError(
                f"incompatibilities reported but nothing matched. "
                f"api_qids={list(incompat_map.keys())} types_extracted={unsupported_types}"
            )
        all_deleted |= deleted_this_round

    raise ConverterError(
        f"still incompatible after {MAX_HARD_STRIP_ROUNDS} rounds; manual review needed"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("source_survey_id", help="Source survey ID (SV_...)")
    parser.add_argument("--name", help="Custom name for the new copy (default: '[orig] - AI Copy')")
    parser.add_argument("--no-soft-strip", action="store_true",
                        help="Skip the soft-strip pass (demographics/consent/attention checks stay)")
    parser.add_argument("--keep-on-failure", action="store_true",
                        help="If conversion fails, keep the partial copy for manual inspection (default: delete)")
    args = parser.parse_args()

    cfg = load_config()
    client = Qualtrics(cfg.qualtrics_base_url, cfg.qualtrics_token)
    me = client.whoami()
    owner_id = me["userId"]
    print(f"Authenticated as {me.get('userName')} ({owner_id})")

    print(f"\nFetching source survey {args.source_survey_id}...")
    src_name = client.get_survey_name(args.source_survey_id)
    src_q_count = len(client.get_questions(args.source_survey_id))
    print(f"  name: {src_name}")
    print(f"  questions: {src_q_count}")

    new_name = args.name or f"{src_name} - AI Copy"
    print(f"\nCopying to '{new_name}'...")
    new_id = client.copy_survey(args.source_survey_id, new_name, owner_id)
    print(f"  → {new_id}")

    try:
        print("\nPre-activation strip (incompatible types + soft-strip tags)...")
        pre = pre_activation_strip(client, new_id, do_soft=not args.no_soft_strip)
        for qid, tag, reason in pre:
            print(f"  - removed {qid}  ({reason})")
        print(f"  total pre-activation: {len(pre)}")

        print("\nNeutralizing end-of-survey redirects in flow...")
        flow_fixed = pre_activation_flow_strip(client, new_id)
        for fid in flow_fixed:
            print(f"  - neutralized EndSurvey {fid} (removed redirect/termination)")
        print(f"  total flow elements fixed: {len(flow_fixed)}")

        print("\nActivating copy...")
        client.activate(new_id)

        print("\nPost-activation probe (catches any types I didn't know about)...")
        hard = hard_strip(client, new_id)
        if hard:
            print("  ⚠️  Sessions API rejected additional types AFTER activation.")
            print("     These may not have actually been deleted from the live survey")
            print("     because Qualtrics caches at activation time. Consider adding the")
            print("     reported types to INCOMPATIBLE_TYPE_SELECTORS and re-running.")
            for qid, sig in hard:
                print(f"  - flagged {qid}  ({sig})")
        else:
            print("  ✓ no additional incompatibilities")

        final_count = len(client.get_questions(new_id))
        print("\n" + "=" * 60)
        print(f"DONE.  New AI-ready survey: {new_id}")
        print(f"  {src_q_count} → {final_count} questions  "
              f"(removed: {src_q_count - final_count})")
        print(f"\nRun with:")
        print(f"  python main.py run --survey-id {new_id}")
        print("=" * 60)
        return 0
    except ConverterError as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        if args.keep_on_failure:
            print(f"Keeping partial copy at {new_id} for inspection.", file=sys.stderr)
        else:
            print(f"Deleting partial copy {new_id}...", file=sys.stderr)
            try:
                client.delete_survey(new_id)
            except Exception as cleanup_err:
                print(f"  cleanup also failed: {cleanup_err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
