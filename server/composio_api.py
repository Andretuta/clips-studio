"""Connect channels and queue explicitly requested Composio uploads."""

import json
import re
from contextlib import closing
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, SecretStr

from core import secrets
from publish import composio
from publish.errors import PublishError

Platform = Literal["youtube", "tiktok"]


class SettingsIn(BaseModel):
    api_key: SecretStr | None = None
    tiktok_auth_config: str | None = Field(default=None, max_length=128)


class ConnectIn(BaseModel):
    platform: Platform


class SendIn(ConnectIn):
    title: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=5000)


def _job(row) -> dict:
    platform = json.loads(row["request"])["platform"]
    return {
        "id": row["id"], "platform": platform, "status": row["status"], "error": row["error"],
        "url": f"https://studio.youtube.com/video/{row['youtube_id']}/edit" if row["youtube_id"] else "",
    }


def install(app, *, db, data_dir, publish_worker) -> None:
    @app.get("/composio/status")
    def status():
        key = composio.api_key(data_dir)
        with closing(db()) as d:
            channels = {}
            for platform in composio.TOOLS:
                try:
                    account, name = composio.connection(d, key, platform)
                    channels[platform] = {"connected": bool(account), "name": name, "error": ""}
                except PublishError as error:
                    channels[platform] = {"connected": False, "name": "", "error": error.message}
            return {"configured": bool(key), "tiktok_auth_config": d.get_flag(composio.TIKTOK_CONFIG) or "",
                    "channels": channels}

    @app.put("/composio/settings")
    def settings(body: SettingsIn):
        key = body.api_key.get_secret_value().strip() if body.api_key else ""
        tiktok = body.tiktok_auth_config.strip() if body.tiktok_auth_config is not None else None
        if tiktok and not re.fullmatch(r"ac_[A-Za-z0-9_-]+", tiktok):
            raise HTTPException(422, "Use o ID do Auth Config do TikTok, que começa com ac_.")
        with closing(db()) as d:
            previous_key = composio.api_key(data_dir)
            verified_key = key or previous_key
            key_changed = bool(key and key != previous_key)
            new_config = tiktok is not None and tiktok != (d.get_flag(composio.TIKTOK_CONFIG) or "")
            try:
                if key:
                    composio.verify_key(key)
                if tiktok and (new_config or key_changed):
                    config = composio.call(verified_key, "GET", f"/auth_configs/{tiktok}")
                    if (config.get("toolkit") or {}).get("slug") != "tiktok":
                        raise PublishError("O Auth Config informado não é do conector TikTok.")
            except PublishError as error:
                raise HTTPException(400, error.message) from None
            if key:
                secrets.save(data_dir, composio.KEY, {"key": key})
            if key_changed:
                d.set_flag("composio_account_youtube", "")
                d.set_flag("composio_account_tiktok", "")
            if new_config:
                d.set_flag(composio.TIKTOK_CONFIG, tiktok)
                d.set_flag("composio_account_tiktok", "")
        return {"ok": True}

    @app.post("/composio/connect")
    def connect(body: ConnectIn):
        with closing(db()) as d:
            try:
                return {"url": composio.link(d, composio.api_key(data_dir), body.platform)}
            except PublishError as error:
                raise HTTPException(400, error.message) from None

    @app.post("/composio/clips/{clip_id}/send", status_code=202)
    def send(clip_id: int, body: SendIn):
        with closing(db()) as d:
            clip = d.get_clip(clip_id)
            if clip is None or clip["status"] not in ("rendered", "published"):
                raise HTTPException(404, "Corte pronto não encontrado.")
            title = body.title.strip() or clip["title"] or clip["hook"] or f"Corte {clip_id}"
            try:
                composio.clip_path(clip, data_dir)
                account, _ = composio.connection(d, composio.api_key(data_dir), body.platform)
            except PublishError as error:
                raise HTTPException(400, error.message) from None
            if not account:
                raise HTTPException(409, "Conecte o canal no Composio antes de enviar.")
            user = composio.user_id(d)
            d.conn.execute("BEGIN IMMEDIATE")
            if d.active_publish_job_for_clip(clip_id):
                raise HTTPException(409, "Já existe um envio ativo para este MP4.")
            request = {
                "provider": "composio", "platform": body.platform, "account_id": account,
                "user_id": user, "title": title[:100], "description": body.description, "tags": [],
            }
            job_id = d.add_publish_job(clip_id, json.dumps(request), video_id=clip["video_id"],
                                       start_s=clip["start_s"], end_s=clip["end_s"])
            row = d.get_publish_job(job_id)
        publish_worker.notify()
        return _job(row)

    @app.get("/composio/clips/{clip_id}/jobs")
    def jobs(clip_id: int):
        with closing(db()) as d:
            rows = d.conn.execute(
                "SELECT * FROM publish_jobs WHERE clip_id = ? AND json_extract(request, '$.provider') = 'composio' "
                "ORDER BY id DESC", (clip_id,),
            )
            latest = {}
            for row in rows:
                item = _job(row)
                latest.setdefault(item["platform"], item)
            return list(latest.values())
