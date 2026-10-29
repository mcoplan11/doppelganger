"""Unit tests for image-stimulus support (no network: fetch helpers mocked).

Covers the pipeline stages in order: <img> extraction from Qualtrics HTML,
Question/SurveyDefinition parsing, prompt annotation + attachment ordering,
and the OpenRouter multimodal message shape.
"""
from unittest.mock import patch

import gemini_client
import openrouter_client
import stimuli
from gemini_client import (
    _build_prompt,
    _is_answerable,
    collect_image_urls,
    image_labels_for,
)
from personas import Persona
from qualtrics_client import (
    Question,
    _parse_question,
    _parse_session_block,
    _parse_survey_definition,
)
from stimuli import extract_image_urls, origin_of

ORIGIN = "https://yul1.qualtrics.com"


def _q(qid: str, qtype: str = "MC", text: str = "prompt", images: list[str] | None = None):
    return Question(
        qid=qid, export_tag=qid, question_type=qtype, selector="SAVR",
        sub_selector="", prompt_text=text, image_urls=images or [],
    )


# ── stimuli.extract_image_urls ───────────────────────────────────────────────

def test_extract_absolute_url():
    html = '<p>Rate this ad:</p><img src="https://cdn.example.com/ad.png" alt="">'
    assert extract_image_urls(html) == ["https://cdn.example.com/ad.png"]


def test_extract_relative_url_absolutized_against_origin():
    html = '<img src="/ControlPanel/Graphic.php?IM=IM_abc&amp;v=1">'
    assert extract_image_urls(html, ORIGIN) == [
        f"{ORIGIN}/ControlPanel/Graphic.php?IM=IM_abc&v=1"
    ]


def test_extract_relative_url_dropped_without_origin():
    assert extract_image_urls('<img src="/ControlPanel/Graphic.php?IM=IM_abc">') == []


def test_extract_dedupes_and_preserves_order():
    html = (
        '<img src="https://a.com/1.png"><img src="https://a.com/2.png">'
        '<img src="https://a.com/1.png">'
    )
    assert extract_image_urls(html) == ["https://a.com/1.png", "https://a.com/2.png"]


def test_extract_ignores_non_http_and_handles_no_images():
    assert extract_image_urls('<img src="javascript:alert(1)">') == []
    assert extract_image_urls("<p>plain text</p>") == []
    assert extract_image_urls("") == []


def test_origin_of():
    assert origin_of("https://yul1.qualtrics.com/API/v3") == ORIGIN


# ── qualtrics_client parsing ─────────────────────────────────────────────────

def test_parse_question_extracts_images_and_strips_html():
    q = _parse_question("QID1", {
        "QuestionText": '<p>Rate this product</p><img src="https://a.com/p.jpg">',
        "QuestionType": "MC",
        "Selector": "SAVR",
        "Choices": {"1": {"Display": "Good"}, "2": {"Display": "Bad"}},
    }, ORIGIN)
    assert q.image_urls == ["https://a.com/p.jpg"]
    assert q.prompt_text == "Rate this product"


def test_session_block_display_images_override_definition():
    survey = _parse_survey_definition("SV_x", {
        "SurveyName": "s",
        "Questions": {"QID1": {
            "QuestionText": '<img src="https://a.com/old.png">old',
            "QuestionType": "MC", "Selector": "SAVR",
            "Choices": {"1": {"Display": "Yes"}},
        }},
    }, origin=ORIGIN)
    block = _parse_session_block({
        "sessionId": "sess1",
        "questions": [{
            "questionId": "QID1", "type": "mc",
            "display": '<img src="https://a.com/new.png">new',
        }],
        "done": False,
    }, survey)
    assert block.questions[0].image_urls == ["https://a.com/new.png"]


def test_session_block_falls_back_to_definition_images():
    survey = _parse_survey_definition("SV_x", {
        "SurveyName": "s",
        "Questions": {"QID1": {
            "QuestionText": '<img src="https://a.com/ad.png">Rate it',
            "QuestionType": "MC", "Selector": "SAVR",
            "Choices": {"1": {"Display": "Yes"}},
        }},
    }, origin=ORIGIN)
    block = _parse_session_block({
        "sessionId": "sess1",
        "questions": [{"questionId": "QID1", "type": "mc", "display": "Rate it"}],
        "done": False,
    }, survey)
    assert block.questions[0].image_urls == ["https://a.com/ad.png"]
    assert survey.has_image_stimuli


# ── answerability / collection / prompt ──────────────────────────────────────

def test_image_only_question_is_answerable():
    assert _is_answerable(_q("QID1", text="", images=["https://a.com/x.png"]))
    assert not _is_answerable(_q("QID1", text="", images=[]))


def test_collect_image_urls_context_first_deduped():
    ctx = [_q("QID0", "DB", images=["https://a.com/ad.png"])]
    qs = [_q("QID1", images=["https://a.com/ad.png", "https://a.com/logo.png"])]
    assert collect_image_urls(qs, ctx) == ["https://a.com/ad.png", "https://a.com/logo.png"]


def test_prompt_annotates_images():
    persona = Persona(name="p1", description="A test persona.")
    ctx = [_q("QID0", "DB", text="Here is the ad.", images=["https://a.com/ad.png"])]
    qs = [_q("QID1", text="How appealing is this ad?", images=["https://a.com/ad.png"])]
    urls = collect_image_urls(qs, ctx)
    prompt = _build_prompt(persona, qs, [], ctx, "Ad Study",
                           image_labels=image_labels_for(urls))
    assert "Here is the ad. [shows attached IMAGE 1]" in prompt
    assert "How appealing is this ad? [shows attached IMAGE 1]" in prompt


def test_prompt_unchanged_without_labels():
    persona = Persona(name="p1", description="A test persona.")
    qs = [_q("QID1", text="How appealing?")]
    assert _build_prompt(persona, qs, [], [], "s") == \
        _build_prompt(persona, qs, [], [], "s", image_labels={})


# ── multimodal content builders ──────────────────────────────────────────────

def test_openrouter_content_plain_string_without_images():
    assert openrouter_client._build_message_content("hi", [], {}) == "hi"


def test_openrouter_content_interleaves_labels_and_images():
    with patch.object(openrouter_client, "image_data_url",
                      return_value="data:image/png;base64,AAAA"):
        content = openrouter_client._build_message_content(
            "prompt", ["https://a.com/ad.png"], {"https://a.com/ad.png": "IMAGE 1"})
    assert content == [
        {"type": "text", "text": "prompt"},
        {"type": "text", "text": "\nIMAGE 1:"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
    ]


def test_openrouter_content_degrades_on_fetch_failure():
    with patch.object(openrouter_client, "image_data_url",
                      side_effect=RuntimeError("boom")):
        content = openrouter_client._build_message_content(
            "prompt", ["https://a.com/ad.png"], {"https://a.com/ad.png": "IMAGE 1"})
    assert content[0] == {"type": "text", "text": "prompt"}
    assert len(content) == 2
    assert "failed to load" in content[1]["text"]


def test_gemini_contents_plain_string_without_images():
    assert gemini_client._build_contents("hi", [], {}) == "hi"


def test_gemini_contents_attaches_bytes():
    with patch.object(gemini_client, "fetch_image",
                      return_value=(b"\x89PNG", "image/png")):
        parts = gemini_client._build_contents(
            "prompt", ["https://a.com/ad.png"], {"https://a.com/ad.png": "IMAGE 1"})
    assert len(parts) == 3  # prompt, label, image bytes
    assert parts[2].inline_data.data == b"\x89PNG"
    assert parts[2].inline_data.mime_type == "image/png"


def test_fetch_image_parses_data_url():
    data, mime = stimuli.fetch_image("data:image/png;base64,iVBORw0KGgo=")
    assert mime == "image/png"
    assert data.startswith(b"\x89PNG")
