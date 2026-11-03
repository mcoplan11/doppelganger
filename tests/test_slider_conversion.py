"""Unit tests for convert_sliders_to_te (no network — fake Qualtrics client).

The live end-to-end path (create survey → convert → activate → run a session)
was verified against the real Sessions API on 2026-11-02; these tests pin the
payload-building logic so regressions surface without an API token.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from convert_to_ai import _fmt_bound, _slider_bounds, convert_sliders_to_te


class FakeQualtrics:
    def __init__(self, questions: dict, blocks: dict):
        self._questions = questions
        self._blocks = blocks
        self.created: list[tuple[dict, str | None]] = []
        self.deleted: list[str] = []

    def get_definition(self, survey_id):
        return {"Questions": self._questions, "Blocks": self._blocks}

    def create_question(self, survey_id, payload, block_id=None):
        self.created.append((payload, block_id))
        return f"QID_NEW{len(self.created)}"

    def delete_question(self, survey_id, qid):
        self.deleted.append(qid)


def _slider(selector="HSLIDER", cfg=None, choices=None, tag="dv", text="Rate it."):
    return {
        "QuestionType": "Slider",
        "Selector": selector,
        "QuestionText": text,
        "DataExportTag": tag,
        "Configuration": {"CSSliderMin": 0, "CSSliderMax": 100, "NumDecimals": "0",
                          **(cfg or {})},
        "Choices": choices if choices is not None else {"1": {"Display": "Overall"}},
        "ChoiceOrder": list((choices or {"1": None}).keys()),
    }


BLOCKS = {"BL_1": {"BlockElements": [{"Type": "Question", "QuestionID": "QID1"}]}}


def test_multi_statement_slider_explodes_per_row():
    q = _slider(choices={"1": {"Display": "Trust"}, "2": {"Display": "Warmth"}})
    client = FakeQualtrics({"QID1": q}, BLOCKS)
    result = convert_sliders_to_te(client, "SV_x")

    assert result == [("QID1", ["QID_NEW1", "QID_NEW2"])]
    assert client.deleted == ["QID1"]
    tags = [p["DataExportTag"] for p, _ in client.created]
    assert tags == ["dv_1", "dv_2"]
    for payload, block_id in client.created:
        assert (payload["QuestionType"], payload["Selector"]) == ("TE", "SL")
        assert "between 0 and 100" in payload["QuestionText"]
        # must match simulator._NUMERIC_HINTS so answers reduce to a number
        assert "please enter the number" in payload["QuestionText"].lower()
        assert block_id == "BL_1"
    assert "Trust" in client.created[0][0]["QuestionText"]
    assert "Warmth" in client.created[1][0]["QuestionText"]


def test_single_statement_slider_keeps_original_tag():
    client = FakeQualtrics({"QID1": _slider()}, BLOCKS)
    convert_sliders_to_te(client, "SV_x")
    assert [p["DataExportTag"] for p, _ in client.created] == ["dv"]


def test_custom_range_and_decimals_in_prompt():
    q = _slider(cfg={"CSSliderMin": 1, "CSSliderMax": 7, "NumDecimals": "2"})
    client = FakeQualtrics({"QID1": q}, BLOCKS)
    convert_sliders_to_te(client, "SV_x")
    text = client.created[0][0]["QuestionText"]
    assert "between 1 and 7" in text
    assert "2 decimal place" in text


def test_star_without_bounds_defaults_to_numstars():
    q = {"Selector": "STAR", "Configuration": {"NumStars": 7}}
    assert _slider_bounds(q) == (1.0, 7.0, 0)


def test_non_slider_questions_untouched():
    mc = {"QuestionType": "MC", "Selector": "SAVR"}
    client = FakeQualtrics({"QID1": mc}, BLOCKS)
    assert convert_sliders_to_te(client, "SV_x") == []
    assert client.created == [] and client.deleted == []


def test_fmt_bound_trims_whole_floats():
    assert _fmt_bound(100.0) == "100"
    assert _fmt_bound(2.5) == "2.5"
