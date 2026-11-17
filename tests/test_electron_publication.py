"""OAuth e publicação com HTTP/LLM dublês; nenhuma chamada externa."""

import json
import time
import webbrowser
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.state import StateDB
from plugins import session
from publish import composio, receipts, transfer
from publish.desk_api import Policy, eligible
from server.composio_api import install
from server.publisher import PublishWorker
from video_editor import desk


@pytest.fixture
def rig(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    path = data / "state.db"
    base = tmp_path / "saida"
    (base / "pendentes").mkdir(parents=True)
    config = {"mesa": {"dir": str(base)}}
    worker = PublishWorker(config, path, data)
    worker.notify = Mock()
    d = StateDB(path)
    d.close()
    app = FastAPI()
    install(app, db=lambda: StateDB(path), data_dir=data, publish_worker=worker)
    client = TestClient(app)
    headers = {session.HEADER: session.secret_for(data, {})}
    from server import youtube_service
    monkeypatch.setattr(youtube_service, "status_payload", lambda *a: {"enabled": True, "connected": True})
    monkeypatch.setattr(youtube_service, "default_channel_id", lambda *a: "channel-test")
    monkeypatch.setattr(desk, "duration", lambda *a: 30)
    return client, headers, base, data, path, worker


def cut(base, name="corte", moment=None):
    p = base / "pendentes" / f"{name}.json"
    side = {"titulo": "Fuga #GTA6", "descricao": "Uma fuga", "hashtags": ["#GTA6"],
            "cortes_gamer_watermark": False, "streamer": "canal"}
    if moment is not None:
        side["momento_chave"] = moment
    p.write_text(json.dumps(side), encoding="utf-8")
    p.with_suffix(".mp4").write_bytes(b"video")
    return p


def test_youtube_mesa_private_and_durable_duplicate_guard(rig):
    client, headers, base, data, path, worker = rig
    cut(base)
    route = "/publication/mesa/corte/private-test"
    assert client.post(route, json={}).status_code == 403
    response = client.post(route, json={}, headers=headers)
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    again = client.post(route, json={}, headers=headers).json()
    assert again["job_id"] == job_id and again["status"] == "existing"
    with StateDBContext(path) as d:
        request = json.loads(d.get_publish_job(job_id)["request"])
        assert request["privacy"] == "public" and not request["notify_subscribers"]
        assert request["channel_id"] == "channel-test"
        assert d.conn.execute("SELECT count(*) FROM publish_jobs").fetchone()[0] == 1
    assert (base / "aprovados" / "originais" / "corte.mp4").read_bytes() == b"video"
    assert not (base / "pendentes" / "corte.json").exists()
    assert list((data / "clips" / "mesa").glob("*.mp4"))


class StateDBContext:
    def __init__(self, path): self.db = StateDB(path)
    def __enter__(self): return self.db
    def __exit__(self, *a): self.db.close()


@pytest.mark.parametrize("moment", [None, {}, {"score": .89}, {"score": "0.99"}, {"score": True}, {"score": 2}, {"score": float('nan')}])
def test_missing_or_invalid_score_never_autoposts(rig, moment):
    client, headers, base, _, path, _ = rig
    cut(base, moment=moment)
    assert client.put("/publication/autonomy", headers=headers, json={"post_enabled": True}).status_code == 200
    result = client.post("/publication/mesa/corte/auto", headers=headers)
    assert result.status_code == 200 and result.json()["status"] == "review"
    with StateDBContext(path) as d:
        assert d.conn.execute("SELECT count(*) FROM publish_jobs").fetchone()[0] == 0


def test_autonomy_defaults_off_limit_and_reason_survive_reopen(rig):
    client, headers, base, _, path, _ = rig
    assert client.get("/publication/autonomy", headers=headers).json()["post_enabled"] is False
    cut(base, moment={"score": .95, "motivos": ["pico do chat"]})
    assert client.post("/publication/mesa/corte/auto", headers=headers).json()["status"] == "review"
    client.put("/publication/autonomy", headers=headers, json={"post_enabled": True, "max_per_hour": 1})
    result = client.post("/publication/mesa/corte/auto", headers=headers)
    assert result.status_code == 200, result.text
    assert "pico do chat" in result.json()["reason"]
    cut(base, "outro", {"score": 1, "motivos": []})
    assert client.post("/publication/mesa/outro/auto", headers=headers).status_code == 429
    assert (base / "pendentes" / "outro.mp4").exists()
    with StateDBContext(path) as d:
        assert d.conn.execute("SELECT count(*) FROM desk_publications").fetchone()[0] == 1


def test_tiktok_mesa_uses_draft_and_no_source_dependency(rig, monkeypatch):
    client, headers, base, _, path, worker = rig
    cut(base)
    monkeypatch.setattr(composio, "api_key", lambda *a: "fake")
    monkeypatch.setattr(composio, "connection", lambda *a: ("ca_test", "Conta"))
    captured = []
    def upload(key, data, file, cancel, submitting):
        submitting()
        captured.append(data)
        return "v_inbox~02"
    monkeypatch.setattr(composio, "upload", upload)
    result = client.post("/publication/mesa/corte/private-test", headers=headers, json={"target": "tiktok"})
    assert result.status_code == 200, result.text
    with StateDBContext(path) as d:
        worker._publish(d, d.claim_next_publish_job())
    history = client.get("/publication/history", headers=headers).json()[0]
    assert history["status"] == "awaiting_operator" and history["receipt"]["remote_id"] == "v_inbox~02"
    assert captured[0]["platform"] == "tiktok"


def test_uncertain_requires_explicit_reconciliation_before_retry(rig, monkeypatch):
    client, headers, _, data, path, worker = rig
    with StateDBContext(path) as d:
        d.upsert_video("v")
        file = data / "clips" / "clip.mp4"
        file.parent.mkdir()
        file.write_bytes(b"fake")
        cid = d.add_clip("v", 0, 30, 90, "Teste", path=str(file))
        d.set_flag("composio_account_tiktok", "ca_test")
    monkeypatch.setattr(composio, "api_key", lambda *a: "fake")
    monkeypatch.setattr(composio, "connection", lambda *a: ("ca_test", "Conta"))
    def lost(*a, submitting, **kw):
        submitting()
        raise receipts.UncertainDelivery("Resposta perdida; confira o canal.")
    monkeypatch.setattr(composio, "upload", lost)
    route = f"/composio/clips/{cid}/send"
    jid = client.post(route, json={"platform": "tiktok"}).json()["id"]
    with StateDBContext(path) as d:
        worker._publish(d, d.claim_next_publish_job())
        assert d.get_publish_job(jid)["status"] == "uncertain"
    assert client.post(route, json={"platform": "tiktok"}).status_code == 409
    rec = f"/composio/jobs/{jid}/reconcile"
    assert client.post(rec, json={"outcome": "absent", "note": "Conferi a caixa de entrada"}).status_code == 403
    assert client.post(rec, headers=headers, json={"outcome": "absent", "note": "Conferi a caixa de entrada e não chegou"}).status_code == 200
    assert client.post(route, json={"platform": "tiktok"}).status_code == 202


def test_known_remote_id_cannot_be_declared_absent(rig):
    client, headers, _, _, path, _ = rig
    with StateDBContext(path) as d:
        d.upsert_video("v")
        cid = d.add_clip("v", 0, 30, 90, "Teste")
        jid = d.add_publish_job(cid, json.dumps({"provider": "composio", "platform": "tiktok"}))
        receipts.save(d, jid, "tiktok", "awaiting_operator", "known-id")
        d.finish_publish_job(jid, "awaiting_operator")
    result = client.post(f"/composio/jobs/{jid}/reconcile", headers=headers,
                         json={"outcome": "absent", "note": "Conferi mas quero repetir"})
    assert result.status_code == 409


def test_oauth_url_goes_to_electron_and_credentials_are_not_in_state(monkeypatch, caplog):
    import logging
    from publish.oauth import ConnectFlow, client_config
    import google_auth_oauthlib.flow
    creds = Mock()
    def local_server(**kw):
        assert kw["host"] == "127.0.0.1" and kw["port"] == 0 and kw["timeout_seconds"] == 300
        assert kw["authorization_prompt_message"] is None
        webbrowser.get(kw["browser"]).open("https://accounts.google.com/o/oauth2/auth?state=fake-state")
        return creds
    factory = Mock(return_value=Mock(run_local_server=local_server))
    monkeypatch.setattr(google_auth_oauthlib.flow.InstalledAppFlow, "from_client_config", factory)
    flow = ConnectFlow(client_config("fake-client", "fake-secret"), ["upload"])
    flow.run()
    assert flow.state == "done" and flow.credentials is creds
    assert flow.authorization_url.startswith("https://accounts.google.com/")
    assert "fake-secret" not in flow.authorization_url
    with caplog.at_level(logging.INFO):
        logging.getLogger("google_auth_oauthlib.flow").info("GET /?code=fixture-oauth-code&state=fixture-state")
    assert "fixture-oauth-code" not in caplog.text


def test_oauth_completion_persists_account_without_returning_tokens(tmp_path, monkeypatch):
    from core import secrets
    from publish import oauth
    from publish.youtube_shorts import token_name_for
    from server import youtube_api, youtube_service
    path = tmp_path / "state.db"
    with StateDBContext(path) as d:
        youtube_service.save_settings(d, {"enabled": True})
    app = FastAPI()
    youtube_api.install(app, config={}, db=lambda: StateDB(path), data_dir=tmp_path,
                        worker=Mock(), publish_worker=Mock())
    client = TestClient(app)
    monkeypatch.setitem(youtube_api._flow, "thread", None)
    class Flow:
        state = "done"
        error = ""
        credentials = Mock(scopes=["upload", "readonly"])
        credentials.to_json.return_value = json.dumps({"token": "fixture-access", "refresh_token": "fixture-refresh"})
        def __init__(self, *args): pass
        def is_alive(self): return False
        def start(self): pass
    monkeypatch.setattr(oauth, "ConnectFlow", Flow)
    monkeypatch.setattr(youtube_service, "make_publisher", lambda *a, **kw: Mock(channel_info=lambda: {"id": "test-channel", "title": "Canal de ensaio"}))
    assert client.put("/youtube/credentials", json={"client_id": "fixture-client", "client_secret": "fixture-secret"}).status_code == 200
    assert client.post("/youtube/connect", json={}).status_code == 200
    response = client.get("/youtube/connect")
    assert response.json()["status"]["connected"] is True
    assert response.json()["channel"]["id"] == "test-channel"
    assert secrets.has(tmp_path, token_name_for("test-channel"))
    assert not secrets.has(tmp_path, token_name_for("pending"))
    assert all(value not in response.text for value in ("fixture-secret", "fixture-access", "fixture-refresh"))


def test_total_deadline_terminates_stalled_transfer(monkeypatch, tmp_path):
    # A producer that has submitted, then never responds. The OS process is
    # doubled so Windows startup latency cannot consume the test's deadline.
    receiver, sender, process = Mock(), Mock(), Mock()
    receiver.recv.return_value = ("submitting", "")
    events = iter([True])
    def poll(seconds):
        value = next(events, False)
        if not value:
            time.sleep(seconds)
        return value
    receiver.poll.side_effect = poll
    process.is_alive.return_value = True
    ctx = Mock()
    ctx.Pipe.return_value = (receiver, sender)
    ctx.Process.return_value = process
    monkeypatch.setattr(transfer.multiprocessing, "get_context", lambda *_: ctx)
    started = time.monotonic()
    with pytest.raises(receipts.UncertainDelivery):
        transfer.bounded_upload("fake", {}, tmp_path / "unused", lambda: False, lambda: None, seconds=.2)
    assert time.monotonic() - started < 2
    process.terminate.assert_called_once()
    process.join.assert_called_once_with(timeout=2)


def test_editor_limits_speech_and_preserves_game_tag():
    from llm.editorial import decide
    backend = Mock(supports_schema=False)
    backend.generate.return_value = json.dumps({"trim_start": 2, "trim_end": 2, "titulo": "Fuga",
        "descricao": "Texto", "hashtags": ["#fuga"], "motivo": "Remover bordas"})
    result = decide(backend, {"hashtags": ["#GTA6"], "transcricao": [{"start": .5, "end": 29.5}]}, 30)
    assert result.trim_start == pytest.approx(.4) and result.trim_end == pytest.approx(.4)
    assert "#GTA6" in result.hashtags
    assert "#GTA6" in result.titulo
    result = decide(backend, {"hashtags": []}, 30)
    assert result.trim_start == result.trim_end == 0


@pytest.mark.parametrize("delta", [-1, 3, float('nan')])
def test_editor_refuses_invalid_limits(delta):
    from llm.editorial import decide
    backend = Mock(supports_schema=False)
    backend.generate.return_value = json.dumps({"trim_start": delta, "titulo": "Fuga", "descricao": "",
                                              "hashtags": [], "motivo": "Teste"})
    with pytest.raises(ValueError):
        decide(backend, {}, 30)


def test_real_trim_keeps_audio_duration_and_original(tmp_path):
    import subprocess
    from core.binaries import ffmpeg, ffprobe
    from llm.editorial import EditorialDecision
    path = tmp_path / "corte.json"
    path.write_text("{}")
    source = path.with_suffix(".mp4")
    subprocess.run([ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=10",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=10", "-c:v", "libx264", "-c:a", "aac",
                    "-shortest", str(source)], check=True, capture_output=True, timeout=30)
    original = source.read_bytes()
    decision = EditorialDecision(trim_start=1, trim_end=1, titulo="Ensaio", descricao="", hashtags=[], motivo="Silêncio nas bordas")
    desk.edit(path, {}, decision, 10)
    assert desk.duration(source) == pytest.approx(8, abs=.15)
    assert (tmp_path / "originais" / "corte.mp4").read_bytes() == original
    result = subprocess.run([ffprobe(), "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
                             "-of", "json", str(source)], check=True, capture_output=True, text=True, timeout=20)
    assert json.loads(result.stdout)["streams"][0]["codec_type"] == "audio"
