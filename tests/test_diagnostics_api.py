from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.state import StateDB
from plugins import session
from server.diagnostics_api import install


def test_diagnostics_require_session_and_filter_history(tmp_path):
    secret = "test-session-unique-value"
    headers = {session.HEADER: secret}
    db = StateDB(tmp_path / "state.db")
    try:
        job_id = db.add_job("process", "{}")
        db.finish_job(job_id, "failed", "Falha de rede em https://example.test/live?key=privada")
        cancelled = db.add_job("process", "{}")
        db.finish_job(cancelled, "cancelled", "Cancelado")
        publish_id = db.add_publish_job(10, "{}")
        db.finish_publish_job(publish_id, "failed", error="Falha ao publicar")
        db.record_clip_publish(10, "tiktok", {"state": "failed", "error": "Envio recusado"})
    finally:
        db.close()

    path = tmp_path / "logs" / f"job_{job_id}.log"
    path.parent.mkdir()
    path.write_text("a" * 70_000 + f"\nliberação falhou\naccess_token: pequeno\n{secret}\n", encoding="utf-8")
    recorder = tmp_path / "cola.log"
    recorder.write_text("recorder ok\n", encoding="utf-8")
    app = FastAPI()
    install(app, data_dir=tmp_path, recorder_log=recorder, session_secret=secret)
    client = TestClient(app)

    assert client.get("/diagnostics/errors").status_code == 403
    assert client.get("/diagnostics/logs/recorder", headers={session.HEADER: "wrong"}).status_code == 403
    result = client.get("/diagnostics/errors", headers=headers)
    assert result.headers["cache-control"] == "no-store"
    errors = {error["source"]: error for error in result.json()["errors"]}
    assert set(errors) == {"processing", "publication", "delivery"}
    assert errors["processing"]["job_id"] == job_id
    assert errors["processing"]["error"] == "Falha de rede em [url]"
    assert errors["publication"]["job_id"] == publish_id
    assert errors["delivery"]["operation"] == "tiktok"

    result = client.get("/diagnostics/logs/job", params={"job_id": job_id}, headers=headers).json()
    assert result["lines"] == ["liberação falhou", "[linha ocultada: credencial]", "[redacted]"]
    assert client.get("/diagnostics/logs/job", params={"job_id": cancelled}, headers=headers).json()["status"] == "missing"
    assert client.get("/diagnostics/logs/job", headers=headers).status_code == 422
    assert client.get("/diagnostics/logs/recorder", headers=headers).json()["lines"] == ["recorder ok"]
    assert client.get("/diagnostics/logs/engine?lines=101", headers=headers).status_code == 422
