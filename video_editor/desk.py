"""Transformações da cópia da Mesa, conservando o original em cada aprovação."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def write_side(path, side):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(side, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def duration(path):
    from core.binaries import ffprobe
    result = subprocess.run([ffprobe(), "-v", "error", "-show_entries", "format=duration",
                             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                            capture_output=True, text=True, timeout=20, check=True)
    value = float(result.stdout.strip())
    import math
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Duração inválida")
    return value


def edit(path, side, decision, seconds):
    source = path.with_suffix(".mp4")
    if decision.trim_start or decision.trim_end:
        from core.binaries import ffmpeg
        with TemporaryDirectory(prefix="editorial-", dir=source.parent) as folder:
            staged = Path(folder) / source.name
            subprocess.run([ffmpeg(), "-y", "-v", "error", "-i", str(source),
                "-ss", str(decision.trim_start), "-t", str(seconds - decision.trim_start - decision.trim_end),
                "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-movflags", "+faststart", str(staged)],
                capture_output=True, timeout=180, check=True)
            originals = source.parent / "originais"
            originals.mkdir(exist_ok=True)
            backup = originals / source.name
            if backup.exists():
                raise ValueError("Já há uma revisão guardada para este corte")
            shutil.copy2(source, backup)
            os.replace(staged, source)
    side.update({"titulo": decision.titulo, "descricao": decision.descricao, "hashtags": decision.hashtags,
                 "edicao_ia": decision.model_dump()})
    if "inicio_s" in side:
        side["inicio_s"] += decision.trim_start
    if "fim_s" in side:
        side["fim_s"] -= decision.trim_end
    write_side(path, side)


def approve(path, base, side):
    from datetime import datetime
    from video_editor.cortes_gamer import render, style_for
    target = base / "aprovados" / path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.with_suffix(".mp4").exists():
        raise ValueError("Já há um corte aprovado com este nome; confira a Mesa")
    source = path.with_suffix(".mp4")
    style = style_for(side.get("cortes_gamer_style"))
    with TemporaryDirectory(prefix="aprovar-", dir=target.parent) as folder:
        staged = Path(folder) / source.name
        if side.get("cortes_gamer_watermark") and style.opacity and not side.get("cortes_gamer_baked"):
            render(source, staged, style=style)
            side["cortes_gamer_baked"] = True
        else:
            shutil.copy2(source, staged)
        # Keep the pending original until BOTH approved files are durable.
        os.replace(staged, target.with_suffix(".mp4"))
        side["decidido_em"] = datetime.now().isoformat(timespec="seconds")
        write_side(target, side)
    originals = target.parent / "originais"
    originals.mkdir(exist_ok=True)
    backup = originals / source.name
    if not backup.exists():
        shutil.copy2(source, backup)
    source.unlink()
    path.unlink()
    return target
