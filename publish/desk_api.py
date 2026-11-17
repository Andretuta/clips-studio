"""Mesa → cópia independente na biblioteca → fila; autonomia opt-in e auditável."""

import hashlib
import json
import math
import re
import shutil
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Literal

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field

from plugins import session
from publish.errors import PublishError
from video_editor import desk

_lock = threading.Lock()
FLAG = "publication_autonomy"


class Policy(BaseModel):
    edit_enabled: bool = False
    post_enabled: bool = False
    threshold: float = Field(default=.9, ge=0, le=1, allow_inf_nan=False)
    max_per_hour: int = Field(default=2, ge=1, le=20)
    target: Literal["youtube", "tiktok"] = "youtube"
    youtube_privacy: Literal["private", "public"] = "private"


class TestSend(BaseModel):
    target: Literal["youtube", "tiktok"] = "youtube"


def policy(db):
    return Policy.model_validate_json(db.get_flag(FLAG) or "{}")


def eligible(side, settings):
    moment = side.get("momento_chave")
    score = moment.get("score") if isinstance(moment, dict) else None
    return (isinstance(score, (int, float)) and not isinstance(score, bool)
            and math.isfinite(score) and 0 <= score <= 1 and score >= settings.threshold)


def session_guard(data_dir):
    def guard(x_clips_kitty_session: str | None = Header(default=None)):
        try:
            expected = session.path(data_dir).read_text(encoding="utf-8").strip()
        except OSError:
            expected = ""
        if not expected or not session.matches(expected, x_clips_kitty_session):
            raise HTTPException(403, "A sessão do aplicativo é necessária.")
    return guard


def install(app, *, db, data_dir, publish_worker):
    config = publish_worker.config
    base = Path((config.get("mesa") or {}).get("dir") or data_dir / "mesa-disabled")

    guarded = [Depends(session_guard(data_dir))]

    def locate(name):
        if not (config.get("mesa") or {}).get("dir") or not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or ".." in name:
            raise HTTPException(404, "Corte da Mesa não encontrado.")
        for folder in ("aprovados", "pendentes"):
            path = base / folder / f"{name}.json"
            if path.is_file() and path.with_suffix(".mp4").is_file():
                return path, json.loads(path.read_text(encoding="utf-8"))
        raise HTTPException(404, "Corte da Mesa não encontrado.")

    @app.get("/publication/autonomy", dependencies=guarded)
    def settings():
        with closing(db()) as d:
            return policy(d).model_dump()

    @app.put("/publication/autonomy", dependencies=guarded)
    def save_settings(body: Policy):
        with closing(db()) as d:
            d.set_flag(FLAG, body.model_dump_json())
        return body.model_dump()

    @app.get("/publication/mesa/{name}/details", dependencies=guarded)
    def details(name: str):
        _, side = locate(name)
        return {k: side.get(k) for k in ("momento_chave", "edicao_ia", "automacao")}

    @app.get("/publication/history", dependencies=guarded)
    def history():
        from publish import receipts
        with closing(db()) as d:
            rows = d.conn.execute("SELECT * FROM publish_jobs ORDER BY id DESC LIMIT 30").fetchall()
            return [{"id": row["id"], "status": row["status"], "error": row["error"],
                     "youtube_id": row["youtube_id"], "platform": json.loads(row["request"]).get("platform", "youtube"),
                     "receipt": receipts.get(d, row["id"])} for row in rows]

    def review(path, side, d):
        if side.get("edicao_ia") or path.parent.name != "pendentes":
            return
        from llm.editorial import decide
        from llm.registry import create_backend
        llm_config = {**config.get("llm", {}), "data_dir": str(data_dir), "unattended": True}
        from llm.signin import catalog
        provider = str(llm_config.get("backend") or "").partition("/")[0]
        llm_config["plan_automation"] = d.get_flag(catalog.AUTOMATION_FLAG + provider) == "1"
        seconds = desk.duration(path.with_suffix(".mp4"))
        decision = decide(create_backend(llm_config), side, seconds)
        desk.edit(path, side, decision, seconds)

    def send(name, target, automatic):
        with _lock, closing(db()) as d:
            settings = policy(d)
            path, side = locate(name)
            if automatic and not settings.post_enabled:
                if settings.edit_enabled:
                    review(path, side, d)
                return {"status": "review", "reason": "Postagem automática desligada"}
            if automatic and not eligible(side, settings):
                if settings.edit_enabled:
                    review(path, side, d)
                return {"status": "review", "reason": "Pontuação ausente, inválida ou abaixo do limiar"}
            target = settings.target if automatic else target
            d.conn.execute("""CREATE TABLE IF NOT EXISTS desk_publications (
                name TEXT NOT NULL, target TEXT NOT NULL, created REAL NOT NULL, automatic INTEGER NOT NULL,
                job_id INTEGER, reason TEXT NOT NULL, PRIMARY KEY(name, target))""")
            d.conn.commit()
            prior = d.conn.execute("SELECT * FROM desk_publications WHERE name=? AND target=?", (name, target)).fetchone()
            if prior:
                return {"status": "existing" if prior["job_id"] else "uncertain", "job_id": prior["job_id"], "reason": prior["reason"]}
            from publish import composio
            from server import youtube_service
            if target == "youtube":
                status = youtube_service.status_payload(d, config, data_dir)
                if not status.get("enabled") or not status.get("connected"):
                    raise HTTPException(409, "Conecte e habilite o YouTube nas configurações.")
                request = {"channel_id": youtube_service.default_channel_id(d),
                           "privacy": settings.youtube_privacy if automatic else "private",
                           "notify_subscribers": False}
            else:
                account, _ = composio.connection(d, composio.api_key(data_dir), "tiktok")
                if not account:
                    raise HTTPException(409, "Conecte o TikTok pelo Composio.")
                request = {"provider": "composio", "platform": "tiktok", "account_id": account,
                           "user_id": composio.user_id(d)}
            if automatic and settings.edit_enabled:
                review(path, side, d)
            reason = (f"momento_chave.score={side['momento_chave']['score']} >= {settings.threshold}; "
                      + "; ".join(str(x)[:100] for x in (side["momento_chave"].get("motivos") or [])[:5])) if automatic else "Ensaio privado solicitado na Mesa"
            # Reserve before slow editing, approval and queue insertion. A crash
            # here requires review; it cannot create a second submission.
            d.conn.execute("BEGIN IMMEDIATE")
            count = d.conn.execute("SELECT count(*) FROM desk_publications WHERE automatic=1 AND created>?", (time.time()-3600,)).fetchone()[0]
            if automatic and count >= settings.max_per_hour:
                raise HTTPException(429, "Teto de postagens automáticas por hora atingido.")
            d.conn.execute("INSERT INTO desk_publications VALUES (?, ?, ?, ?, NULL, ?)", (name, target, time.time(), int(automatic), reason))
            d.conn.commit()
            side["automacao"] = {"motivo": reason, "destino": target, "automatica": automatic}
            if path.parent.name == "pendentes":
                path = desk.approve(path, base, side)
            else:
                desk.write_side(path, side)
            digest = hashlib.sha256(name.encode()).hexdigest()[:24]
            file = Path(data_dir) / "clips" / "mesa" / f"{digest}.mp4"
            file.parent.mkdir(parents=True, exist_ok=True)
            if not file.exists():
                staged = file.with_suffix(".mp4.tmp")
                shutil.copy2(path.with_suffix(".mp4"), staged)
                staged.replace(file)
            video_id = "mesa_" + digest
            d.upsert_video(video_id, title=side.get("titulo") or name, channel_name=side.get("streamer") or "")
            d.set_video_status(video_id, "done")
            clip_id = d.add_clip(video_id, 0, desk.duration(file), 0, side.get("titulo") or name,
                                 path=str(file), title=side.get("titulo") or name,
                                 hashtags=json.dumps(side.get("hashtags") or []))
            if clip_id is None:
                clip_id = d.conn.execute("SELECT id FROM clips WHERE video_id=?", (video_id,)).fetchone()[0]
            request.update({"title": (side.get("titulo") or name)[:100],
                            "description": (side.get("descricao") or "")[:3000], "tags": side.get("hashtags") or []})
            job_id = d.add_publish_job(clip_id, json.dumps(request), video_id=video_id)
            d.conn.execute("UPDATE desk_publications SET job_id=? WHERE name=? AND target=?", (job_id, name, target))
            d.conn.commit()
            publish_worker.notify()
            return {"status": "queued", "job_id": job_id, "reason": reason}

    @app.post("/publication/mesa/{name}/private-test", dependencies=guarded)
    def private_test(name: str, body: TestSend):
        try:
            return send(name, body.target, False)
        except PublishError as exc:
            raise HTTPException(409, exc.message) from None

    @app.post("/publication/mesa/{name}/auto", dependencies=guarded)
    def auto(name: str):
        try:
            return send(name, "youtube", True)
        except PublishError as exc:
            raise HTTPException(409, exc.message) from None
