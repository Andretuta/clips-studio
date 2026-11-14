"""clips.gaming_no_cam: the layout a gaming clip gets when no webcam is found.

Factory: Blurred (the whole game, small, on a blur). A channel of GTA
gameplay wants Fullscreen (the game zoomed to fill the Short). Only the
layouts that show the game alone qualify; anything else is Blurred.
"""

from gaming.layout import no_cam_preset, plan, resolve


def test_default_is_factory_blurred():
    assert no_cam_preset({}) == "blurred"
    assert resolve({"preset": "half", "cam": None})["preset"] == "blurred"


def test_fullscreen_when_configured():
    assert no_cam_preset({"clips": {"gaming_no_cam": "fullscreen"}}) == "fullscreen"
    assert resolve({"preset": "half", "cam": None, "no_cam": "fullscreen"})["preset"] == "fullscreen"
    assert plan(1920, 1080, {"preset": "split", "cam": None, "no_cam": "fullscreen"}).preset == "fullscreen"


def test_invalid_value_is_blurred():
    assert no_cam_preset({"clips": {"gaming_no_cam": "half"}}) == "blurred"
    assert no_cam_preset({"clips": {"gaming_no_cam": "xyz"}}) == "blurred"
    assert no_cam_preset({"clips": None}) == "blurred"
    assert resolve({"preset": "half", "cam": None, "no_cam": "half"})["preset"] == "blurred"


def test_a_found_webcam_keeps_its_layout():
    assert resolve({"preset": "half", "cam": [0.7, 0.7, 0.3, 0.3], "no_cam": "fullscreen"})["preset"] == "half"
