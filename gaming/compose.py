"""The FFmpeg render for a gaming layout. One encode, no frames through Python.

Every layout is the same few steps (gaming/layout.py makes the Plan): each
element is cut from the source, made the size of its region, and laid on the
1080x1920 canvas in order.

- cover:   scaled to fill its region (the plan already cut it to that shape).
- contain: shown whole, as big as fits, at the region's anchor (top, bottom
           or centre), on a blurred copy of itself that fills the rest of that
           region only: the bars are the picture's own colours, never black.
- shift:   a camera picture moved down within its region so the streamer's
           head clears the platform's top bar (gaming/framing.py), with the
           same blur above it.
- circle:  a round alpha mask, for the Circle facecam layout.

video/cropper.py is not modified; this is its own graph, with the same
encoder, audio and captions handling as the standard renderer.
"""

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from core.binaries import ffmpeg
from gaming.layout import OUT_H, OUT_W, Element, Plan
from video.encoding import audio_filter_args, final_movflags, video_encoder_args
from video.filters import subtitles_filter
from video.gpu_filters import (
    contain_fit_rect,
    cover_crop_rect,
    cuda_filters_available,
    gpu_blur_chain,
    gpu_ffmpeg_thread_args,
    hwaccel_cuda_decode_args,
    is_nvenc_args,
)


def _blur_fill(label: str, w: int, h: int) -> str:
    """The picture on [label] blown up to cover w x h, then downscaled hard,
    blurred and scaled back: a wash of its colours (the standard Letterbox
    layout's recipe, video/cropper.py _render_fit_blur)."""
    return (f"[{label}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"scale={max(2, w // 8)}:{max(2, h // 8)},gblur=sigma=12,scale={w}:{h}:flags=bilinear,setsar=1")


def _element(i: int, e: Element) -> tuple[str, str]:
    """(filter chain, output label) making element `i` the size of its region."""
    name = f"e{i}"
    sx, sy, sw, sh = e.src
    _dx, _dy, dw, dh = e.dest
    cut = f"[0:v]crop={sw}:{sh}:{sx}:{sy}"
    if e.fit == "blur":
        return f"{cut}[{name}s];{_blur_fill(name + 's', dw, dh)}[{name}]", name
    if e.fit == "contain" or e.shift:
        if e.fit == "contain":
            fg = f"scale={dw}:{dh}:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos"
            y = {"top": "0", "bottom": "H-h"}.get(e.anchor, "(H-h)/2")
            at = f"(W-w)/2:{y}"
        else:
            fg = f"scale={dw}:{dh}:flags=lanczos"
            at = f"0:{e.shift}"
        chain = (f"{cut},split=2[{name}b][{name}f];"
                 f"{_blur_fill(name + 'b', dw, dh)}[{name}bg];"
                 f"[{name}f]{fg},setsar=1[{name}fg];"
                 f"[{name}bg][{name}fg]overlay={at}[{name}]")
    else:
        chain = f"{cut},scale={dw}:{dh}:flags=lanczos,setsar=1[{name}]"
    if e.shape == "circle":
        chain += (f";[{name}]format=yuva444p,geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':"
                  f"a='if(lte(hypot(X-W/2,Y-H/2),W/2),255,0)'[{name}c]")
        return chain, f"{name}c"
    return chain, name


def filter_graph(p: Plan, vf_extra: str = "", ass_name: str | None = None) -> str:
    """The CPU -filter_complex for one plan; the output pad is [v]."""
    parts = [f"[0:v]crop=2:2:0:0,scale={OUT_W}:{OUT_H},setsar=1,"
             f"drawbox=x=0:y=0:w={OUT_W}:h={OUT_H}:color=black:t=fill[base]"]
    below = "base"
    for i, e in enumerate(p.elements):
        chain, label = _element(i, e)
        parts.append(chain)
        out = f"l{i}"
        parts.append(f"[{below}][{label}]overlay={e.dest[0]}:{e.dest[1]}[{out}]")
        below = out
    parts.append(f"[{below}]format=yuv420p[v]")
    graph = ";".join(parts)
    if vf_extra:
        graph += f";[v]{vf_extra}[v]"
    if ass_name:
        graph += f";[v]{subtitles_filter(ass_name)}[v]"
    return graph


def _gpu_element(i: int, e: Element, cuda_fmt: str) -> tuple[str, str, bool]:
    """(CUDA filter chain, output label, has_alpha) for element `i`."""
    name = f"e{i}"
    sx, sy, sw, sh = e.src
    _dx, _dy, dw, dh = e.dest
    cut = f"[0:v]crop={sw}:{sh}:{sx}:{sy}"
    if e.fit == "blur":
        return f"{cut},{gpu_blur_chain(dw, dh, cuda_fmt, (sw, sh))}[{name}]", name, False
    if e.shape == "circle":
        # Static 1-frame circular alpha mask looped + merged onto the small webcam box,
        # replacing per-frame 1800x geq(hypot(...)) CPU evaluations.
        if e.shift:
            cx, cy, cw, ch = cover_crop_rect(sw, sh, dw, dh)
            bw, bh = max(2, round((dw / 8.0) / 2.0) * 2), max(2, round((dh / 8.0) / 2.0) * 2)
            prep = (f"{cut},split=2[{name}b][{name}f];"
                    f"[{name}b]crop={cw}:{ch}:{cx}:{cy},scale={bw}:{bh}:flags=bilinear,"
                    f"gblur=sigma=12,scale={dw}:{dh}:flags=bilinear,setsar=1[{name}bg];"
                    f"[{name}f]scale={dw}:{dh}:flags=lanczos,setsar=1[{name}fg];"
                    f"[{name}bg][{name}fg]overlay=0:{e.shift},format=yuv420p[{name}s]")
        else:
            prep = f"{cut},scale={dw}:{dh}:flags=lanczos,setsar=1,format=yuv420p[{name}s]"
        mask = (f"color=black:s={dw}x{dh}:r=1:d=1,format=gray,"
                f"geq=lum='if(lte(hypot(X-W/2,Y-H/2),W/2),255,0)',"
                f"loop=-1:size=1:start=0,setpts=N/FRAME_RATE/TB[{name}m]")
        merge = f"[{name}s][{name}m]alphamerge,format=yuva420p,hwupload_cuda[{name}c]"
        return f"{prep};{mask};{merge}", f"{name}c", True
    if e.fit == "contain" or e.shift:
        if e.fit == "contain":
            ox, oy, fw, fh = contain_fit_rect(sw, sh, dw, dh, e.anchor)
            if fw == dw and fh == dh and not e.shift:
                chain = (f"{cut},hwupload_cuda,"
                         f"scale_cuda={dw}:{dh}:interp_algo=lanczos:format={cuda_fmt}:reset_sar=1[{name}]")
                return chain, name, False
            fg = f"hwupload_cuda,scale_cuda={fw}:{fh}:interp_algo=lanczos:format={cuda_fmt}:reset_sar=1"
            at = f"{ox}:{oy}"
        else:
            fg = f"hwupload_cuda,scale_cuda={dw}:{dh}:interp_algo=lanczos:format={cuda_fmt}:reset_sar=1"
            at = f"0:{e.shift}"
        chain = (f"{cut},split=2[{name}b][{name}f];"
                 f"[{name}b]{gpu_blur_chain(dw, dh, cuda_fmt, (sw, sh))}[{name}bg];"
                 f"[{name}f]{fg}[{name}fg];"
                 f"[{name}bg][{name}fg]overlay_cuda={at}[{name}]")
        return chain, name, False
    chain = (f"{cut},hwupload_cuda,"
             f"scale_cuda={dw}:{dh}:interp_algo=lanczos:format={cuda_fmt}:reset_sar=1[{name}]")
    return chain, name, False


def gpu_filter_graph(p: Plan, vf_extra: str = "", ass_name: str | None = None,
                     hw_encode: bool = True) -> str:
    """The CUDA -filter_complex for one plan; the output pad is [v]."""
    has_circle = any(e.shape == "circle" for e in p.elements)
    # overlay_cuda accepts alpha overlays (yuva420p) only onto yuv420p mains;
    # non-circle layouts stay in nv12 everywhere.
    cuda_fmt = "yuv420p" if has_circle else "nv12"
    parts: list[str] = []
    below = "base"
    if not p.elements:
        parts.append(
            f"[0:v]crop=2:2:0:0,drawbox=x=0:y=0:w=2:h=2:color=black:t=fill,"
            f"hwupload_cuda,scale_cuda={OUT_W}:{OUT_H}:interp_algo=nearest:"
            f"format={cuda_fmt}:reset_sar=1[base]"
        )
    else:
        for i, e in enumerate(p.elements):
            chain, label, has_alpha = _gpu_element(i, e, cuda_fmt)
            parts.append(chain)
            out = f"l{i}"
            if i == 0 and not has_alpha:
                if e.dest == (0, 0, OUT_W, OUT_H):
                    below = label
                else:
                    parts.append(f"[{label}]pad_cuda={OUT_W}:{OUT_H}:{e.dest[0]}:{e.dest[1]}:black[{out}]")
                    below = out
                continue
            if i == 0:
                parts.append(
                    f"[0:v]crop=2:2:0:0,drawbox=x=0:y=0:w=2:h=2:color=black:t=fill,"
                    f"hwupload_cuda,scale_cuda={OUT_W}:{OUT_H}:interp_algo=nearest:"
                    f"format={cuda_fmt}:reset_sar=1[base]"
                )
            shortest = ":shortest=1" if has_alpha else ""
            parts.append(f"[{below}][{label}]overlay_cuda={e.dest[0]}:{e.dest[1]}{shortest}[{out}]")
            below = out

    tail = f"[{below}]hwdownload,format={cuda_fmt}"
    if cuda_fmt != "yuv420p" and (vf_extra or not hw_encode):
        tail += ",format=yuv420p"
    parts.append(f"{tail}[v]")
    if vf_extra:
        parts.append(f"[v]{vf_extra}[v]")
    if ass_name:
        parts.append(f"[v]{subtitles_filter(ass_name)}[v]")
    return ";".join(parts)


def render(clip_path: Path, output_path: Path, p: Plan, ass_path: Path | None = None,
           vf_extra: str = "", normalize: bool = True) -> Path:
    if ass_path is not None and p.caption_y is not None:
        from video.captions import place_middle_captions

        # Keep the original ASS in case the pipeline falls back to another layout.
        with TemporaryDirectory(prefix="gaming-caption-", dir=ass_path.parent) as folder:
            placed = Path(folder) / "captions.ass"
            placed.write_text(place_middle_captions(ass_path.read_text(encoding="utf-8"),
                                                   OUT_W // 2, p.caption_y), encoding="utf-8")
            return _render(clip_path, output_path, p, placed, vf_extra, normalize)
    return _render(clip_path, output_path, p, ass_path, vf_extra, normalize)


def _ffmpeg_cmd(clip_path: Path, output_path: Path, graph: str, enc: list[str],
                normalize: bool, hw_decode: bool) -> list[str]:
    return [
        ffmpeg(), "-y",
        *(hwaccel_cuda_decode_args() if hw_decode else []),
        *(gpu_ffmpeg_thread_args() if hw_decode else []),
        "-i", str(clip_path.resolve()),
        "-filter_complex", graph,
        "-map", "[v]", "-map", "0:a:0?",
        *enc,
        "-c:a", "aac", "-b:a", "128k",
        *audio_filter_args(normalize),
        "-fps_mode", "cfr",
        # The clip itself: its first frame at 0 with or without the edit list.
        *final_movflags(),
        "-shortest", "-shortest_buf_duration", "1",
        str(output_path.resolve()),
    ]


def _render(clip_path: Path, output_path: Path, p: Plan, ass_path: Path | None,
            vf_extra: str, normalize: bool) -> Path:
    enc = video_encoder_args()
    ass_name = ass_path.name if ass_path is not None else None
    cwd = ass_path.parent if ass_path is not None else None
    if cuda_filters_available():
        gpu_cmd = _ffmpeg_cmd(
            clip_path, output_path,
            gpu_filter_graph(p, vf_extra, ass_name, hw_encode=is_nvenc_args(enc)),
            enc, normalize, hw_decode=True,
        )
        result = subprocess.run(gpu_cmd, capture_output=True, text=True, cwd=cwd)
        if result.returncode == 0:
            return output_path
        print(f"      (GPU filter render failed, falling back to CPU: {result.stderr[-200:].strip()})")

    cpu_cmd = _ffmpeg_cmd(
        clip_path, output_path,
        filter_graph(p, vf_extra, ass_name),
        enc, normalize, hw_decode=False,
    )
    # cwd is the captions' folder so the subtitles filter gets a bare name,
    # the same way the standard renderer avoids Windows path escaping.
    result = subprocess.run(cpu_cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"gaming render failed:\n{result.stderr[-2000:]}")
    return output_path
