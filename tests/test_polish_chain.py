"""video.polish: a light denoise and a sharpen after the crop is scaled up.

A 9:16 crop of a 1080p stream is enlarged ~1.8x; Lanczos keeps it clean but
soft, and Twitch's compression shows as blocks. hqdn3d (denoise) and cas
(contrast-adaptive sharpen) are FFmpeg built-ins. Absent config = factory.
"""

import subprocess
from pathlib import Path

import pytest

from core.binaries import ffmpeg
from video.filters import polish_chain


def test_absent_config_is_factory():
    assert polish_chain({}) == ""
    assert polish_chain({"video": {}}) == ""
    assert polish_chain({"video": {"polish": {"denoise": 0, "sharpen": 0}}}) == ""


def test_both_on():
    assert polish_chain({"video": {"polish": {"denoise": 1.5, "sharpen": 0.5}}}) == \
        "hqdn3d=1.50:1.50:3.00:3.00,cas=strength=0.50"


def test_clamped_and_bad_values():
    assert polish_chain({"video": {"polish": {"denoise": 99, "sharpen": -1}}}) == "hqdn3d=6.00:6.00:12.00:12.00"
    assert polish_chain({"video": {"polish": {"denoise": "x", "sharpen": 0.3}}}) == "cas=strength=0.30"
    assert polish_chain({"video": {"polish": None}}) == ""


@pytest.mark.parametrize("polish", [True, 1.5, "on", [1, 2]])
def test_a_polish_that_is_not_a_block_is_off(polish):
    # Hand-editing the block is how a user turns it on; a scalar must not
    # crash every render.
    assert polish_chain({"video": {"polish": polish}}) == ""


def test_bool_and_non_finite_amounts_are_off():
    assert polish_chain({"video": {"polish": {"denoise": float("nan"), "sharpen": True}}}) == ""
    assert polish_chain({"video": {"polish": {"denoise": float("inf"), "sharpen": float("-inf")}}}) == ""


def test_ffmpeg_accepts_the_chain():
    binary = ffmpeg()
    if not Path(binary).is_file():
        pytest.skip("FFmpeg is not installed here")
    chain = polish_chain({"video": {"polish": {"denoise": 1.5, "sharpen": 0.5}}})
    result = subprocess.run(
        [binary, "-v", "error", "-f", "lavfi", "-i", "color=gray:s=320x240:d=0.5",
         "-vf", chain, "-f", "null", "-"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-500:]
