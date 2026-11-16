import subprocess
from pathlib import Path

import numpy as np

from analysis import visual_features


def test_visual_signals_survive_split_frames_and_ignore_partial_last_frame(monkeypatch):
    frame_bytes = visual_features.FRAME_W * visual_features.FRAME_H
    raw = b"".join(bytes([value]) * frame_bytes for value in (0, 0, 255, 255, 255, 0, 0))
    raw += b"\xff" * 19

    def streamed(cmd, *, consume_stdout):
        for start in range(0, len(raw), frame_bytes + 11):
            consume_stdout(raw[start : start + frame_bytes + 11])
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(visual_features.cancel, "run", streamed)
    signals = visual_features.extract_visual_features(Path("test.mp4"))

    expected = {"motion": [0, 127.5, 127.5], "scene_cut": [0, 1, 1], "flash": [0, 255, 255]}
    for key, values in expected.items():
        np.testing.assert_array_equal(signals[key], np.array(values, dtype=np.float32))
