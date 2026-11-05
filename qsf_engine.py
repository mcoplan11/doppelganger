"""Run a Qualtrics survey locally from a .qsf export — no Qualtrics account needed.

Three parts:
  - parse_qsf():   .qsf JSON → ParsedQsf (reuses qualtrics_client's question/
                   branch parsing, so Question/SurveyDefinition objects are
                   identical to the API path's).
  - validate_qsf(): strict whitelist over flow elements and logic expressions.
                   Anything we can't execute faithfully is REJECTED with a
                   human-readable reason — we never guess at survey logic.
  - LocalSessionEngine: duck-types the two QualtricsClient methods the
                   simulator uses (start_session / advance_session), walking
                   the QSF flow per respondent: randomizer assignment, branch
                   conditions, embedded data, display logic, basic piping.

Design notes:
  - One SessionBlock per survey block (the Sessions API paginates within
    blocks; answering block-at-a-time preserves the same reading order).
  - BlockRandomizer with EvenPresentation balances across the engine's
    lifetime (per model run), matching Qualtrics's evenly-present behavior
    closely enough for pretest sample sizes.
  - Sliders become numeric text-entry items (same transformation and prompt
    wording as convert_to_ai.convert_sliders_to_te) so the LLM answers on the
    original scale. Matrix questions run natively — there is no Sessions API
    here to reject them.
"""
from __future__ import annotations

import json
import random
import re
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any, Iterator

from qualtrics_client import (
    Question,
    SessionBlock,
    SurveyDefinition,
    _parse_survey_definition,
)


class QsfError(ValueError):
    """Raised when a QSF can't be parsed or uses unsupported features."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


# Question (type, selector-prefix) pairs that are dropped at parse time:
# machinery for human respondents that an AI panel never needs.
_DROP_QUESTION_TYPES = {"Timing", "Captcha", "Meta"}

# Flow element types we can execute faithfully.
_SUPPORTED_FLOW_TYPES = {
    "Block", "Standard", "BlockRandomizer", "Randomizer", "Branch",
    "EmbeddedData", "EndSurvey", "Group", "Root",
}

# Logic operators we evaluate. Anything else fails validation.
_SUPPORTED_OPERATORS = {
    "EqualTo", "NotEqualTo", "Selected", "NotSelected",
    "GreaterThan", "GreaterThanOrEqual", "LessThan", "LessThanOrEqual",
    "Displayed", "NotDisplayed",
}
_SUPPORTED_LOGIC_TYPES = {"EmbeddedField", "Question"}

_PIPE_RE = re.compile(r"\$\{([^}]*)\}")


@dataclass
class ParsedQsf:
    definition: SurveyDefinition
    flow: list[dict]                      # the FL Payload Flow list
    blocks: dict[str, dict]               # block_id -> block payload
    questions: dict[str, Question]        # qid -> parsed Question (post-transform)
    display_logic: dict[str, dict]        # qid -> raw DisplayLogic payload
    raw_question_payloads: dict[str, dict]


# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_qsf(qsf: str | bytes | dict) -> ParsedQsf:
    """Parse a .qsf export. Raises QsfError on malformed input."""
    if isinstance(qsf, (str, bytes)):
        try:
            qsf = json.loads(qsf)
        except (ValueError, UnicodeDecodeError) as exc:
            raise QsfError([f"File is not valid QSF JSON: {exc}"]) from exc
    if not isinstance(qsf, dict) or "SurveyElements" not in qsf:
        raise QsfError(["File is not a Qualtrics .qsf export (no SurveyElements)."])

    name = (qsf.get("SurveyEntry") or {}).get("SurveyName", "Uploaded survey")

    question_payloads: dict[str, dict] = {}
    blocks: dict[str, dict] = {}
    flow: list[dict] = []
    for el in qsf.get("SurveyElements") or []:
        kind = el.get("Element")
        payload = el.get("Payload")
        if kind == "SQ" and isinstance(payload, dict):
            qid = payload.get("QuestionID") or el.get("PrimaryAttribute")
            if qid:
                question_payloads[qid] = payload
        elif kind == "BL":
            # Block payload is a dict keyed by index in some exports, a list in others.
            entries = payload.values() if isinstance(payload, dict) else (payload or [])
            for b in entries:
                if isinstance(b, dict) and b.get("ID"):
                    blocks[b["ID"]] = b
        elif kind == "FL" and isinstance(payload, dict):
            flow = payload.get("Flow") or []

    if not flow:
        raise QsfError(["The .qsf has no survey flow — nothing to run."])
    if not question_payloads:
        raise QsfError(["The .qsf contains no questions."])

    # Build a survey-definitions-shaped payload so qualtrics_client's parser
    # produces the exact same Question/SurveyDefinition objects as API mode.
    def_payload = {
        "SurveyName": name,
        "Questions": question_payloads,
        "Blocks": blocks,
        "SurveyFlow": {"Flow": flow},
    }
    definition = _parse_survey_definition("qsf_local", def_payload, origin="")

    questions: dict[str, Question] = {}
    display_logic: dict[str, dict] = {}
    for q in definition.questions:
        payload = question_payloads.get(q.qid) or {}
        if payload.get("QuestionType") in _DROP_QUESTION_TYPES:
            continue
        dl = payload.get("DisplayLogic")
        if isinstance(dl, dict):
            display_logic[q.qid] = dl
        questions[q.qid] = q

    parsed = ParsedQsf(
        definition=definition,
        flow=flow,
        blocks=blocks,
        questions=questions,
        display_logic=display_logic,
        raw_question_payloads=question_payloads,
    )
    _transform_sliders(parsed)
    return parsed


def _slider_items(q: Question, payload: dict) -> list[Question]:
    """Mirror convert_to_ai.convert_sliders_to_te locally: one numeric
    text-entry item per slider statement, same scale, same prompt wording."""
    cfg = payload.get("Configuration") or {}

    def _num(val: Any, default: float) -> float:
        try:
            return float(val)
        except (TypeError, ValueError):
            return float(default)

    if payload.get("Selector") == "STAR" and cfg.get("CSSliderMax") in (None, ""):
        lo, hi, decimals = 1.0, _num(cfg.get("NumStars"), 5), 0
    else:
        lo = _num(cfg.get("CSSliderMin"), 0)
        hi = _num(cfg.get("CSSliderMax"), 100)
        decimals = int(_num(cfg.get("NumDecimals"), 0))

    def _fmt(v: float) -> str:
        return str(int(v)) if float(v).is_integer() else str(v)

    note = (f"Please enter the number between {_fmt(lo)} and {_fmt(hi)} "
            f"that best represents your answer.")
    if decimals:
        note += f" Up to {decimals} decimal place(s) allowed."

    statements = q.choices or []
    items: list[Question] = []
    if len(statements) <= 1:
        text = statements[0].text if statements else ""
        prompt = q.prompt_text + (f"\n{text}" if text else "") + f"\n{note}"
        items.append(replace(
            q, question_type="TE", selector="SL", sub_selector="",
            prompt_text=prompt, choices=[], sub_questions=[],
        ))
    else:
        for st in statements:
            items.append(replace(
                q,
                qid=f"{q.qid}_{st.choice_id}",
                export_tag=f"{q.export_tag}_{st.choice_id}",
                question_type="TE", selector="SL", sub_selector="",
                prompt_text=f"{q.prompt_text}\n{st.text}\n{note}",
                choices=[], sub_questions=[],
            ))
    return items


def _transform_sliders(parsed: ParsedQsf) -> None:
    for qid in list(parsed.questions):
        q = parsed.questions[qid]
        if q.question_type != "Slider":
            continue
        payload = parsed.raw_question_payloads.get(qid) or {}
        items = _slider_items(q, payload)
        del parsed.questions[qid]
        dl = parsed.display_logic.pop(qid, None)
        for item in items:
            parsed.questions[item.qid] = item
            if dl is not None:
                parsed.display_logic[item.qid] = dl
        # Children inherit the parent's slot in block order via _expand_qid.


# ── Validation ───────────────────────────────────────────────────────────────

def validate_qsf(parsed: ParsedQsf) -> list[str]:
    """Return a list of human-readable problems. Empty list = runnable."""
    problems: list[str] = []
    seen: set[str] = set()

    def add(msg: str) -> None:
        if msg not in seen:
            seen.add(msg)
            problems.append(msg)

    def walk(node: dict) -> None:
        t = node.get("Type") or ""
        if t not in _SUPPORTED_FLOW_TYPES:
            add(f"Unsupported survey-flow element: {t or 'unknown'}. "
                "QSF mode supports blocks, randomizers, branches, and embedded data.")
        if t == "Branch":
            _validate_logic(node.get("BranchLogic"), "a branch condition", add)
        if t in ("Block", "Standard") and (node.get("ID") or "") not in parsed.blocks:
            add(f"Flow references block {node.get('ID') or '?'}, which doesn't exist in the file.")
        for child in node.get("Flow") or []:
            walk(child)

    for node in parsed.flow:
        walk(node)

    # Loop & merge lives on the block, not the flow.
    for bid, block in parsed.blocks.items():
        looping = (block.get("Options") or {}).get("Looping")
        if looping and looping not in ("None", "Off"):
            desc = block.get("Description") or bid
            add(f"Block “{desc}” uses Loop & Merge, which QSF mode doesn't support yet. "
                "Use the Qualtrics API connection for this survey.")

    for qid, dl in parsed.display_logic.items():
        _validate_logic(dl, f"display logic on {qid}", add)

    return problems


def _iter_expressions(logic: Any) -> Iterator[dict]:
    """Yield every leaf Expression inside a BooleanExpression payload."""
    if not isinstance(logic, dict):
        return
    if logic.get("Type") == "Expression":
        yield logic
        return
    for key, value in logic.items():
        if key in ("Type", "inPage"):
            continue
        yield from _iter_expressions(value)


def _validate_logic(logic: Any, where: str, add) -> None:
    if logic is None:
        return
    exprs = list(_iter_expressions(logic))
    if not exprs:
        add(f"Could not read {where} — the condition format is unsupported.")
        return
    for e in exprs:
        lt = e.get("LogicType") or ""
        op = e.get("Operator") or ""
        if lt not in _SUPPORTED_LOGIC_TYPES:
            add(f"Unsupported condition type “{lt}” in {where}. "
                "QSF mode evaluates embedded-data and question-choice conditions.")
            continue
        if op not in _SUPPORTED_OPERATORS:
            add(f"Unsupported condition operator “{op}” in {where}.")
        if lt == "Question":
            left = e.get("LeftOperand") or ""
            if not re.match(r"^q://[^/]+(/SelectableChoice/[^/]+|/ChoiceTextEntryValue.*)?$", left):
                add(f"Unsupported question reference “{left}” in {where}.")


# ── Flow walking / session engine ────────────────────────────────────────────

class _EndSurveyReached(Exception):
    pass


@dataclass
class _SessionState:
    session_id: str
    embedded_data: dict[str, str] = field(default_factory=dict)
    selected: dict[str, set[str]] = field(default_factory=dict)   # qid -> choice ids
    texts: dict[str, str] = field(default_factory=dict)           # qid -> text answer
    matrices: dict[str, dict[str, str]] = field(default_factory=dict)  # qid -> sub -> choice
    displayed: set[str] = field(default_factory=set)
    walker: Iterator[list[Question]] | None = None
    done: bool = False


class LocalSessionEngine:
    """Duck-types QualtricsClient.start_session / advance_session for
    simulator.run_many, executing the QSF flow in-process."""

    def __init__(self, parsed: ParsedQsf, seed: int | None = None):
        self._p = parsed
        self._rng = random.Random(seed)
        self._sessions: dict[str, _SessionState] = {}
        self._rand_counts: dict[str, Counter] = {}
        self._lock = threading.Lock()

    # -- public interface (mirrors QualtricsClient) --------------------------

    def start_session(self, survey: SurveyDefinition, embedded_data=None, **_: Any) -> SessionBlock:
        state = _SessionState(session_id=f"local_{uuid.uuid4().hex[:16]}")
        if embedded_data:
            state.embedded_data.update({k: str(v) for k, v in embedded_data.items()})
        state.walker = self._walk(self._p.flow, state)
        with self._lock:
            self._sessions[state.session_id] = state
        return self._next_block(state)

    def advance_session(
        self, survey: SurveyDefinition, session_id: str, responses: dict[str, Any]
    ) -> SessionBlock:
        with self._lock:
            state = self._sessions.get(session_id)
        if state is None:
            raise KeyError(f"unknown local session {session_id}")
        self._record(state, responses)
        return self._next_block(state)

    def close_session(self, survey_id: str, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    # -- internals ------------------------------------------------------------

    def _next_block(self, state: _SessionState) -> SessionBlock:
        questions: list[Question] = []
        try:
            while True:
                questions = next(state.walker)  # type: ignore[arg-type]
                if questions:
                    break
        except (StopIteration, _EndSurveyReached):
            state.done = True
            questions = []
        return SessionBlock(
            session_id=state.session_id,
            questions=questions,
            done=state.done,
            embedded_data=dict(state.embedded_data),
        )

    def _walk(self, nodes: list[dict], state: _SessionState) -> Iterator[list[Question]]:
        for node in nodes:
            t = node.get("Type") or ""
            if t == "EmbeddedData":
                for entry in node.get("EmbeddedData") or []:
                    name = entry.get("Field")
                    if not name:
                        continue
                    value = entry.get("Value")
                    # Fields declared without a value (e.g. PROLIFIC_PID from
                    # the URL) stay as-is if already set, else empty string.
                    if value is not None:
                        state.embedded_data[name] = str(value)
                    else:
                        state.embedded_data.setdefault(name, "")
            elif t in ("Block", "Standard"):
                block = self._p.blocks.get(node.get("ID") or "")
                if block is not None:
                    yield self._emit_block(block, state)
            elif t in ("BlockRandomizer", "Randomizer"):
                children = node.get("Flow") or []
                if children:
                    chosen = self._pick(node, children)
                    yield from self._walk(chosen, state)
            elif t == "Branch":
                if _eval_logic(node.get("BranchLogic"), state):
                    yield from self._walk(node.get("Flow") or [], state)
            elif t in ("Group", "Root"):
                yield from self._walk(node.get("Flow") or [], state)
            elif t == "EndSurvey":
                raise _EndSurveyReached()
            # Unsupported types were rejected at validation; ignore defensively.

    def _pick(self, node: dict, children: list[dict]) -> list[dict]:
        """Choose SubSet children. EvenPresentation balances assignment counts
        across the engine's lifetime; otherwise uniform random."""
        try:
            k = int(node.get("SubSet") or 0)
        except (TypeError, ValueError):
            k = 0
        if k <= 0 or k >= len(children):
            # SubSet 0 / missing = present all, randomized order.
            order = list(children)
            with self._lock:
                self._rng.shuffle(order)
            return order
        key = node.get("FlowID") or id(node)
        with self._lock:
            counts = self._rand_counts.setdefault(str(key), Counter())
            indexed = list(enumerate(children))
            self._rng.shuffle(indexed)  # tie-break randomly
            if node.get("EvenPresentation"):
                indexed.sort(key=lambda pair: counts[pair[0]])
                chosen = indexed[:k]
            else:
                chosen = indexed[:k]
            for idx, _child in chosen:
                counts[idx] += 1
        return [child for _idx, child in chosen]

    def _emit_block(self, block: dict, state: _SessionState) -> list[Question]:
        out: list[Question] = []
        for element in block.get("BlockElements") or []:
            if element.get("Type") != "Question":
                continue  # page breaks etc.
            for q in self._expand_qid(element.get("QuestionID") or ""):
                dl = self._p.display_logic.get(q.qid)
                if dl is not None and not _eval_logic(dl, state):
                    continue
                state.displayed.add(q.qid)
                out.append(replace(q, prompt_text=_resolve_pipes(q.prompt_text, state, self._p)))
        return out

    def _expand_qid(self, qid: str) -> list[Question]:
        """A block references the original QID; sliders may have been split
        into per-statement items keyed qid_choice."""
        if qid in self._p.questions:
            return [self._p.questions[qid]]
        prefix = f"{qid}_"
        return [q for k, q in self._p.questions.items() if k.startswith(prefix)]

    def _record(self, state: _SessionState, responses: dict[str, Any]) -> None:
        """Parse the Qualtrics submission shape back into answer state.
        Shapes (see simulator._gemini_answers_to_qualtrics):
          MC:     {qid: {choiceId: {"selected": true}, ...}}
          TE:     {qid: "free text"}
          Matrix: {qid: {subId: {choiceId: {"selected": true}}}}
        """
        for qid, value in (responses or {}).items():
            if isinstance(value, dict):
                if any(isinstance(v, dict) and "selected" in v for v in value.values()):
                    state.selected[qid] = {
                        str(cid) for cid, v in value.items()
                        if isinstance(v, dict) and v.get("selected")
                    }
                else:  # matrix: sub -> {choice: {selected}}
                    rows: dict[str, str] = {}
                    for sub, inner in value.items():
                        if isinstance(inner, dict):
                            for cid, flag in inner.items():
                                if isinstance(flag, dict) and flag.get("selected"):
                                    rows[str(sub)] = str(cid)
                    state.matrices[qid] = rows
            else:
                state.texts[qid] = str(value)


# ── Logic evaluation ─────────────────────────────────────────────────────────

_Q_CHOICE_RE = re.compile(r"^q://([^/]+)/SelectableChoice/(.+)$")
_Q_TEXT_RE = re.compile(r"^q://([^/]+)/ChoiceTextEntryValue")
_Q_BARE_RE = re.compile(r"^q://([^/]+)$")


def _eval_logic(logic: Any, state: _SessionState) -> bool:
    """Evaluate a BooleanExpression payload against session state.
    Expressions within an If-set combine left-to-right via each expression's
    Conjuction (And/Or), matching Qualtrics's sequential evaluation."""
    if not isinstance(logic, dict):
        return True
    if logic.get("Type") == "Expression":
        return _eval_expression(logic, state)

    result: bool | None = None
    for key in sorted(k for k in logic.keys() if k.isdigit()):
        clause = logic[key]
        if not isinstance(clause, dict):
            continue
        value = _eval_logic(clause, state)
        conj = (clause.get("Conjuction") or clause.get("Conjunction") or "And")
        if result is None:
            result = value
        elif conj == "Or":
            result = result or value
        else:
            result = result and value
    return True if result is None else result


def _eval_expression(e: dict, state: _SessionState) -> bool:
    lt = e.get("LogicType")
    op = e.get("Operator") or ""
    left_ref = e.get("LeftOperand") or ""
    right = e.get("RightOperand")

    if lt == "EmbeddedField":
        left = state.embedded_data.get(left_ref, "")
        return _compare(op, left, right)

    if lt == "Question":
        m = _Q_CHOICE_RE.match(left_ref)
        if m:
            qid, cid = m.group(1), m.group(2)
            chosen = state.selected.get(qid, set())
            if op == "Selected":
                return cid in chosen
            if op == "NotSelected":
                return cid not in chosen
            return _compare(op, "1" if cid in chosen else "0", right)
        m = _Q_TEXT_RE.match(left_ref)
        if m:
            return _compare(op, state.texts.get(m.group(1), ""), right)
        m = _Q_BARE_RE.match(left_ref)
        if m:
            if op == "Displayed":
                return m.group(1) in state.displayed
            if op == "NotDisplayed":
                return m.group(1) not in state.displayed
    return False


def _compare(op: str, left: Any, right: Any) -> bool:
    ls, rs = str(left or "").strip(), str(right or "").strip()
    if op == "EqualTo":
        return ls == rs
    if op == "NotEqualTo":
        return ls != rs
    try:
        ln, rn = float(ls), float(rs)
    except (TypeError, ValueError):
        return False
    if op == "GreaterThan":
        return ln > rn
    if op == "GreaterThanOrEqual":
        return ln >= rn
    if op == "LessThan":
        return ln < rn
    if op == "LessThanOrEqual":
        return ln <= rn
    return False


# ── Piping ───────────────────────────────────────────────────────────────────

def _resolve_pipes(text: str, state: _SessionState, parsed: ParsedQsf) -> str:
    """Resolve ${e://Field/X} and ${q://QID/...} pipes against session state;
    unknown pipes are stripped so the LLM never sees raw ${...} syntax."""
    if "${" not in (text or ""):
        return text

    def sub(m: re.Match) -> str:
        ref = m.group(1)
        if ref.startswith("e://Field/"):
            return state.embedded_data.get(ref[len("e://Field/"):], "")
        qm = re.match(r"^q://([^/]+)/ChoiceGroup/SelectedChoices", ref)
        if qm:
            qid = qm.group(1)
            q = parsed.questions.get(qid)
            chosen = state.selected.get(qid, set())
            if q:
                texts = [c.text for c in q.choices if c.choice_id in chosen]
                return ", ".join(texts)
            return ""
        qm = re.match(r"^q://([^/]+)/ChoiceTextEntryValue", ref)
        if qm:
            return state.texts.get(qm.group(1), "")
        return ""

    return _PIPE_RE.sub(sub, text)
