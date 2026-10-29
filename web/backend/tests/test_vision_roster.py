"""Vision-roster routing: image surveys swap Model B/C to vision-capable
models; text surveys keep the Twin-2K-validated roster; smoke runs are
unaffected (gemini flash-lite is multimodal either way)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ensemble import ROSTER, SMOKE_SPEC, VISION_ROSTER, roster_for


def test_text_surveys_keep_validated_roster():
    assert roster_for(is_smoke=False, has_images=False) == ROSTER
    # Default keeps old call sites / behavior text-only.
    assert roster_for(is_smoke=False) == ROSTER


def test_image_surveys_use_vision_roster():
    assert roster_for(is_smoke=False, has_images=True) == VISION_ROSTER


def test_smoke_single_model_regardless_of_images():
    assert roster_for(is_smoke=True, has_images=True) == [SMOKE_SPEC]
    assert roster_for(is_smoke=True, has_images=False) == [SMOKE_SPEC]


def test_rosters_share_public_identity():
    """Anonymity contract: users see the same Model A/B/C labels and slugs
    whichever roster served the run."""
    assert [(m.label, m.slug) for m in ROSTER] == \
        [(m.label, m.slug) for m in VISION_ROSTER]


def test_vision_models_differ_only_on_openrouter_slots():
    assert VISION_ROSTER[0].model == ROSTER[0].model  # Gemini is already multimodal
    assert all(m.provider == "openrouter" for m in VISION_ROSTER[1:])
