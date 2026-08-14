from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field, replace
from typing import Any

import requests


@dataclass
class Choice:
    choice_id: str
    text: str
    recode: int | None = None


@dataclass
class Question:
    qid: str
    export_tag: str
    question_type: str
    selector: str
    sub_selector: str
    prompt_text: str
    choices: list[Choice] = field(default_factory=list)
    sub_questions: list[Choice] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    # Loop&merge / camelCase session blocks don't carry the Selector field that
    # tells us multi- vs single-select; they put it in `options.multiSelect`
    # instead. Captured here so allows_multiple_answers can honor it.
    multi_select: bool | None = None

    @property
    def is_multiple_choice(self) -> bool:
        return self.question_type == "MC"

    @property
    def is_text_entry(self) -> bool:
        return self.question_type == "TE"

    @property
    def is_matrix(self) -> bool:
        return self.question_type == "Matrix"

    @property
    def allows_multiple_answers(self) -> bool:
        if self.multi_select is not None:
            return self.multi_select
        return self.selector in {"MAVR", "MAHR", "MACOL", "MSB"}


@dataclass
class RandomizerBranch:
    branch_id: str
    description: str
    block_ids: list[str]
    # Embedded-data values an arm sets (e.g. {"Wait": "short"}). Qualtrics often
    # uses this pattern: randomizer sets a field, downstream Branch elements
    # conditionally show blocks. Captured here so we can identify at runtime
    # which arm a session landed in by comparing against session.embedded_data.
    embedded_data: dict[str, str] = field(default_factory=dict)


@dataclass
class SurveyDefinition:
    survey_id: str
    name: str
    questions: list[Question]
    qid_to_block: dict[str, str]
    branches: list[RandomizerBranch]
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_branching_logic(self) -> bool:
        return bool(self.branches)

    def branch_for_qid(self, qid: str) -> str | None:
        block_id = self.qid_to_block.get(qid)
        if not block_id:
            return None
        for branch in self.branches:
            if block_id in branch.block_ids:
                return branch.branch_id
        return None

    def question(self, qid: str) -> Question | None:
        return next((q for q in self.questions if q.qid == qid), None)


@dataclass
class SessionBlock:
    session_id: str
    questions: list[Question]
    done: bool
    embedded_data: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class QualtricsClient:
    def __init__(self, base_url: str, token: str):
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "X-API-TOKEN": token,
            "Content-Type": "application/json",
        })

    def get_survey_definition(self, survey_id: str) -> SurveyDefinition:
        url = f"{self._base_url}/survey-definitions/{survey_id}"
        resp = self._session.get(url, timeout=30)
        _raise_with_body(resp)
        payload = resp.json()["result"]
        return _parse_survey_definition(survey_id, payload)

    def create_response(self, survey_id: str, values: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/surveys/{survey_id}/responses"
        resp = self._session.post(url, json={"values": values}, timeout=60)
        _raise_with_body(resp)
        return resp.json()["result"]

    def start_session(
        self,
        survey: SurveyDefinition,
        embedded_data: dict[str, str] | None = None,
        *,
        max_attempts: int = 4,
    ) -> SessionBlock:
        url = f"{self._base_url}/surveys/{survey.survey_id}/sessions"
        body: dict[str, Any] = {}
        if embedded_data:
            body["embeddedData"] = embedded_data
        # Qualtrics intermittently returns transient 5xx (commonly a QHRSI_2.0
        # wrapping an upstream 502/504) when many sessions are created in a short
        # window — e.g. a 600-participant panel started across 3 parallel models.
        # These are not deterministic failures; a retry with jittered backoff
        # almost always succeeds. Non-transient errors (4xx, auth) fail fast via
        # _raise_with_body. Jitter keeps the parallel per-model runs from retrying
        # in lockstep and re-spiking the server. Mirrors convert_to_ai.probe_session.
        resp = None
        for attempt in range(max_attempts):
            if attempt:
                backoff = min(20, 3 * 2 ** (attempt - 1))  # 3s, 6s, 12s (cap 20)
                time.sleep(backoff + random.uniform(0, 1.5))
            resp = self._session.post(url, json=body, timeout=60)
            if resp.ok:
                result = resp.json()["result"]
                return _parse_session_block(result, survey)
            if attempt < max_attempts - 1 and _is_transient_response(resp):
                print(
                    f"  start_session {resp.status_code} on {survey.survey_id}, "
                    f"retrying (attempt {attempt + 1}/{max_attempts})...",
                    flush=True,
                )
                continue
            break
        _raise_with_body(resp)  # non-transient, or retries exhausted — always raises
        raise RuntimeError("unreachable")  # for type-checkers

    def advance_session(
        self,
        survey: SurveyDefinition,
        session_id: str,
        responses: dict[str, Any],
    ) -> SessionBlock:
        url = f"{self._base_url}/surveys/{survey.survey_id}/sessions/{session_id}"
        body = {"advance": True, "responses": responses}
        resp = self._session.post(url, json=body, timeout=60)
        _raise_with_body(resp)
        result = resp.json()["result"]
        return _parse_session_block(result, survey, fallback_session_id=session_id)

    def close_session(self, survey_id: str, session_id: str) -> None:
        url = f"{self._base_url}/surveys/{survey_id}/sessions/{session_id}"
        resp = self._session.post(url, json={"close": True}, timeout=30)
        _raise_with_body(resp)


def _is_transient_response(resp: requests.Response) -> bool:
    """True for Qualtrics responses worth retrying — gateway/internal server
    errors that occur under load rather than deterministic request failures."""
    if resp.status_code in (500, 502, 503, 504):
        return True
    body = resp.text or ""
    return any(s in body for s in ("QHRSI", "QHRI", "Gateway Time-out", "Gateway Timeout"))


def _raise_with_body(resp: requests.Response) -> None:
    if resp.ok:
        return
    body = resp.text[:1000] if resp.text else "<no body>"
    raise requests.HTTPError(
        f"{resp.status_code} {resp.reason} for {resp.request.method} {resp.url}\n"
        f"Response body: {body}",
        response=resp,
    )


def _parse_session_block(
    result: dict[str, Any],
    survey: SurveyDefinition,
    fallback_session_id: str | None = None,
) -> SessionBlock:
    # The Sessions API response uses camelCase and a list shape, distinct from
    # the Survey Definition API's PascalCase dict. We lean on the SurveyDefinition
    # (already parsed) for fields the session payload doesn't expose (recode
    # values, selectors, export tags), and use the session's `display` for prompt
    # text since it has piped variables like ${e://Field/dv} resolved.
    #
    # Loop & merge wrinkle: questionId may be "{iteration}_QID..." (e.g.
    # "1_QID451"). The base question is QID451 in the survey def; we strip the
    # iteration prefix to look it up but keep the prefixed id as the question's
    # qid so submission keys match what Qualtrics expects.
    raw_questions = result.get("questions") or []
    questions: list[Question] = []
    for q in raw_questions:
        qid = q.get("questionId")
        if not qid:
            continue
        base_qid = _strip_loop_prefix(qid)
        base = survey.question(base_qid)
        if base is not None:
            display = _strip_html(q.get("display", "")) or base.prompt_text
            # When base differs from raw qid (loop iteration), rewrite qid to the
            # iteration-prefixed form so submissions use the same key.
            questions.append(replace(base, qid=qid, prompt_text=display))
        else:
            # Fallback: parse what we can directly from the camelCase entry.
            # Happens when the survey def doesn't expose the question (rare).
            questions.append(_parse_question_camel(q))
    return SessionBlock(
        session_id=result.get("sessionId") or fallback_session_id or "",
        questions=questions,
        done=bool(result.get("done")),
        embedded_data=result.get("embeddedData") or {},
        raw=result,
    )


# Matches loop-iteration prefixes like "1_QID451", "12_QID7". Stripped to look
# up the underlying base question in the survey definition.
_LOOP_PREFIX_RE = re.compile(r"^(\d+)_(QID.+)$")


def _strip_loop_prefix(qid: str) -> str:
    m = _LOOP_PREFIX_RE.match(qid)
    return m.group(2) if m else qid


# camelCase `type` → PascalCase QuestionType used elsewhere in this module.
_TYPE_MAP = {"db": "DB", "mc": "MC", "te": "TE", "matrix": "Matrix", "slider": "Slider"}


def _parse_question_camel(entry: dict[str, Any]) -> Question:
    """Parse a session-block question in the camelCase / list shape used by
    loop & merge surveys. Used only when the survey definition doesn't have a
    base record for this question (e.g. dynamically-generated questions)."""
    qid = entry.get("questionId", "")
    qtype = _TYPE_MAP.get((entry.get("type") or "").lower(), entry.get("type") or "")
    choices = []
    for c in entry.get("choices") or []:
        cid = str(c.get("choiceId", ""))
        text = _strip_html(c.get("display", ""))
        try:
            recode = int(cid)
        except (TypeError, ValueError):
            recode = None
        choices.append(Choice(choice_id=cid, text=text, recode=recode))
    options = entry.get("options") or {}
    return Question(
        qid=qid,
        export_tag=qid,
        question_type=qtype,
        selector="",
        sub_selector="",
        prompt_text=_strip_html(entry.get("display", "")),
        choices=choices,
        multi_select=options.get("multiSelect"),
        raw=entry,
    )


def _parse_survey_definition(survey_id: str, payload: dict[str, Any]) -> SurveyDefinition:
    raw_questions = payload.get("Questions", {})
    questions = [_parse_question(qid, q) for qid, q in raw_questions.items()]

    qid_to_block = _build_qid_to_block(payload.get("Blocks") or {})
    branches = _extract_randomizer_branches(payload.get("SurveyFlow") or {})

    return SurveyDefinition(
        survey_id=survey_id,
        name=payload.get("SurveyName", ""),
        questions=questions,
        qid_to_block=qid_to_block,
        branches=branches,
        raw=payload,
    )


def _build_qid_to_block(blocks: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for block_id, block in blocks.items():
        for element in block.get("BlockElements") or []:
            if element.get("Type") == "Question":
                qid = element.get("QuestionID")
                if qid:
                    out[qid] = block_id
    return out


def _extract_randomizer_branches(flow: dict[str, Any]) -> list[RandomizerBranch]:
    branches: list[RandomizerBranch] = []
    _walk_flow_for_randomizers(flow, branches)
    return branches


def _walk_flow_for_randomizers(node: dict[str, Any], out: list[RandomizerBranch]) -> None:
    if not node:
        return
    node_type = node.get("Type")
    if node_type in {"BlockRandomizer", "Randomizer"}:
        for group in node.get("Flow") or []:
            branch_id = group.get("FlowID") or group.get("ID") or ""
            embedded_data = _collect_embedded_data(group)
            block_ids = _collect_block_ids(group)
            description = group.get("Description") or _describe_embedded(embedded_data) or branch_id or "<unnamed branch>"
            out.append(RandomizerBranch(
                branch_id=branch_id,
                description=description,
                block_ids=block_ids,
                embedded_data=embedded_data,
            ))
        return
    for child in node.get("Flow") or []:
        _walk_flow_for_randomizers(child, out)


def _collect_block_ids(node: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    if not node:
        return ids
    if node.get("Type") == "Block" and node.get("ID"):
        ids.append(node["ID"])
    for child in node.get("Flow") or []:
        ids.extend(_collect_block_ids(child))
    return ids


def _collect_embedded_data(node: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    if not node:
        return out
    if node.get("Type") == "EmbeddedData":
        for entry in node.get("EmbeddedData") or []:
            field_name = entry.get("Field")
            value = entry.get("Value")
            if field_name and value is not None:
                out[field_name] = str(value)
    for child in node.get("Flow") or []:
        out.update(_collect_embedded_data(child))
    return out


def _describe_embedded(embedded: dict[str, str]) -> str:
    return ", ".join(f"{k}={v}" for k, v in embedded.items())


def _parse_question(qid: str, q: dict[str, Any]) -> Question:
    choices_raw = q.get("Choices") or {}
    choice_order = q.get("ChoiceOrder") or list(choices_raw.keys())
    recode_values = q.get("RecodeValues") or {}

    choices: list[Choice] = []
    for cid in choice_order:
        c = choices_raw.get(str(cid)) or choices_raw.get(cid)
        if not c:
            continue
        recode = recode_values.get(str(cid))
        try:
            recode_int = int(recode) if recode is not None else int(cid)
        except (TypeError, ValueError):
            recode_int = None
        choices.append(Choice(
            choice_id=str(cid),
            text=_strip_html(c.get("Display", "")),
            recode=recode_int,
        ))

    sub_raw = q.get("Answers") or {}
    sub_order = q.get("AnswerOrder") or list(sub_raw.keys())
    sub_questions: list[Choice] = []
    for sid in sub_order:
        s = sub_raw.get(str(sid)) or sub_raw.get(sid)
        if not s:
            continue
        sub_questions.append(Choice(
            choice_id=str(sid),
            text=_strip_html(s.get("Display", "")),
        ))

    return Question(
        qid=qid,
        export_tag=q.get("DataExportTag", qid),
        question_type=q.get("QuestionType", ""),
        selector=q.get("Selector", ""),
        sub_selector=q.get("SubSelector", ""),
        prompt_text=_strip_html(q.get("QuestionText", "")),
        choices=choices,
        sub_questions=sub_questions,
        raw=q,
    )


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()
