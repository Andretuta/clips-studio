"""Build a horizontal YouTube video from rendered cuts in a chosen order."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from core import cancel, progress
from core.binaries import ffmpeg, ffprobe
from core.state import StateDB
from video.encoding import concat, concat_entry, video_encoder_args
from video_editor.cortes_gamer import BADGE, CortesGamerStyle, frame_size, overlay_graph, picture_band, style_for


def _streams(source: Path) -> dict:
    result = subprocess.run(
        [ffprobe(), "-v", "error", "-show_entries",
         "stream=codec_type,duration,width,height:stream_side_data=rotation:format=duration",
         "-of", "json", str(source)],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return json.loads(result.stdout)


def _video_duration(media: dict) -> float:
    track = next(stream for stream in media["streams"] if stream["codec_type"] == "video")
    return float(track.get("duration") or media["format"]["duration"])


def assemble(sources: list[Path], output: Path, video_id: str, *,
             watermark_indices: set[int] | None = None, style: CortesGamerStyle | None = None) -> float:
    """Preserve each cut's whole frame and make the pieces safe to join."""
    output.parent.mkdir(parents=True, exist_ok=True)
    resize = ("scale=1920:1080:force_original_aspect_ratio=decrease:"
              "force_divisible_by=2:flags=lanczos")
    pad = "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
    style = style or CortesGamerStyle()
    encoder = video_encoder_args()
    with TemporaryDirectory(prefix="compilation-", dir=output.parent) as folder:
        work = Path(folder)
        entries = []
        elapsed = 0.0
        for number, source in enumerate(sources, 1):
            cancel.check(video_id)
            progress.emit(stage="render", video_id=video_id, clip=number, total=len(sources))
            part = work / f"{number:04d}.mp4"
            media = _streams(source)
            tracks = {stream["codec_type"] for stream in media["streams"]}
            if "video" not in tracks:
                raise ValueError(f"O corte {number} não tem faixa de vídeo.")
            silence = [] if "audio" in tracks else [
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            ]
            if watermark_indices and number in watermark_indices and style.opacity:
                logo_index = 2 if silence else 1
                w, h = frame_size(next(track for track in media["streams"] if track["codec_type"] == "video"))
                scale = min(1920 / w, 1080 / h)
                fitted = (round(w * scale), round(h * scale))
                # Place the badge on the resized picture before adding any bars.
                graph = overlay_graph(fitted, logo_index, base="fit", time_offset=elapsed, style=style,
                                      band=picture_band(source, (w, h)))
                picture = [
                    "-i", str(BADGE), "-filter_complex_threads", "1", "-filter_complex",
                    f"[0:v]{resize}[fit];{graph},{pad}[video]", "-map", "[video]",
                ]
            else:
                picture = ["-map", "0:v:0", "-vf", f"{resize},{pad}"]
            result = cancel.run([
                ffmpeg(), "-y", "-v", "error", "-nostdin", "-progress", "pipe:1", "-i", str(source), *silence,
                *picture, "-map", "1:a:0" if silence else "0:a:0", *encoder, "-pix_fmt", "yuv420p", "-video_track_timescale", "90000",
                "-af", "aresample=async=1:first_pts=0,apad", "-c:a", "aac",
                "-b:a", "160k", "-ar", "48000", "-ac", "2",
                "-t", f"{_video_duration(media):.6f}", "-shortest", "-shortest_buf_duration", "1", str(part),
            ])
            if result.returncode != 0:
                detail = result.stderr.decode("utf-8", errors="replace").strip()[-400:]
                raise RuntimeError(f"Não foi possível preparar o corte {number}. {detail}")
            # The MP4's overall duration includes AAC padding. Advance the
            # concat clock by the video duration to avoid gaps between cuts.
            part_duration = _video_duration(_streams(part))
            elapsed += part_duration
            entries.append(f"{concat_entry(part.resolve().as_posix())}\nduration {part_duration:.6f}\n")

        cancel.check(video_id)
        listing = work / "concat.txt"
        listing.write_text("".join(entries), encoding="utf-8")
        joined = work / "compilado.mp4"
        result = concat(listing, joined)
        if result.returncode != 0 or not joined.is_file():
            raise RuntimeError(f"Não foi possível juntar os cortes.\n{result.stderr[-400:]}")
        duration = _video_duration(_streams(joined))
        cancel.check(video_id)
        os.replace(joined, output)
    return duration


def save(db: StateDB, data_dir: Path, video_id: str, title: str, sources: list[Path], *,
         watermark_indices: set[int] | None = None, cortes_gamer: bool = False,
         watermark_style: dict | None = None) -> None:
    target = data_dir / "clips" / "Compilados" / video_id / "compilado.mp4"
    existing = db.clips_for_video(video_id)
    if existing and target.is_file():
        db.set_video_status(video_id, "done")
        return
    style = style_for(watermark_style)
    duration = assemble(sources, target, video_id, watermark_indices=watermark_indices, style=style)
    db.upsert_video(video_id, title=title, channel_name="Compilados", duration=duration)
    if existing:
        db.set_clip(existing[0]["id"], path=str(target), end_s=round(duration, 2))
    else:
        db.add_clip(video_id, 0, duration, 0, title, path=str(target), title=title,
                    render_opts=json.dumps({"profile": "compilation", "cortes_gamer_watermark": cortes_gamer,
                                            "cortes_gamer_style": style.model_dump()}))
    db.set_video_status(video_id, "done")


def save_mesa_cut(db: StateDB, data_dir: Path, video_id: str, source: Path, metadata: dict):
    """Bring a finished Mesa export into the existing publishing editor."""
    target = data_dir / "clips" / "Mesa" / video_id / "corte.mp4"
    existing = db.clips_for_video(video_id)
    if existing and target.is_file():
        db.set_video_status(video_id, "done")
        return existing[0]
    duration = _video_duration(_streams(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="corte-", dir=target.parent) as folder:
        part = Path(folder) / "corte.mp4"
        shutil.copyfile(source, part)
        os.replace(part, target)
    title = str(metadata.get("titulo") or source.stem)
    channel = str(metadata.get("streamer") or "Mesa")
    db.upsert_video(video_id, title=title, channel_name=channel, duration=duration)
    if existing:
        db.set_clip(existing[0]["id"], path=str(target), end_s=round(duration, 2))
    else:
        hashtags = metadata.get("hashtags")
        tags = [str(tag) for tag in hashtags] if isinstance(hashtags, list) else []
        db.add_clip(video_id, 0, duration, 0, title, path=str(target), title=title,
                    description=str(metadata.get("descricao") or ""), hashtags=json.dumps(tags),
                    render_opts=json.dumps({"cortes_gamer_watermark": True,
                                            "cortes_gamer_style": style_for(metadata.get("cortes_gamer_style")).model_dump()})
                    if metadata.get("cortes_gamer_baked") else "")
    db.set_video_status(video_id, "done")
    return db.clips_for_video(video_id)[0]
