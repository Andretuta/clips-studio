"""Composio OAuth and uploads for the Clipador publishing screen."""

import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import requests

from core import secrets
from publish.errors import PublishCancelled, PublishError

API = "https://backend.composio.dev/api/v3.1"
KEY = "composio_api_key"
TIKTOK_CONFIG = "composio_tiktok_auth_config"
TOOLS = {
    "youtube": ("YOUTUBE_UPLOAD_VIDEO", "20261113_00"),
    "tiktok": ("TIKTOK_UPLOAD_VIDEO", "20261101_00"),
}


def api_key(data_dir: Path) -> str:
    saved = secrets.load(data_dir, KEY) or {}
    return str(saved.get("key") or os.environ.get("COMPOSIO_API_KEY") or "").strip()


def user_id(db) -> str:
    db.conn.execute("INSERT OR IGNORE INTO app_state (key, value) VALUES (?, ?)",
                    ("composio_user_id", f"clipador_{uuid4().hex}"))
    db.conn.commit()
    return db.get_flag("composio_user_id")


def call(key: str, method: str, path: str, *, body: dict | None = None, timeout: int = 20,
         missing_ok: bool = False) -> dict:
    if not key:
        raise PublishError("Configure a chave do Composio em Publicação → Canais de postagem.")
    try:
        response = requests.request(method, API + path, headers={"x-api-key": key},
                                    json=body, timeout=(8, timeout), allow_redirects=False)
    except requests.RequestException:
        raise PublishError("Não foi possível comunicar com o Composio.") from None
    if missing_ok and response.status_code == 404:
        return {}
    if not 200 <= response.status_code < 300:
        raise PublishError(f"O Composio retornou HTTP {response.status_code}.")
    try:
        value = response.json()
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    raise PublishError("O Composio retornou uma resposta inesperada.")


def link(db, key: str, platform: str) -> str:
    body = {"user_id": user_id(db), "toolkits": {"enable": [platform]}, "instant": False}
    if platform == "tiktok":
        config = db.get_flag(TIKTOK_CONFIG)
        if not config:
            raise PublishError("Informe o ID do Auth Config do seu app TikTok no Composio.")
        body["auth_configs"] = {"tiktok": config}
    created = call(key, "POST", "/tool_router/session", body=body)
    session = created.get("session_id", "")
    if not re.fullmatch(r"trs_[A-Za-z0-9_-]+", str(session)):
        raise PublishError("O Composio não retornou uma sessão de autorização.")
    request = call(key, "POST", f"/tool_router/session/{session}/link", body={"toolkit": platform})
    url = str(request.get("redirect_url") or "")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc not in ("connect.composio.dev", "app.composio.dev")
            or not parsed.path.startswith("/link/")):
        raise PublishError("O endereço de autorização do Composio é inválido.")
    account = request.get("connected_account_id")
    if not re.fullmatch(r"ca_[A-Za-z0-9_-]+", str(account)):
        raise PublishError("O Composio não identificou a conta a autorizar.")
    db.set_flag(f"composio_account_{platform}", account)
    return url


def connection(db, key: str, platform: str) -> tuple[str, str]:
    account = db.get_flag(f"composio_account_{platform}")
    if not key or not re.fullmatch(r"ca_[A-Za-z0-9_-]+", account or ""):
        return "", ""
    result = call(key, "GET", f"/connected_accounts/{account}", missing_ok=True)
    if (result.get("status") != "ACTIVE" or result.get("is_disabled")
            or (result.get("toolkit") or {}).get("slug") != platform):
        return "", ""
    profile = (result.get("state") or {}).get("val") or {}
    return account, str(profile.get("displayName") or "")[:120]


def clip_path(clip, data_dir: Path) -> Path:
    path = Path(clip["path"] or "").resolve()
    if not path.is_relative_to(data_dir.resolve() / "clips") or path.suffix.lower() != ".mp4" or not path.is_file():
        raise PublishError("O MP4 pronto não está disponível na biblioteca do Clipador.")
    return path


def verify_key(key: str) -> None:
    for tool, _ in TOOLS.values():
        call(key, "GET", f"/tools/{tool}")


def _stage(key: str, platform: str, tool: str, file: Path) -> dict:
    mime = "video/mp4"
    with file.open("rb") as media:
        checksum = hashlib.md5(usedforsecurity=False)
        while chunk := media.read(1024 * 1024):
            checksum.update(chunk)
        response = call(key, "POST", "/files/upload/request", body={
            "toolkit_slug": platform, "tool_slug": tool, "filename": file.name,
            "mimetype": mime, "md5": checksum.hexdigest(),
        })
        remote_key = response.get("key")
        if not remote_key:
            raise PublishError("O Composio não reservou o arquivo para envio.")
        if response.get("type") == "new":
            url = str(response.get("new_presigned_url") or response.get("newPresignedUrl") or "")
            parsed = urlsplit(url)
            host = parsed.hostname or ""
            s3 = re.fullmatch(r"(?:[a-z0-9.-]+\.)?s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com", host)
            r2 = re.fullmatch(r"temp\.[a-f0-9]{32}\.r2\.cloudflarestorage\.com", host)
            if parsed.scheme != "https" or parsed.netloc != host or not (s3 or r2):
                raise PublishError("O endereço de armazenamento do Composio é inválido.")
            media.seek(0)
            try:
                uploaded = requests.put(url, data=media, headers={"Content-Type": mime},
                                        timeout=(8, 600), allow_redirects=False)
            except requests.RequestException:
                raise PublishError("A transferência do MP4 para o Composio foi interrompida.") from None
            if not 200 <= uploaded.status_code < 300:
                raise PublishError(f"O armazenamento do Composio recusou o MP4 (HTTP {uploaded.status_code}).")
        elif response.get("type") != "existing":
            raise PublishError("O Composio não confirmou que o MP4 está disponível.")
    return {"name": file.name, "mimetype": mime, "s3key": remote_key}


def tiktok_public_allowed(key: str, data: dict) -> bool:
    """TikTok só aceita público de app auditado; a conta diz quais níveis aceita agora."""
    try:
        result = call(key, "POST", "/tools/execute/TIKTOK_QUERY_CREATOR_INFO", body={
            "user_id": data["user_id"], "connected_account_id": data["account_id"],
            "version": TOOLS["tiktok"][1], "arguments": {}})
    except PublishError:
        return False
    payload = result.get("data") if isinstance(result.get("data"), dict) else {}
    nested = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    options = payload.get("privacy_level_options") or nested.get("privacy_level_options") or []
    return result.get("successful") is True and "PUBLIC_TO_EVERYONE" in options


def upload(key: str, data: dict, file: Path, cancelled, submitting=lambda: None) -> str:
    from publish.transfer import bounded_upload
    return bounded_upload(key, data, file, cancelled, submitting)


def _upload(key: str, data: dict, file: Path, cancelled, submitting=lambda: None) -> str:
    """Return the YouTube video ID or the TikTok inbox submission ID."""
    platform = data["platform"]
    tool, version = TOOLS[platform]
    media = _stage(key, platform, tool, file)
    if cancelled():
        raise PublishCancelled("Envio cancelado.")
    if platform == "youtube":
        privacy = data.get("privacy") if data.get("privacy") in ("public", "unlisted", "private") else "public"
        args = {"videoFilePath": media, "title": data["title"], "description": data["description"],
                "tags": data["tags"], "categoryId": "20", "privacyStatus": privacy}
    elif data.get("tiktok_direct"):
        caption = " ".join([data["title"], *data.get("tags", [])])[:2200]
        args = {"file_to_upload": media, "publish": True, "privacy_level": "PUBLIC_TO_EVERYONE",
                "caption": caption}
    else:
        args = {"file_to_upload": media, "publish": False}
    submitting()
    try:
        result = call(key, "POST", f"/tools/execute/{tool}", body={
            "user_id": data["user_id"], "connected_account_id": data["account_id"],
            "version": version, "arguments": args,
        }, timeout=600)
    except PublishError as error:
        raise PublishError(f"{error.message} Confira o painel do canal antes de repetir.") from None
    if result.get("successful") is not True:
        log_id = str(result.get("log_id") or "")
        trace = f" Registro {log_id}." if re.fullmatch(r"log_[A-Za-z0-9_-]+", log_id) else ""
        raise PublishError(f"O Composio não confirmou o envio.{trace}")
    payload = result.get("data")
    if not isinstance(payload, dict):
        payload = {}
    nested = payload.get("data")
    if not isinstance(nested, dict):
        nested = {}
    if platform == "youtube":
        identifier = payload.get("id") or payload.get("video_id") or payload.get("videoId") or nested.get("id")
        pattern = r"[A-Za-z0-9_-]{11}"
    else:
        identifier = payload.get("publish_id") or nested.get("publish_id")
        pattern = r"[A-Za-z0-9_~.-]+"
    if not re.fullmatch(pattern, str(identifier or "")):
        raise PublishError("Confira o painel do canal antes de repetir. O envio terminou sem um ID reconhecido.")
    return str(identifier)
