from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.state import StateDB
from publish import composio
from server.composio_api import install
from server.publisher import PublishWorker


@pytest.mark.parametrize("platform", ["youtube", "tiktok"])
def test_composio_connect_queue_and_worker(tmp_path, monkeypatch, platform):
    path = tmp_path / "state.db"
    db = StateDB(path)
    db.set_flag(composio.TIKTOK_CONFIG, "ac_test")
    db.upsert_video("source")
    clip_path = tmp_path / "clips" / "test.mp4"
    clip_path.parent.mkdir()
    clip_path.write_bytes(b"test video data")
    clip_id = db.add_clip("source", 0, 10, 90, "Cut", path=str(clip_path))
    worker = PublishWorker({}, path, tmp_path)
    app = FastAPI()
    install(app, db=lambda: StateDB(path), data_dir=tmp_path, publish_worker=worker)
    client = TestClient(app)
    monkeypatch.setenv("COMPOSIO_API_KEY", "test-key")
    account = "ca_clipador"
    status = "INITIATED"
    requests_to_provider = []
    tool, version = composio.TOOLS[platform]

    def call(_key, method, path, *, body=None, **options):
        requests_to_provider.append((method, path, body))
        if path == "/tool_router/session":
            assert body["toolkits"] == {"enable": [platform]}
            if platform == "tiktok":
                assert body["auth_configs"] == {"tiktok": "ac_test"}
            return {"session_id": "trs_clipador"}
        if path.endswith("/link"):
            return {"connected_account_id": account, "redirect_url": "https://app.composio.dev/link/lt_test"}
        if path == f"/connected_accounts/{account}":
            return {"status": status, "toolkit": {"slug": platform}}
        if path == "/files/upload/request":
            return {"type": "new", "key": "stage/video", "new_presigned_url":
                    "https://temp.0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com/video"}
        if path == f"/tools/execute/{tool}":
            data = {"id": "test1234_-A"} if platform == "youtube" else {"data": {"publish_id": "v_inbox~01"}}
            return {"successful": True, "data": data}
        pytest.fail(f"Unexpected endpoint {path}")

    monkeypatch.setattr(composio, "call", call)
    put = Mock(return_value=Mock(status_code=200))
    monkeypatch.setattr(composio.requests, "put", put)
    request = {"platform": platform}
    send = f"/composio/clips/{clip_id}/send"
    try:
        assert client.post(send, json=request).status_code == 409
        assert client.post("/composio/connect", json=request).status_code == 200
        assert not client.get("/composio/status").json()["channels"][platform]["connected"]
        status = "ACTIVE"
        assert client.get("/composio/status").json()["channels"][platform]["connected"]
        response = client.post(send, json=request)
        assert response.status_code == 202, response.text
        assert client.post(send, json=request).status_code == 409
        worker._publish(db, db.claim_next_publish_job())
        [job] = client.get(f"/composio/clips/{clip_id}/jobs").json()
        assert job["status"] == "done"
        assert bool(job["url"]) is (platform == "youtube")
        put.assert_called_once()
        execute = requests_to_provider[-1][2]
        assert execute["connected_account_id"] == account
        assert execute["version"] == version
        arguments = execute["arguments"]
        if platform == "youtube":
            assert arguments["privacyStatus"] == "private"
            assert arguments["videoFilePath"]["s3key"] == "stage/video"
        else:
            assert arguments["publish"] is False
            assert arguments["file_to_upload"]["s3key"] == "stage/video"
    finally:
        db.close()
