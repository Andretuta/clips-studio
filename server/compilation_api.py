"""Select published-ready local cuts and queue a new compilation."""

import json
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from core import queue
from server.events import broadcaster
from server.mesa_api import NOME, _ler, _posicao
from video_editor.cortes_gamer import CortesGamerStyle, picture_band, style_for


class CompilationIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    sources: list[str] = Field(min_length=2)
    cortes_gamer_watermark: bool = False
    cortes_gamer_style: CortesGamerStyle | None = None


def _local_file(path: Path, root: Path) -> Path | None:
    resolved = path.resolve()
    return resolved if resolved.is_relative_to(root) and resolved.is_file() else None


def _library_cut(row, data_dir: Path) -> Path | None:
    if row is None or not row["path"] or row["status"] not in ("rendered", "published"):
        return None
    return _local_file(Path(row["path"]), data_dir / "clips")


def _mesa_dirs(config: dict) -> list[tuple[str, Path]]:
    configured = (config.get("mesa") or {}).get("dir")
    if not configured:
        return []
    root = Path(configured).resolve()
    return [("aprovado", root / "aprovados"), ("pendente", root / "pendentes")]


def _mesa_video_id(source: str) -> str:
    return f"mesa_{sha256(source.encode()).hexdigest()[:20]}"


def source_path(source_id: str, d, config: dict, data_dir: Path) -> Path | None:
    kind, _, name = source_id.partition(":")
    if kind == "clip" and name.isascii() and name.isdecimal() and len(name) <= 18:
        return _library_cut(d.get_clip(int(name)), data_dir)
    if kind == "mesa" and NOME.fullmatch(name) and ".." not in name:
        for _, folder in _mesa_dirs(config):
            index = folder / f"{name}.json"
            if _ler(index) is not None and (path := _local_file(index.with_suffix(".mp4"), folder)):
                return path
    return None


def source_has_cortes_gamer(source: str, path: Path, d) -> bool:
    if source.startswith("mesa:"):
        return bool((_ler(path.with_suffix(".json")) or {}).get("cortes_gamer_baked"))
    row = d.get_clip(int(source.split(":", 1)[1]))
    return _clip_has_cortes_gamer(row)


def _clip_has_cortes_gamer(row) -> bool:
    opts = json.loads(row["render_opts"] or "{}") if row is not None else {}
    return bool(opts.get("cortes_gamer_watermark") and style_for(opts.get("cortes_gamer_style")).opacity)


def _sources(d, config: dict, data_dir: Path) -> list[dict]:
    rows = d.clips_with_status("rendered", "published")
    library = {row["id"]: row for row in rows}
    items = {}
    on_desk = set()
    for state, folder in _mesa_dirs(config):
        for index in sorted(folder.glob("*.json")):
            if (not NOME.fullmatch(index.stem) or ".." in index.stem
                    or (meta := _ler(index)) is None
                    or not _local_file(index.with_suffix(".mp4"), folder)):
                continue
            source = f"mesa:{index.stem}"
            if source in items:
                continue
            clip_id = meta.get("clip_id")
            row = library.get(clip_id) if isinstance(clip_id, int) else None
            if row is not None:
                on_desk.add(clip_id)
            span = _posicao(meta)
            duration = (row["end_s"] - row["start_s"] if row is not None else
                        span["fim_s"] - span["inicio_s"] if span else None)
            items[source] = {"id": source, "title": meta.get("titulo") or index.stem,
                             "channel": meta.get("streamer") or "", "state": state, "duration": duration,
                             "cortes_gamer_baked": bool(meta.get("cortes_gamer_baked"))}
    channels = {row["video_id"]: row["channel_name"] or row["title"] for row in d.videos_with_status("done")}
    prepared = {_mesa_video_id(source) for source in items}
    for row in rows:
        if row["id"] in on_desk or row["video_id"] in prepared or not _library_cut(row, data_dir):
            continue
        source = f"clip:{row['id']}"
        items[source] = {"id": source, "title": row["title"] or row["hook"] or f"Corte {row['id']}",
                         "channel": channels.get(row["video_id"]) or "", "state": "biblioteca",
                         "duration": row["end_s"] - row["start_s"],
                         "cortes_gamer_baked": _clip_has_cortes_gamer(row)}
    return list(items.values())


def install(app, *, config, db, data_dir, worker) -> None:
    @app.get("/compilations/sources")
    def sources():
        d = db()
        try:
            return _sources(d, config, data_dir)
        finally:
            d.close()

    @app.get("/compilations/sources/{source_id}/media")
    def media(source_id: str):
        d = db()
        try:
            path = source_path(source_id, d, config, data_dir)
        finally:
            d.close()
        if path is None:
            raise HTTPException(404, "Este corte não está mais disponível.")
        return FileResponse(path, media_type="video/mp4")

    @app.get("/compilations/sources/{source_id}/media/picture")
    def media_picture(source_id: str):
        return {"band": picture_band(Path(media(source_id).path))}

    @app.post("/publication/sources/{source_id}/prepare")
    def prepare_clip(source_id: str):
        from longform.compilation import save_mesa_cut

        d = db()
        try:
            path = source_path(source_id, d, config, data_dir)
            if path is None:
                raise HTTPException(404, "Este corte não está mais disponível.")
            if source_id.startswith("clip:"):
                clip = d.get_clip(int(source_id.split(":", 1)[1]))
            else:
                metadata = _ler(path.with_suffix(".json"))
                if metadata is None:
                    raise HTTPException(404, "Este corte não está mais disponível.")
                clip = save_mesa_cut(d, data_dir, _mesa_video_id(source_id), path, metadata)
            return {"video_id": clip["video_id"], "clip_id": clip["id"]}
        finally:
            d.close()

    @app.post("/compilations", status_code=202)
    def enqueue(body: CompilationIn):
        title = body.title.strip()
        if not title or len(set(body.sources)) < 2:
            raise HTTPException(400, "Informe um título e escolha pelo menos dois cortes diferentes.")
        d = db()
        try:
            if queue.capacity(d) <= 0:
                raise HTTPException(409, "A fila está cheia. Aguarde uma vaga para exportar.")
            for index, source in enumerate(body.sources, 1):
                if source_path(source, d, config, data_dir) is None:
                    raise HTTPException(404, f"O corte {index} da sequência não está mais disponível.")
            video_id = f"compilation_{uuid4().hex}"
            payload = {"sources": body.sources, "title": title}
            if body.cortes_gamer_watermark:
                payload["cortes_gamer_watermark"] = True
                if body.cortes_gamer_style is not None:
                    payload["cortes_gamer_style"] = body.cortes_gamer_style.model_dump()
            job_id = d.add_job("compilation", json.dumps(payload), video_id=video_id, title=title)
        finally:
            d.close()
        worker.notify()
        broadcaster.publish({"type": "queue"})
        return {"job_id": job_id, "video_id": video_id}
