"""Optional moving Cortes Gamer badge, independent of creator credits."""

import json
import subprocess
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from core import cancel
from core.binaries import ffmpeg, ffprobe
from core.paths import discard
from video.encoding import final_movflags, video_encoder_args

BADGE = Path(__file__).resolve().parent.parent / "assets" / "branding" / "cortes-gamer.png"
DWELL = 3.4
# Fractions of the available picture area after subtracting the badge size.
# Alternate sides and include interior points so one edge crop won't hide it.
ROUTE = ((0.14, 0.16), (0.78, 0.77), (0.60, 0.29), (0.33, 0.67))
# Older portrait exports can already have blurred bands baked in. Keep their
# route in the centre strip, where even a fitted 16:9 frame has real picture.
PORTRAIT_Y = (0.41, 0.58, 0.45, 0.54)
ACTIVE_Y = (0.20, 0.86, 0.37, 0.94)


class CortesGamerStyle(BaseModel):
    size: float = Field(default=22.5, ge=10, le=40)  # % of the shorter picture edge
    opacity: int = Field(default=90, ge=0, le=100)


def style_for(raw: dict | None) -> CortesGamerStyle:
    """Old renders and pending jobs have no saved style."""
    try:
        return CortesGamerStyle.model_validate(raw or {})
    except ValidationError:
        return CortesGamerStyle()


def overlay_graph(canvas: tuple[int, int], logo_index: int = 1, *, base: str = "0:v",
                  time_offset: float = 0.0, style: CortesGamerStyle | None = None,
                  band: tuple[float, float] | None = None) -> str:
    """Keep the badge visible and jump between points inside the picture."""
    w, h = canvas
    edge = min(w, h)
    style = style or CortesGamerStyle()
    size = max(2, round(style.size / 100 * edge))
    phase = f"mod(t+{time_offset:.6f},{len(ROUTE) * DWELL:g})"

    def axis(points: tuple, space: str) -> str:
        coord = f"{points[-1]:g}*({space})"
        for i in reversed(range(len(points) - 1)):
            coord = f"if(lt({phase},{DWELL * (i + 1):g}),{points[i]:g}*({space}),{coord})"
        return coord

    x = axis(tuple(p[0] for p in ROUTE), "W-w")
    if band:
        top, bottom = band
        y = f"{top:.5f}*H+{axis(ACTIVE_Y, f'{bottom - top:.5f}*H-h')}"
    else:
        y = axis(PORTRAIT_Y if h > w else tuple(p[1] for p in ROUTE), "H-h")
    return (
        f"[{logo_index}:v]scale={size}:-1:flags=lanczos,format=rgba,"
        f"colorchannelmixer=aa={style.opacity / 100:.2f}[cg];[{base}][cg]"
        f"overlay=x='{x}':y='{y}'"
    )


def _canvas(source: Path) -> tuple[int, int]:
    info = subprocess.run([
        ffprobe(), "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height:stream_side_data=rotation", "-of", "json", str(source),
    ], capture_output=True, check=True, timeout=30)
    return frame_size(json.loads(info.stdout)["streams"][0])


def frame_size(stream: dict) -> tuple[int, int]:
    width, height = stream["width"], stream["height"]
    rotation = next((side["rotation"] for side in stream.get("side_data_list", [])
                     if "rotation" in side), 0)
    return (height, width) if rotation % 180 else (width, height)


def picture_band(source: Path, canvas: tuple[int, int] | None = None) -> tuple[float, float] | None:
    """Find a broad, sharp picture on older portrait files with baked blur bars."""
    try:
        w, h = canvas or _canvas(source)
        return _portrait_band(source, source.stat().st_mtime_ns) if h > w else None
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError):
        return None


@lru_cache(maxsize=128)
def _portrait_band(source: Path, _modified: int) -> tuple[float, float] | None:
    # Persistent detail across the frame distinguishes the playing picture
    # from the large blurred areas and the already-burned captions/credits.
    import numpy as np

    width, height = 192, 336
    sample = subprocess.run([
        ffmpeg(), "-v", "error", "-nostdin", "-threads", "1", "-ss", "1", "-i", str(source),
        "-vf", f"fps=1,scale={width}:{height}:flags=area,format=gray",
        "-frames:v", "4", "-f", "rawvideo", "-threads", "1", "pipe:1",
    ], capture_output=True, check=True, timeout=10).stdout
    if len(sample) < 2 * width * height:
        return None
    frames = np.frombuffer(sample, dtype=np.uint8).reshape(-1, height, width).astype(np.int16)
    detail = np.abs(np.diff(frames, axis=2)).mean(axis=2)
    rows = np.convolve(np.median(detail, axis=0), np.ones(7) / 7, mode="same")
    threshold = max(1.65, float(np.percentile(rows[65:271], 65)) * 0.20)
    sharp = np.flatnonzero(rows > threshold)
    # Only widen the path when one broad picture spans the middle. A short
    # stretch with subtitles or bright UI is not enough to infer the layout.
    for group in np.split(sharp, np.flatnonzero(np.diff(sharp) > 12) + 1):
        if len(group) < height * 0.45:
            continue
        top, bottom = group[0] / height, (group[-1] + 1) / height
        if top < 0.25 and bottom > 0.75:
            return float(top + 0.02), float(bottom - 0.02)
    return None


def render(source: Path, target: Path, *, style: CortesGamerStyle | None = None,
           cancellable: bool = False) -> None:
    """Render to a different file; the input video and its audio stay intact."""
    canvas = _canvas(source)
    cmd = [
        ffmpeg(), "-y", "-v", "error", "-nostdin", "-filter_complex_threads", "1",
        "-i", str(source), "-i", str(BADGE),
        "-filter_complex", overlay_graph(canvas, style=style, band=picture_band(source, canvas)) + "[out]",
        "-map", "[out]", "-map", "0:a?", *video_encoder_args(),
        "-c:a", "copy", *final_movflags(), str(target),
    ]
    if cancellable:
        result = cancel.run([*cmd[:1], "-progress", "pipe:1", *cmd[1:]])
    else:
        result = subprocess.run(cmd, capture_output=True)
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()[-800:]
        raise RuntimeError(f"Não foi possível renderizar a marca Cortes Gamer. {detail}")


def apply(path: Path, *, style: CortesGamerStyle | None = None, cancellable: bool = False) -> None:
    """Replace a generated file only after the overlay has rendered."""
    from video.outro import _replace_with_retry

    stage = path.with_suffix(".cortes-gamer.mp4")
    try:
        render(path, stage, style=style, cancellable=cancellable)
        if not _replace_with_retry(stage, path, label="Cortes Gamer"):
            raise RuntimeError(f"Não foi possível gravar a marca em {path.name}.")
    finally:
        discard(stage)
