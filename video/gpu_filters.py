"""CUDA FFmpeg filter helpers shared exclusively by gaming/compose.py and video/cropper.py.

Moves scale, pad, blur-wash construction and compositing onto the GPU when
FFmpeg's CUDA filter pipeline (`hwupload_cuda`, `scale_cuda`, `pad_cuda`,
`overlay_cuda`, `hwdownload`) actually works on the host machine.

Detection runs once per process with a thread-safe cache and executes a tiny
end-to-end synthetic filtergraph against the real FFmpeg binary, rather than
trusting `-filters` text output (machines without an NVIDIA driver or with
mismatching CUDA runtime list the filters but fail at init). Callers also keep
the CPU graph as a runtime fallback in case a specific clip (odd codec,
10-bit input, driver session limit) fails on the GPU path.
"""

from __future__ import annotations

import subprocess
import threading

from core.binaries import ffmpeg

_PROBE_LOCK = threading.Lock()
_CUDA_FILTERS_OK: bool | None = None


def reset_cuda_cache() -> None:
    """Clear the cached CUDA filter probe (for tests)."""
    global _CUDA_FILTERS_OK
    with _PROBE_LOCK:
        _CUDA_FILTERS_OK = None


def cuda_filters_available() -> bool:
    """Whether FFmpeg CUDA video filters work on this machine (cached once)."""
    global _CUDA_FILTERS_OK
    if _CUDA_FILTERS_OK is not None:
        return _CUDA_FILTERS_OK
    with _PROBE_LOCK:
        if _CUDA_FILTERS_OK is not None:
            return _CUDA_FILTERS_OK
        _CUDA_FILTERS_OK = _probe_cuda_filters()
        return _CUDA_FILTERS_OK


def _probe_cuda_filters() -> bool:
    """Run a 0.1s synthetic graph exercising every CUDA filter we depend on:
    hwupload_cuda, scale_cuda (nv12 & yuv420p), pad_cuda, overlay_cuda
    (nv12+nv12 and yuv420p+yuva420p), and hwdownload."""
    cmd = [
        ffmpeg(), "-v", "error",
        "-f", "lavfi", "-i", "color=black:s=64x64:d=0.1",
        "-init_hw_device", "cuda=cu", "-filter_hw_device", "cu",
        "-filter_complex",
        "[0:v]split=3[a][b][c];"
        "[a]hwupload_cuda,scale_cuda=64:64:format=nv12:reset_sar=1[m1];"
        "[b]hwupload_cuda,scale_cuda=32:32:format=nv12:reset_sar=1,pad_cuda=64:64:0:0:black[o1];"
        "[m1][o1]overlay_cuda=0:0,hwdownload,format=nv12[v1];"
        "[c]hwupload_cuda,scale_cuda=64:64:format=yuv420p:reset_sar=1[m2];"
        "color=c=black@0.0:s=32x32:r=1:d=0.1,format=yuva420p,hwupload_cuda[o2];"
        "[m2][o2]overlay_cuda=0:0:shortest=1,hwdownload,format=yuv420p[v2]",
        "-map", "[v1]", "-map", "[v2]", "-f", "null", "-",
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc.wait(timeout=15) == 0
    except Exception:
        return False


def hwaccel_cuda_decode_args() -> list[str]:
    """Input flags enabling NVDEC decoding when feeding a GPU filtergraph."""
    return ["-hwaccel", "cuda"]


def hw_device_cuda_args() -> list[str]:
    """Explicit CUDA device creation for rawvideo/piped inputs without -hwaccel."""
    return ["-init_hw_device", "cuda=cu", "-filter_hw_device", "cu"]


def gpu_ffmpeg_thread_args() -> list[str]:
    """Cap CPU decoder/filter worker threads on GPU-filtered runs (~140 MiB less RAM
    per FFmpeg process with zero wall-time penalty when NVDEC/CUDA handle video)."""
    return ["-threads", "1", "-filter_threads", "1", "-filter_complex_threads", "1"]


def is_nvenc_args(enc_args: list[str]) -> bool:
    """Whether the chosen encoder args use NVIDIA NVENC (can accept CUDA frames)."""
    return "h264_nvenc" in enc_args


def even_blur_size(w: int, h: int) -> tuple[int, int]:
    """Even ~1/8 scale dimensions for the blur wash (hwupload/CUDA require even)."""
    bw = max(2, round((w / 8.0) / 2.0) * 2)
    bh = max(2, round((h / 8.0) / 2.0) * 2)
    return bw, bh


def cover_crop_rect(src_w: int, src_h: int, dst_w: int, dst_h: int) -> tuple[int, int, int, int]:
    """Centered even (x, y, cw, ch) inside src_w x src_h matching dst_w:dst_h aspect."""
    if src_w <= 2 or src_h <= 2:
        return 0, 0, max(2, src_w), max(2, src_h)
    target = dst_w / dst_h
    if src_w / src_h > target:
        ch = src_h - (src_h % 2)
        cw = max(2, min(src_w, round(ch * target / 2.0) * 2))
    else:
        cw = src_w - (src_w % 2)
        ch = max(2, min(src_h, round(cw / target / 2.0) * 2))
    cx = max(0, (src_w - cw) // 2)
    cy = max(0, (src_h - ch) // 2)
    return cx, cy, cw, ch


def contain_fit_rect(
    src_w: int,
    src_h: int,
    dst_w: int,
    dst_h: int,
    anchor: str = "center",
) -> tuple[int, int, int, int]:
    """Compute (ox, oy, fw, fh) matching scale=dst_w:dst_h:decrease:force_divisible_by=2
    + anchored overlay without relying on overlay_cuda W/H/w/h expression eval
    (FFmpeg 8.0.1 overlay_cuda mis-evaluates W/H/w/h when CUDA surfaces pad pitch)."""
    dw = max(2, dst_w - (dst_w % 2))
    dh = max(2, dst_h - (dst_h % 2))
    if src_w <= 0 or src_h <= 0:
        return 0, 0, dw, dh
    if src_w * dh >= dw * src_h:
        fw = dw
        fh = max(2, min(dh, int((dw * src_h / src_w + 1.0) // 2) * 2))
    else:
        fh = dh
        fw = max(2, min(dw, int((dh * src_w / src_h + 1.0) // 2) * 2))
    ox = (dst_w - fw) // 2
    if anchor == "top":
        oy = 0
    elif anchor == "bottom":
        oy = dst_h - fh
    else:
        oy = (dst_h - fh) // 2
    return ox, oy, fw, fh


def cover_crop_expr(dst_w: int, dst_h: int) -> str:
    """Zero-copy CPU crop expression matching dst_w:dst_h aspect (even output)."""
    return (
        f"crop='max(2\\,round(min(iw\\,ih*{dst_w}/{dst_h})/2)*2)'"
        f":'max(2\\,round(min(ih\\,iw*{dst_h}/{dst_w})/2)*2)'"
    )


def gpu_blur_chain(
    dst_w: int,
    dst_h: int,
    pix_fmt: str = "nv12",
    src_size: tuple[int, int] | None = None,
) -> str:
    """Build the blur-wash chain matching CPU `_blur_fill`:
    aspect-cover crop -> shrink ~1/8 on CPU -> gblur=sigma=12 -> hwupload_cuda
    -> scale_cuda bilinear back up to dst_w x dst_h in `pix_fmt`.

    Running gblur at tiny 1/8 resolution (~49 KB/frame at 136x240) keeps CPU
    cost negligible while matching CPU gblur=sigma=12 at ~0.994+ SSIM and
    needing only one CUDA surface upload.
    """
    if src_size is not None:
        cx, cy, cw, ch = cover_crop_rect(src_size[0], src_size[1], dst_w, dst_h)
        crop_part = f"crop={cw}:{ch}:{cx}:{cy}"
    else:
        crop_part = cover_crop_expr(dst_w, dst_h)
    bw, bh = even_blur_size(dst_w, dst_h)
    return (
        f"{crop_part},"
        f"scale={bw}:{bh}:flags=bilinear,format=yuv420p,gblur=sigma=12,"
        f"hwupload_cuda,"
        f"scale_cuda={dst_w}:{dst_h}:interp_algo=bilinear:format={pix_fmt}:reset_sar=1"
    )
