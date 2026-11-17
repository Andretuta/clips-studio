"""GPU FFmpeg filter pipeline (video/gpu_filters.py, gaming/compose.py, video/cropper.py).

Covers cached one-time CUDA probing, integer layout geometry for scale_cuda /
overlay_cuda, CPU fallback when CUDA is unavailable or fails at runtime, graph
coverage across all 11 gaming presets, and real-render verification when FFmpeg
and cv2 are installed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gaming import compose, layout
from video import encoding, gpu_filters
from video.filters import subtitles_filter

W, H = 1920, 1080
CAM = (0.0, 0.0, 0.25, 1 / 3)
CAM2 = (0.75, 0.0, 0.25, 1 / 3)
UI = (0.3, 0.0, 0.4, 0.08)


class _Ran:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture(autouse=True)
def _restore_cuda_cache():
    gpu_filters.reset_cuda_cache()
    yield
    gpu_filters.reset_cuda_cache()


# ---- one-time probe + cache ---------------------------------------------------------------


def test_cuda_probe_is_cached_after_first_call(monkeypatch):
    calls = 0

    def fake_probe():
        nonlocal calls
        calls += 1
        return True

    monkeypatch.setattr(gpu_filters, "_probe_cuda_filters", fake_probe)
    assert gpu_filters.cuda_filters_available() is True
    assert gpu_filters.cuda_filters_available() is True
    assert calls == 1

    gpu_filters.reset_cuda_cache()
    assert gpu_filters.cuda_filters_available() is True
    assert calls == 2


def test_cuda_probe_handles_missing_ffmpeg_or_nonzero_exit(monkeypatch):
    def boom(*_a, **_k):
        raise FileNotFoundError("no ffmpeg")

    monkeypatch.setattr(subprocess, "Popen", boom)
    assert gpu_filters.cuda_filters_available() is False

    gpu_filters.reset_cuda_cache()

    class _FailProc:
        def wait(self, timeout=None):
            return 1

    monkeypatch.setattr(subprocess, "Popen", lambda *_a, **_k: _FailProc())
    assert gpu_filters.cuda_filters_available() is False


# ---- geometry & graph construction --------------------------------------------------------


def test_contain_fit_rect_produces_even_sizes_and_anchored_positions():
    # 16:9 inside 1080x1920 -> 1080x608 centered at y=656
    assert gpu_filters.contain_fit_rect(1920, 1080, 1080, 1920, "center") == (0, 656, 1080, 608)
    assert gpu_filters.contain_fit_rect(1920, 1080, 1080, 1920, "top") == (0, 0, 1080, 608)
    assert gpu_filters.contain_fit_rect(1920, 1080, 1080, 1920, "bottom") == (0, 1312, 1080, 608)

    # Taller source inside wider box -> width-padded horizontally
    ox, oy, fw, fh = gpu_filters.contain_fit_rect(600, 800, 1080, 740, "center")
    assert fh == 740 and fw == 556 and ox == (1080 - 556) // 2 and oy == 0


def test_cover_crop_rect_and_blur_chain_stay_even_and_reset_sar():
    cx, cy, cw, ch = gpu_filters.cover_crop_rect(1920, 1080, 1080, 1920)
    assert (cw, ch) == (608, 1080) and cx == 656 and cy == 0
    assert all(v % 2 == 0 for v in (cx, cy, cw, ch))

    chain = gpu_filters.gpu_blur_chain(1080, 1920, "nv12", (1920, 1080))
    assert "crop=608:1080:656:0" in chain
    assert "gblur=sigma=12" in chain
    assert "hwupload_cuda,scale_cuda=1080:1920:interp_algo=bilinear:format=nv12:reset_sar=1" in chain


@pytest.mark.parametrize("preset", sorted(layout.PRESETS))
def test_gpu_filter_graph_covers_every_gaming_preset(preset):
    p = layout.plan(W, H, {
        "preset": preset, "cam": list(CAM), "cam2": list(CAM2), "ui_box": list(UI),
    })
    graph = compose.gpu_filter_graph(p, vf_extra="eq=saturation=1.1", ass_name="c.ass")
    assert "hwupload_cuda" in graph
    assert "scale_cuda=" in graph
    assert "reset_sar=1" in graph
    # Always downloads to avoid NVENC 1088 CUDA surface pitch bug, and keeps subtitles on CPU.
    assert "hwdownload,format=" in graph
    assert graph.endswith(";[v]eq=saturation=1.1[v];[v]" + subtitles_filter("c.ass") + "[v]")
    # overlay_cuda must never rely on FFmpeg 8 W/H/w/h expression evaluation.
    assert "(W-w)" not in graph and "H-h" not in graph


def test_gpu_filter_graph_adds_yuv420p_for_cpu_encoder():
    p = layout.plan(W, H, {"preset": "fullscreen", "game_box": [0, 0, 1, 1]})
    nvenc_graph = compose.gpu_filter_graph(p, hw_encode=True)
    x264_graph = compose.gpu_filter_graph(p, hw_encode=False)
    assert "hwdownload,format=nv12[v]" in nvenc_graph
    assert "hwdownload,format=nv12,format=yuv420p[v]" in x264_graph


# ---- compose fallback tests ---------------------------------------------------------------


def test_compose_uses_cpu_graph_when_cuda_probe_is_false(monkeypatch, tmp_path):
    cmds = []
    monkeypatch.setattr(compose, "cuda_filters_available", lambda: False)
    monkeypatch.setattr(compose, "video_encoder_args", lambda: encoding.CPU_ARGS)
    monkeypatch.setattr(subprocess, "run", lambda cmd, **_k: cmds.append(cmd) or _Ran(0))

    p = layout.plan(W, H, {"preset": "blurred", "game_box": [0, 0, 1, 1]})
    compose.render(tmp_path / "in.mp4", tmp_path / "out.mp4", p)
    [cmd] = cmds
    assert "-hwaccel" not in cmd
    assert "overlay_cuda" not in " ".join(cmd)
    assert "-shortest_buf_duration" in cmd and "1" in cmd


def test_compose_falls_back_to_cpu_when_gpu_render_fails_at_runtime(monkeypatch, tmp_path):
    cmds = []

    def fake_run(cmd, **_k):
        cmds.append(cmd)
        return _Ran(1, stderr="CUDA init failed") if len(cmds) == 1 else _Ran(0)

    monkeypatch.setattr(compose, "cuda_filters_available", lambda: True)
    monkeypatch.setattr(compose, "video_encoder_args", lambda: ["-c:v", "h264_nvenc"])
    monkeypatch.setattr(subprocess, "run", fake_run)

    p = layout.plan(W, H, {"preset": "split", "cam": list(CAM)})
    out = tmp_path / "out.mp4"
    assert compose.render(tmp_path / "in.mp4", out, p) == out
    assert len(cmds) == 2
    assert "-hwaccel" in cmds[0] and "cuda" in cmds[0]
    assert "-filter_complex_threads" in cmds[0]
    assert "-hwaccel" not in cmds[1]
    assert "-filter_complex_threads" not in cmds[1]
    assert "overlay_cuda" not in " ".join(cmds[1])


# ---- cropper fallback tests ---------------------------------------------------------------


@pytest.fixture
def synthetic_clip(tmp_path):
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    clip = tmp_path / "clip.mp4"
    out = cv2.VideoWriter(str(clip), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (640, 360))
    for _ in range(4):
        out.write(np.full((360, 640, 3), 128, np.uint8))
    out.release()
    return clip


@pytest.mark.parametrize("tracking", [
    {"mode": "fit_blur", "region": None},
    {"mode": "split", "webcam_box": (0.0, 0.0, 0.3, 0.3)},
    {"mode": "track", "path": [(0.0, 0.5)], "face_y": 0.1},
])
def test_cropper_uses_cpu_when_cuda_probe_is_false(monkeypatch, synthetic_clip, tmp_path, tracking):
    from video import cropper

    cmds = []
    monkeypatch.setattr(cropper, "cuda_filters_available", lambda: False)
    monkeypatch.setattr(cropper, "video_encoder_args", lambda: encoding.CPU_ARGS)
    monkeypatch.setattr(cropper, "_run_ffmpeg", lambda cmd, _ass: cmds.append(cmd))
    monkeypatch.setattr(cropper, "_run_ffmpeg_piped", lambda cmd, _ass, _p: cmds.append(cmd))

    cropper.render_vertical(synthetic_clip, tracking, tmp_path / "out.mp4")
    [cmd] = cmds
    assert "-hwaccel" not in cmd
    assert "scale_cuda" not in " ".join(cmd)
    assert "overlay_cuda" not in " ".join(cmd)


@pytest.mark.parametrize("tracking", [
    {"mode": "fit_blur", "region": None},
    {"mode": "split", "webcam_box": (0.0, 0.0, 0.3, 0.3)},
    {"mode": "track", "path": [(0.0, 0.5)], "face_y": 0.1},
])
def test_cropper_falls_back_to_cpu_on_runtime_gpu_error(monkeypatch, synthetic_clip, tmp_path, tracking):
    from video import cropper

    cmds = []

    def fail_first_run(cmd, _ass):
        cmds.append(cmd)
        if len(cmds) == 1:
            raise RuntimeError("GPU filter failure")

    def fail_first_piped(cmd, _ass, produce):
        cmds.append(cmd)
        produced = []
        produce(produced.append)
        if len(cmds) == 1:
            raise RuntimeError("GPU piped failure")
        assert len(produced) >= 1  # fallback rewound VideoCapture and re-emitted frames

    monkeypatch.setattr(cropper, "cuda_filters_available", lambda: True)
    monkeypatch.setattr(cropper, "video_encoder_args", lambda: ["-c:v", "h264_nvenc"])
    monkeypatch.setattr(cropper, "_run_ffmpeg", fail_first_run)
    monkeypatch.setattr(cropper, "_run_ffmpeg_piped", fail_first_piped)

    out = tmp_path / "out.mp4"
    assert cropper.render_vertical(synthetic_clip, tracking, out) == out
    assert len(cmds) == 2
    assert "scale_cuda" in " ".join(cmds[0])
    assert "scale_cuda" not in " ".join(cmds[1])
    assert "overlay_cuda" not in " ".join(cmds[1])


# ---- real GPU encode smoke tests ----------------------------------------------------------


def _ffmpeg_and_ffprobe_or_skip():
    from core.binaries import ffmpeg, ffprobe

    bin_ff = ffmpeg()
    try:
        subprocess.run([bin_ff, "-version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("FFmpeg unavailable")
    return bin_ff, ffprobe()


def test_real_gpu_render_keeps_dimensions_duration_and_captions(tmp_path):
    pytest.importorskip("cv2")
    bin_ff, bin_probe = _ffmpeg_and_ffprobe_or_skip()
    if not gpu_filters.cuda_filters_available():
        pytest.skip("CUDA FFmpeg filters unavailable on this host")

    from core.models import ClipCandidate
    from video.captions import build_captions

    src = tmp_path / "src.mp4"
    subprocess.run([
        bin_ff, "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=blue:s=1920x1080:r=30:d=2,drawbox=x=0:y=0:w=480:h=360:color=red:t=fill",
        "-f", "lavfi", "-i", "sine=frequency=440:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src),
    ], check=True)

    ass = build_captions(
        [], ClipCandidate(start=0, end=2, score=0), tmp_path / "cap.ass",
        style={"font": "Bebas Neue", "size": 72},
        lines=[{"start": 0.2, "end": 1.8, "text": "Teste na GPU"}],
    )

    for preset in ("blurred", "split"):
        plan = layout.plan(W, H, {"preset": preset, "cam": list(CAM)})
        out = compose.render(src, tmp_path / f"{preset}.mp4", plan, ass)
        info = json.loads(subprocess.check_output([
            bin_probe, "-v", "error",
            "-show_entries", "stream=codec_type,width,height,sample_aspect_ratio:format=duration",
            "-of", "json", str(out),
        ], text=True))
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (v["width"], v["height"]) == (1080, 1920)
        assert v["sample_aspect_ratio"] == "1:1"
        assert any(s["codec_type"] == "audio" for s in info["streams"])
        assert abs(float(info["format"]["duration"]) - 2.0) < 0.15
