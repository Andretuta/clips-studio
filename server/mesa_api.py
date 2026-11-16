"""The approval desk (/mesa): the cuts an external clipper (the "cola") leaves
in `<mesa.dir>/pendentes` as an mp4 and a JSON side by side, approved into
`aprovados` or discarded into `descartados` (moved, never deleted), and the
control room: which recorder channels are writing, today's lives with where
each cut came from, and the best cuts still waiting.

Off unless `mesa.dir` is set in settings.yaml. The routes that change files
take the desktop app's session header, as the campaign routes do.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from plugins import session
from video_editor.cortes_gamer import CortesGamerStyle, picture_band, style_for

NOME = re.compile(r"[A-Za-z0-9_.-]+")
# "<streamer> 2026-11-14 1825 [local_55a38fd2ff41]\clip_00320-00356.mp4": a block of a recorded live.
# Cuts the garimpeiro found ("[tw_clip_...]") have no place in a live and don't match.
ORIGEM = re.compile(r"(?P<data>\d{4}-\d{2}-\d{2}) (?P<hh>\d{2})(?P<mm>\d{2}) \[local_[^\]]+\][\\/]"
                    r"clip_(?P<ini>\d+)-(?P<fim>\d+)\.mp4$")
CAMPOS = ("streamer", "plataforma", "fonte", "titulo", "descricao", "hashtags", "nota", "clip_id",
          "video_id", "criado_em", "destinos", "cortes_gamer_watermark", "cortes_gamer_baked",
          "cortes_gamer_style")
GRAVANDO_S = 180  # the recorder writes a segment a minute; three without one means it stopped


class Edicao(BaseModel):
    titulo: str | None = None
    descricao: str | None = None
    hashtags: list[str] | None = None
    destinos: list[str] | None = None
    cortes_gamer_watermark: bool | None = None
    cortes_gamer_style: CortesGamerStyle | None = None


def _ler(j: Path, precisa_video: bool = True) -> dict | None:
    try:
        d = json.loads(j.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or (precisa_video and not j.with_suffix(".mp4").is_file()):
        return None
    return d


def _escrever(j: Path, d: dict) -> None:
    tmp = j.with_name(j.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, j)


def _posicao(d: dict) -> dict | None:
    m = ORIGEM.search(str(d.get("arquivo_original") or ""))
    if not m:
        return None
    # bloco_s: the Cola writes it since the 4 + 1 min blocks; older cuts came from 16-minute blocks.
    return {"data": m["data"], "bloco": f"{m['hh']}:{m['mm']}", "inicio_s": int(m["ini"]), "fim_s": int(m["fim"]),
            "bloco_s": int(d.get("bloco_s") or 960)}


def _hoje() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def install(app: FastAPI, *, config: dict, db, data_dir, session_secret: str) -> None:
    mesa = config.get("mesa") or {}
    base = Path(mesa["dir"]) if mesa.get("dir") else None
    gravacoes = Path(mesa["gravacoes_dir"]) if mesa.get("gravacoes_dir") else None
    pastas = {"pendente": base / "pendentes", "aprovado": base / "aprovados",
              "descartado": base / "descartados"} if base else {}

    def require_session(x_clips_kitty_session: str | None = Header(default=None)) -> None:
        if not session.matches(session_secret, x_clips_kitty_session):
            raise HTTPException(403, f"This needs the {session.HEADER} header. The desktop app sends it; a script "
                                     f"finds it in {session.path(data_dir)}.")

    guarded = [Depends(require_session)]

    def achar(nome: str) -> Path:
        """The JSON of a pending cut, or 404: the name never leaves the folder."""
        if base and NOME.fullmatch(nome) and ".." not in nome:
            j = pastas["pendente"] / f"{nome}.json"
            if j.is_file() and j.with_suffix(".mp4").is_file():
                return j
        raise HTTPException(404, "No such cut on the desk")

    def jsons(estado: str):
        pasta = pastas[estado]
        return sorted(pasta.glob("*.json")) if pasta.is_dir() else []

    def view(nome: str, d: dict, no_editor: bool) -> dict:
        pos = _posicao(d)
        live = {k: pos[k] for k in ("bloco", "inicio_s", "fim_s", "bloco_s")} if pos else None
        return {"nome": nome, **{k: d.get(k) for k in CAMPOS}, "no_editor": no_editor, "live": live}

    def pendentes() -> list[dict]:
        lidos = [(j.stem, d) for j in jsons("pendente") if (d := _ler(j)) is not None]
        conn = db()
        try:
            cortes = [view(nome, d, isinstance(d.get("clip_id"), int) and conn.get_clip(d["clip_id"]) is not None)
                      for nome, d in lidos]
        finally:
            conn.close()
        return sorted(cortes, key=lambda c: (-(c["nota"] or 0), c["nome"]))

    def decididos_hoje(estado: str) -> int:
        hoje = _hoje()
        return sum(1 for j in jsons(estado)
                   if str((_ler(j, precisa_video=False) or {}).get("decidido_em", "")).startswith(hoje))

    def contagens(cortes: list[dict]) -> dict:
        return {"pendentes": len(cortes), "aprovados_hoje": decididos_hoje("aprovado"),
                "descartados_hoje": decididos_hoje("descartado"), "aprovados": len(jsons("aprovado"))}

    @app.get("/mesa/cortes")
    def listar():
        if not base:
            return {"enabled": False}
        cortes = pendentes()
        return {"enabled": True, "cortes": cortes, "contagens": contagens(cortes)}

    @app.get("/mesa/cortes/{nome}/video")
    def video(nome: str):
        return FileResponse(achar(nome).with_suffix(".mp4"), media_type="video/mp4")

    @app.get("/mesa/cortes/{nome}/video/picture")
    def video_picture(nome: str):
        return {"band": picture_band(achar(nome).with_suffix(".mp4"))}

    @app.get("/mesa/cortes/{nome}/capa")
    def capa(nome: str):
        """A small JPEG of the cut, for the desk's list: made once from a frame
        of the video and cached on disk, so the list never holds the video
        open (Windows could then not move it)."""
        from core.binaries import ffmpeg
        from sources.preview_frames import made_once

        j = achar(nome)
        pos = _posicao(_ler(j) or {})
        quando = (pos["fim_s"] - pos["inicio_s"]) / 2 if pos else 1.0

        def make(part: Path) -> None:
            r = subprocess.run([ffmpeg(), "-y", "-v", "error", "-ss", f"{quando:.2f}", "-i", str(j.with_suffix(".mp4")),
                                "-frames:v", "1", "-vf", "scale=216:-2", "-q:v", "5", str(part)],
                               capture_output=True, text=True)
            if r.returncode != 0 or not part.exists():
                raise HTTPException(404, "No frame could be read from this cut")

        return FileResponse(made_once(Path(data_dir) / "previews" / "mesa", f"{nome}.jpg", make),
                            media_type="image/jpeg", headers={"Cache-Control": "private, max-age=604800"})

    @app.patch("/mesa/cortes/{nome}", dependencies=guarded)
    def editar(nome: str, edicao: Edicao):
        j = achar(nome)
        d = _ler(j)
        if d is None:
            raise HTTPException(404, "No such cut on the desk")
        d.update(edicao.model_dump(exclude_none=True))
        _escrever(j, d)
        return view(nome, d, False)

    def decidir(nome: str, estado: str, edicao: Edicao | None) -> dict:
        j = achar(nome)
        d = _ler(j)
        if d is None:
            raise HTTPException(404, "No such cut on the desk")
        if edicao:
            d.update(edicao.model_dump(exclude_none=True))
        d["decidido_em"] = datetime.now().isoformat(timespec="seconds")
        pasta = pastas[estado]
        pasta.mkdir(parents=True, exist_ok=True)
        alvo, n = nome, 1
        while (pasta / f"{alvo}.mp4").exists() or (pasta / f"{alvo}.json").exists():
            n += 1
            alvo = f"{nome}-{n}"
        source = j.with_suffix(".mp4")
        target = pasta / f"{alvo}.mp4"
        style = style_for(d.get("cortes_gamer_style"))
        if (estado == "aprovado" and d.get("cortes_gamer_watermark") and style.opacity
                and not d.get("cortes_gamer_baked")):
            from video_editor.cortes_gamer import render

            originals = pasta / "originais"
            originals.mkdir(exist_ok=True)
            backup = originals / target.name
            if backup.exists():
                raise HTTPException(409, "Já existe um original com esse nome.")
            with TemporaryDirectory(prefix="marca-", dir=pasta) as folder:
                staged = Path(folder) / target.name
                try:
                    render(source, staged, style=style)
                except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                    raise HTTPException(500, f"Não foi possível aplicar a marca Cortes Gamer: {exc}") from exc
                # Keep the clean original for future use. Until rendering succeeds,
                # the cut remains on the desk with its original file.
                try:
                    source.rename(backup)
                except PermissionError:
                    raise HTTPException(409, "O vídeo ainda está aberto. Tente novamente.") from None
                try:
                    staged.replace(target)
                    d["cortes_gamer_baked"] = True
                    _escrever(target.with_suffix(".json"), d)
                except OSError:
                    target.unlink(missing_ok=True)
                    backup.rename(source)
                    raise
        else:
            # The video first: if the player still has it open, the cut stays on the desk.
            for tentativa in range(10):
                try:
                    shutil.move(source, target)
                    break
                except PermissionError:
                    if tentativa == 9:
                        raise HTTPException(409, "The video is still open; try again in a moment") from None
                    time.sleep(0.2)
            _escrever(target.with_suffix(".json"), d)
        j.unlink()
        return {"nome": alvo, "estado": estado}

    @app.post("/mesa/cortes/{nome}/aprovar", dependencies=guarded)
    def aprovar(nome: str, edicao: Edicao | None = None):
        return decidir(nome, "aprovado", edicao)

    @app.post("/mesa/cortes/{nome}/descartar", dependencies=guarded)
    def descartar(nome: str, edicao: Edicao | None = None):
        return decidir(nome, "descartado", edicao)

    def canais() -> list[dict]:
        if not gravacoes or not gravacoes.is_dir():
            return []
        agora, achados = time.time(), []
        for pasta in sorted(p for p in gravacoes.iterdir() if p.is_dir()):
            mtimes = [e.stat().st_mtime for e in os.scandir(pasta) if e.name.endswith(".ts")]
            # No segment left (the recorder deletes them once cut into blocks): the folder's own
            # last change says when it stopped.
            idade = int(agora - (max(mtimes) if mtimes else pasta.stat().st_mtime))
            plataforma, _, canal = pasta.name.partition("_")
            achados.append({"nome": pasta.name, "plataforma": plataforma, "canal": canal or plataforma,
                            "gravando": bool(mtimes) and idade < GRAVANDO_S, "ultimo_s": idade})
        return achados

    def lives() -> list[dict]:
        hoje, por_streamer = _hoje(), {}
        for estado in pastas:
            for j in jsons(estado):
                d = _ler(j, precisa_video=False)
                pos = _posicao(d) if d else None
                if not pos or pos["data"] != hoje:
                    continue
                live = por_streamer.setdefault(d.get("streamer") or "?", {
                    "streamer": d.get("streamer") or "?", "plataforma": d.get("plataforma"), "blocos": {}})
                live["blocos"].setdefault(pos["bloco"], []).append(
                    {"nome": j.stem, "inicio_s": pos["inicio_s"], "fim_s": pos["fim_s"], "nota": d.get("nota"),
                     "estado": estado, "bloco_s": pos["bloco_s"]})
        return [{**lv, "blocos": [{"inicio": b, "dur_s": max(c.pop("bloco_s") for c in cs),
                                   "cortes": sorted(cs, key=lambda c: c["inicio_s"])}
                                  for b, cs in sorted(lv["blocos"].items())]}
                for _, lv in sorted(por_streamer.items())]

    @app.get("/mesa/controle")
    def controle():
        if not base:
            return {"enabled": False}
        cortes = pendentes()
        return {"enabled": True, "canais": canais(), "lives": lives(), "melhores": cortes[:5],
                "contagens": contagens(cortes)}
