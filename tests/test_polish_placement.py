"""video.polish runs at the source's resolution, before any upscale.

hqdn3d + cas after the 9:16 crop was scaled to 1080x1920 cost ~14 s on a
28 s 1080p60 clip (+50% render time); on the source-size crop, before the
Lanczos upscale, ~2 s. So the tracked path polishes the intermediate it cuts
(detection and every layout read that), and a single-encode path puts the
polish ahead of its fit/scale. The colour look stays where it was.
"""

from pathlib import Path

import pytest

from core import modes

POLISH = {"video": {"polish": {"denoise": 1.5, "sharpen": 0.5}}}
CHAIN = "hqdn3d=1.50:1.50:3.00:3.00,cas=strength=0.50"


@pytest.fixture
def pipeline(monkeypatch):
    pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    from core import pipeline as pipeline_mod

    return pipeline_mod


def _config(tmp_path, **clips):
    return {
        **POLISH,
        "clips": {"captions": False, "outro": False, "vertical": True, **clips},
        "paths": {"data_dir": str(tmp_path)},
        "tracking": {"detector": "yolov8n-pose.pt", "sample_fps": 8},
    }


def _render(pipeline, monkeypatch, tmp_path, size, config, opts=None):
    import video.cropper as cropper
    import video.tracker as tracker
    from core.models import ClipCandidate

    cuts, renders = [], []

    def fake_cut(source, candidate, output, ass_path=None, vf_extra="", normalize=True, final=False):
        cuts.append((Path(output).name, vf_extra))
        Path(output).write_bytes(b"clip")

    def fake_render(intermediate, tracking, output, ass_path=None, vf_extra="", normalize=True):
        renders.append(vf_extra)
        Path(output).write_bytes(b"clip")

    monkeypatch.setattr(pipeline, "cut_clip", fake_cut)
    monkeypatch.setattr(pipeline, "_share_the_cpu", lambda *_a: None)
    monkeypatch.setattr(tracker, "compute_tracking", lambda *_a, **_k: {"mode": "track", "path": [(0.0, 0.5)]})
    monkeypatch.setattr(cropper, "render_vertical", fake_render)
    monkeypatch.setattr(modes, "probe_size", lambda _path: size)
    pipeline._render_files(tmp_path / "source.mp4", ClipCandidate(start=10.0, end=40.0, score=80), [],
                           tmp_path / "clips", config, opts)
    return cuts, renders


def test_tracked_path_polishes_the_intermediate_not_the_upscaled_render(pipeline, monkeypatch, tmp_path):
    cuts, renders = _render(pipeline, monkeypatch, tmp_path, (1920, 1080), _config(tmp_path))
    assert [vf for name, vf in cuts if name.endswith(".source.mp4")] == [CHAIN]
    assert renders == [""]


def test_the_colour_look_stays_on_the_render(pipeline, monkeypatch, tmp_path):
    cuts, renders = _render(pipeline, monkeypatch, tmp_path, (1920, 1080), _config(tmp_path, filter="bw"))
    assert [vf for name, vf in cuts if name.endswith(".source.mp4")] == [CHAIN]
    assert renders == ["hue=s=0,eq=contrast=1.15"]


def test_single_encode_path_polishes_before_its_upscale(pipeline, monkeypatch, tmp_path):
    cuts, _ = _render(pipeline, monkeypatch, tmp_path, (720, 1280), _config(tmp_path, vertical_live=True))
    assert len(cuts) == 1
    assert cuts[0][1].startswith(CHAIN + ",scale=1080:1920")


def test_no_polish_config_is_factory(pipeline, monkeypatch, tmp_path):
    config = {k: v for k, v in _config(tmp_path).items() if k != "video"}
    cuts, renders = _render(pipeline, monkeypatch, tmp_path, (1920, 1080), config)
    assert [vf for name, vf in cuts if name.endswith(".source.mp4")] == [""]
    assert renders == [""]
