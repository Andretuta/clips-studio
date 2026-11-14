"""A tuned NVENC set (AQ, lookahead, B-frames as references, lower cq) tried
before the plain one. A card or driver that refuses one of its flags fails
the probe and gets the plain NVENC set, not the CPU."""

from unittest.mock import patch

from video.encoding import _CANDIDATES, _select

TUNED = ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", "21", "-b:v", "0",
         "-spatial-aq", "1", "-temporal-aq", "1", "-rc-lookahead", "32", "-bf", "3", "-b_ref_mode", "middle"]


def test_tuned_set_is_first_and_as_specified():
    assert next(iter(_CANDIDATES)) == "nvenc_hq"
    assert _CANDIDATES["nvenc_hq"] == TUNED


@patch("video.encoding._probe")
def test_auto_prefers_tuned_nvenc(mock_probe):
    mock_probe.return_value = True
    assert _select("auto") == ("nvenc_hq", TUNED)


@patch("video.encoding._probe")
def test_tuned_refused_falls_back_to_plain_nvenc(mock_probe):
    mock_probe.side_effect = lambda args: args == _CANDIDATES["nvenc"]
    assert _select("auto") == ("nvenc", _CANDIDATES["nvenc"])


@patch("video.encoding._probe")
def test_forced_nvenc_is_factory(mock_probe):
    mock_probe.return_value = True
    assert _select("nvenc") == ("nvenc", _CANDIDATES["nvenc"])
    mock_probe.assert_called_once_with(_CANDIDATES["nvenc"])
